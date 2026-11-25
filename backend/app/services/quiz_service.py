from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.repositories.course_repository import (
    MongoCourse,
    get_course_by_id,
    get_enrollment_by_student_and_course,
    get_lesson_by_id,
    get_section_by_id,
)
from app.repositories.quiz_repository import (
    MongoAnswerOption,
    MongoQuestion,
    MongoQuiz,
    count_all_attempts_by_quiz_ids,
    count_completed_attempts_for_student_quiz,
    create_question_with_options_doc,
    create_quiz_attempt_doc,
    create_quiz_doc,
    delete_question_cascade_mongo,
    delete_question_from_sqlite_shadow,
    delete_quiz_attempt_doc,
    delete_quiz_cascade_mongo,
    delete_quiz_from_sqlite_shadow,
    get_latest_unfinished_attempt,
    get_question_by_id,
    get_quiz_attempt_by_id,
    get_quiz_by_id,
    get_quizzes_by_ids,
    list_attempt_answers,
    list_completed_attempts_for_student,
    list_completed_attempts_for_student_quiz,
    list_options_for_question_ids,
    list_questions_for_quiz,
    list_quizzes_for_course,
    replace_attempt_answers_docs,
    replace_question_and_options_doc,
    restore_question_snapshot,
    restore_quiz_attempt_snapshot,
    restore_quiz_snapshot,
    sync_question_to_sqlite_shadow,
    sync_quiz_attempt_to_sqlite_shadow,
    sync_quiz_to_sqlite_shadow,
    update_quiz_attempt_doc,
    update_quiz_doc,
)
from app.repositories.user_repository import MongoUser
from app.schemas.quiz import (
    AnswerOptionDetail,
    AnswerOptionResponse,
    QuestionCreate,
    QuestionDetail,
    QuestionResponse,
    QuestionReviewItem,
    QuizAttemptAnswerReview,
    QuizAttemptResult,
    QuizAttemptSummary,
    QuizCreate,
    QuizDetail,
    QuizResponse,
    QuizStartResponse,
    QuizSubmission,
    QuizUpdate,
)


def _check_course_instructor_or_admin(course: MongoCourse, user: MongoUser) -> None:
    """Ensure user is course instructor or system administrator."""
    if user.role == "admin":
        return
    if course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to manage assessments for this course.",
        )


def _validate_quiz_course_links(
    mongo_db: Database,
    course_id: int,
    section_id: Optional[int],
    lesson_id: Optional[int],
) -> None:
    if section_id is not None and section_id > 0:
        sec = get_section_by_id(mongo_db, section_id)
        if not sec or sec.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Section does not exist or does not belong to this course.",
            )
    if lesson_id is not None and lesson_id > 0:
        les = get_lesson_by_id(mongo_db, lesson_id)
        if not les or les.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lesson does not exist or does not belong to this course.",
            )


def _load_questions_and_options(
    mongo_db: Database,
    quiz_id: int,
) -> tuple[List[MongoQuestion], Dict[int, List[MongoAnswerOption]]]:
    questions = list_questions_for_quiz(mongo_db, quiz_id)
    options_map = list_options_for_question_ids(mongo_db, [q.id for q in questions])
    return questions, options_map


def _build_quiz_detail(
    quiz: MongoQuiz,
    questions: List[MongoQuestion],
    options_map: Dict[int, List[MongoAnswerOption]],
    total_attempts: int = 0,
) -> QuizDetail:
    """Convert MongoQuiz + questions + options to QuizDetail with answer keys."""
    questions_detail = []
    for q in sorted(questions, key=lambda x: x.order_index):
        opts = [
            AnswerOptionDetail(
                id=opt.id,
                question_id=opt.question_id,
                option_text=opt.option_text,
                is_correct=opt.is_correct,
            )
            for opt in sorted(options_map.get(q.id, []), key=lambda x: x.id)
        ]
        questions_detail.append(
            QuestionDetail(
                id=q.id,
                quiz_id=q.quiz_id,
                question_text=q.question_text,
                order_index=q.order_index,
                points=q.points,
                options=opts,
            )
        )
    return QuizDetail(
        id=quiz.id,
        course_id=quiz.course_id,
        section_id=quiz.section_id,
        lesson_id=quiz.lesson_id,
        title=quiz.title,
        description=quiz.description,
        passing_score=quiz.passing_score,
        is_published=quiz.is_published,
        time_limit_minutes=quiz.time_limit_minutes,
        max_attempts=quiz.max_attempts,
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
        questions=questions_detail,
        total_attempts=total_attempts,
    )


def _require_student_quiz_access(
    mongo_db: Database,
    quiz: MongoQuiz,
    user: MongoUser,
    *,
    action_label: str,
) -> None:
    is_manager = user.role in ("instructor", "admin")
    if not quiz.is_published and not is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assessment is currently in draft mode and not published.",
        )

    if not is_manager:
        enrollment = get_enrollment_by_student_and_course(mongo_db, user.id, quiz.course_id)
        if not enrollment or enrollment.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You must be enrolled in the course to {action_label} this quiz.",
            )


def get_quiz_for_student(
    mongo_db: Database,
    quiz_id: int,
    user: MongoUser,
) -> QuizResponse:
    """
    Fetch quiz and questions for student taking the quiz.
    CRITICAL SECURITY RULE: Never expose is_correct in student view before submission.
    """
    quiz = get_quiz_by_id(mongo_db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    _require_student_quiz_access(mongo_db, quiz, user, action_label="take")

    completed_attempts = list_completed_attempts_for_student_quiz(mongo_db, quiz.id, user.id)
    attempts_count = len(completed_attempts)
    best_score = max([a.score for a in completed_attempts], default=None)
    can_attempt = not (quiz.max_attempts > 0 and attempts_count >= quiz.max_attempts)

    questions, options_map = _load_questions_and_options(mongo_db, quiz.id)
    questions_response = []
    for q in sorted(questions, key=lambda x: x.order_index):
        options_response = [
            AnswerOptionResponse(
                id=opt.id,
                question_id=opt.question_id,
                option_text=opt.option_text,
            )
            for opt in sorted(options_map.get(q.id, []), key=lambda x: x.id)
        ]
        questions_response.append(
            QuestionResponse(
                id=q.id,
                quiz_id=q.quiz_id,
                question_text=q.question_text,
                order_index=q.order_index,
                points=q.points,
                options=options_response,
            )
        )

    return QuizResponse(
        id=quiz.id,
        course_id=quiz.course_id,
        section_id=quiz.section_id,
        lesson_id=quiz.lesson_id,
        title=quiz.title,
        description=quiz.description,
        passing_score=quiz.passing_score,
        is_published=quiz.is_published,
        time_limit_minutes=quiz.time_limit_minutes,
        max_attempts=quiz.max_attempts,
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
        questions=questions_response,
        attempts_count=attempts_count,
        can_attempt=can_attempt,
        best_score=best_score,
    )


def start_quiz_attempt(
    mongo_db: Database,
    quiz_id: int,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> QuizStartResponse:
    """Start an authorized quiz attempt session with timer calculation."""
    quiz = get_quiz_by_id(mongo_db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    _require_student_quiz_access(mongo_db, quiz, user, action_label="take")

    completed_count = count_completed_attempts_for_student_quiz(mongo_db, quiz.id, user.id)
    if quiz.max_attempts > 0 and completed_count >= quiz.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You have reached the maximum allowed attempts ({quiz.max_attempts}) for this quiz.",
        )

    active_attempt = get_latest_unfinished_attempt(mongo_db, quiz.id, user.id)
    now = datetime.now(timezone.utc)

    if active_attempt and quiz.time_limit_minutes:
        elapsed = (now - active_attempt.started_at).total_seconds()
        if elapsed > (quiz.time_limit_minutes * 60 + 120):
            closed = update_quiz_attempt_doc(
                mongo_db,
                active_attempt.id,
                {"is_completed": True, "submitted_at": now},
            )
            if closed:
                sync_quiz_attempt_to_sqlite_shadow(sqlite_db, closed)
            completed_count += 1
            if quiz.max_attempts > 0 and completed_count >= quiz.max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Previous attempt expired. Maximum allowed attempts ({quiz.max_attempts}) reached.",
                )
            active_attempt = None

    if not active_attempt:
        active_attempt = create_quiz_attempt_doc(
            mongo_db,
            quiz_id=quiz.id,
            student_id=user.id,
            attempt_number=completed_count + 1,
            is_completed=False,
            now=now,
        )
        try:
            sync_quiz_attempt_to_sqlite_shadow(sqlite_db, active_attempt)
        except Exception:
            delete_quiz_attempt_doc(mongo_db, active_attempt.id)
            raise

    expires_at = None
    if quiz.time_limit_minutes:
        expires_at = active_attempt.started_at + timedelta(minutes=quiz.time_limit_minutes)

    return QuizStartResponse(
        attempt_id=active_attempt.id,
        quiz_id=quiz.id,
        attempt_number=active_attempt.attempt_number,
        max_attempts=quiz.max_attempts,
        time_limit_minutes=quiz.time_limit_minutes,
        started_at=active_attempt.started_at,
        expires_at=expires_at,
    )


def evaluate_quiz_submission(
    mongo_db: Database,
    quiz_id: int,
    user: MongoUser,
    submission: QuizSubmission,
    sqlite_db: Optional[Session] = None,
) -> QuizAttemptResult:
    """Evaluate quiz on server side and persist attempt in MongoDB."""
    quiz = get_quiz_by_id(mongo_db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    _require_student_quiz_access(mongo_db, quiz, user, action_label="submit")

    questions, options_map = _load_questions_and_options(mongo_db, quiz.id)
    if not questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This quiz has no questions.")

    if isinstance(submission.answers, list):
        answers_dict = {item.question_id: item.selected_option_id for item in submission.answers}
    elif isinstance(submission.answers, dict):
        answers_dict = {int(k): int(v) for k, v in submission.answers.items()}
    else:
        answers_dict = {}

    now = datetime.now(timezone.utc)
    attempt = None
    prev_attempt_snapshot = None
    created_new_attempt = False

    if submission.attempt_id:
        attempt = get_quiz_attempt_by_id(mongo_db, submission.attempt_id)
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt session not found.")
        if attempt.student_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This attempt session belongs to another student.")
        if attempt.is_completed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This quiz attempt has already been submitted and graded.")

        if quiz.time_limit_minutes:
            elapsed = (now - attempt.started_at).total_seconds()
            max_allowed = (quiz.time_limit_minutes * 60) + 120
            if elapsed > max_allowed:
                closed = update_quiz_attempt_doc(
                    mongo_db,
                    attempt.id,
                    {"is_completed": True, "submitted_at": now},
                )
                if closed:
                    sync_quiz_attempt_to_sqlite_shadow(sqlite_db, closed)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Time limit for this quiz has expired.",
                )
        prev_attempt_snapshot = attempt

    if not attempt:
        completed_count = count_completed_attempts_for_student_quiz(mongo_db, quiz.id, user.id)
        if quiz.max_attempts > 0 and completed_count >= quiz.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You have reached the maximum allowed attempts ({quiz.max_attempts}) for this quiz.",
            )
        attempt = create_quiz_attempt_doc(
            mongo_db,
            quiz_id=quiz.id,
            student_id=user.id,
            attempt_number=completed_count + 1,
            is_completed=False,
            now=now,
        )
        created_new_attempt = True

    points_earned = 0
    total_possible_points = sum(q.points for q in questions)
    answers_to_create = []
    answers_review = []
    review_items = []

    for q in sorted(questions, key=lambda x: x.order_index):
        opts = options_map.get(q.id, [])
        selected_option_id = answers_dict.get(q.id)
        selected_opt = next((opt for opt in opts if opt.id == selected_option_id), None)
        correct_option = next((opt for opt in opts if opt.is_correct), None)
        correct_option_id = correct_option.id if correct_option else 0
        correct_option_text = correct_option.option_text if correct_option else ""

        is_correct = False
        awarded = 0
        if selected_opt and selected_opt.is_correct:
            is_correct = True
            awarded = q.points
            points_earned += awarded

        answers_to_create.append({
            "question_id": q.id,
            "selected_option_id": selected_option_id,
            "is_correct": is_correct,
            "awarded_points": awarded,
        })

        answers_review.append(
            QuizAttemptAnswerReview(
                question_id=q.id,
                question_text=q.question_text,
                selected_option_id=selected_option_id,
                selected_option_text=selected_opt.option_text if selected_opt else None,
                correct_option_id=correct_option_id,
                correct_option_text=correct_option_text,
                is_correct=is_correct,
                awarded_points=awarded,
                points=q.points,
            )
        )

        review_items.append(
            QuestionReviewItem(
                question_id=q.id,
                question_text=q.question_text,
                selected_option_id=selected_option_id,
                correct_option_id=correct_option_id,
                is_correct=is_correct,
            )
        )

    score_percentage = (
        round((points_earned / total_possible_points) * 100.0, 1)
        if total_possible_points > 0
        else 100.0
    )
    passed = score_percentage >= quiz.passing_score

    updated_attempt = update_quiz_attempt_doc(
        mongo_db,
        attempt.id,
        {
            "score": score_percentage,
            "total_points": total_possible_points,
            "passed": passed,
            "submitted_at": now,
            "is_completed": True,
        },
    )
    assert updated_attempt is not None
    stored_answers = replace_attempt_answers_docs(
        mongo_db,
        updated_attempt.id,
        answers_to_create,
    )

    try:
        sync_quiz_attempt_to_sqlite_shadow(sqlite_db, updated_attempt, stored_answers)
    except Exception:
        if created_new_attempt:
            delete_quiz_attempt_doc(mongo_db, updated_attempt.id)
        elif prev_attempt_snapshot is not None:
            restore_quiz_attempt_snapshot(mongo_db, prev_attempt_snapshot)
        raise

    return QuizAttemptResult(
        id=updated_attempt.id,
        attempt_id=updated_attempt.id,
        quiz_id=quiz.id,
        quiz_title=quiz.title,
        student_id=user.id,
        attempt_number=updated_attempt.attempt_number,
        score=score_percentage,
        total_points=total_possible_points,
        total_questions=len(questions),
        passing_score=quiz.passing_score,
        passed=passed,
        started_at=updated_attempt.started_at,
        submitted_at=updated_attempt.submitted_at,
        answers=answers_review,
        questions_review=review_items,
    )


def get_attempt_detail(
    mongo_db: Database,
    attempt_id: int,
    user: MongoUser,
) -> QuizAttemptResult:
    """Retrieve private quiz attempt results with authorization check."""
    attempt = get_quiz_attempt_by_id(mongo_db, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found.")

    quiz = get_quiz_by_id(mongo_db, attempt.quiz_id) if attempt.quiz_id is not None else None
    course = get_course_by_id(mongo_db, quiz.course_id) if quiz else None
    if user.id != attempt.student_id and user.role != "admin" and (not course or course.instructor_id != user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this assessment result.",
        )

    questions, options_map = (
        _load_questions_and_options(mongo_db, attempt.quiz_id)
        if attempt.quiz_id is not None
        else ([], {})
    )
    answers_map = {a.question_id: a for a in list_attempt_answers(mongo_db, attempt.id)}

    answers_review = []
    review_items = []
    for q in questions:
        ans = answers_map.get(q.id)
        selected_option_id = ans.selected_option_id if ans else None
        is_correct = ans.is_correct if ans else False
        awarded_points = ans.awarded_points if ans else 0

        opts = options_map.get(q.id, [])
        selected_opt = next((opt for opt in opts if opt.id == selected_option_id), None)
        correct_opt = next((opt for opt in opts if opt.is_correct), None)
        correct_option_id = correct_opt.id if correct_opt else 0
        correct_option_text = correct_opt.option_text if correct_opt else ""

        answers_review.append(
            QuizAttemptAnswerReview(
                question_id=q.id,
                question_text=q.question_text,
                selected_option_id=selected_option_id,
                selected_option_text=selected_opt.option_text if selected_opt else None,
                correct_option_id=correct_option_id,
                correct_option_text=correct_option_text,
                is_correct=is_correct,
                awarded_points=awarded_points,
                points=q.points,
            )
        )

        review_items.append(
            QuestionReviewItem(
                question_id=q.id,
                question_text=q.question_text,
                selected_option_id=selected_option_id,
                correct_option_id=correct_option_id,
                is_correct=is_correct,
            )
        )

    return QuizAttemptResult(
        id=attempt.id,
        attempt_id=attempt.id,
        quiz_id=attempt.quiz_id,
        quiz_title=quiz.title if quiz else "Quiz Assessment",
        student_id=attempt.student_id,
        attempt_number=attempt.attempt_number,
        score=attempt.score,
        total_points=attempt.total_points,
        total_questions=len(questions),
        passing_score=quiz.passing_score if quiz else 70,
        passed=attempt.passed,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        answers=answers_review,
        questions_review=review_items,
    )


def list_user_attempts(
    mongo_db: Database,
    user_id: int,
    quiz_id: Optional[int] = None,
) -> List[QuizAttemptSummary]:
    attempts = list_completed_attempts_for_student(mongo_db, user_id, quiz_id=quiz_id)
    quiz_map = get_quizzes_by_ids(
        mongo_db,
        [a.quiz_id for a in attempts if a.quiz_id is not None],
    )
    return [
        QuizAttemptSummary(
            id=a.id,
            quiz_id=a.quiz_id,
            quiz_title=quiz_map[a.quiz_id].title if a.quiz_id in quiz_map else "Quiz",
            course_id=quiz_map[a.quiz_id].course_id if a.quiz_id in quiz_map else 0,
            score=a.score,
            total_points=a.total_points,
            passed=a.passed,
            submitted_at=a.submitted_at,
        )
        for a in attempts
    ]


# ---------------------------------------------------------------------------
# Instructor Quiz Management Service Functions
# ---------------------------------------------------------------------------


def list_quizzes_for_course_instructor(
    mongo_db: Database,
    course_id: int,
    user: MongoUser,
) -> List[QuizDetail]:
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    quizzes = list_quizzes_for_course(mongo_db, course_id)
    attempt_counts = count_all_attempts_by_quiz_ids(mongo_db, [q.id for q in quizzes])
    results = []
    for q in quizzes:
        questions, options_map = _load_questions_and_options(mongo_db, q.id)
        results.append(
            _build_quiz_detail(
                q,
                questions,
                options_map,
                total_attempts=attempt_counts.get(q.id, 0),
            )
        )
    return results


def get_quiz_detail_for_instructor(
    mongo_db: Database,
    quiz_id: int,
    user: MongoUser,
) -> QuizDetail:
    quiz = get_quiz_by_id(mongo_db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = get_course_by_id(mongo_db, quiz.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    questions, options_map = _load_questions_and_options(mongo_db, quiz.id)
    total_attempts = count_all_attempts_by_quiz_ids(mongo_db, [quiz.id]).get(quiz.id, 0)
    return _build_quiz_detail(quiz, questions, options_map, total_attempts=total_attempts)


def _validate_questions_payload(questions: List[QuestionCreate]) -> None:
    for q_data in questions:
        if len(q_data.options) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question '{q_data.question_text}' must have at least 2 answer options.",
            )
        if not any(opt.is_correct for opt in q_data.options):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question '{q_data.question_text}' must have at least one marked correct answer option.",
            )


def create_instructor_quiz(
    mongo_db: Database,
    course_id: int,
    quiz_in: QuizCreate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> QuizDetail:
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    _validate_quiz_course_links(
        mongo_db,
        course_id,
        quiz_in.section_id,
        quiz_in.lesson_id,
    )
    _validate_questions_payload(quiz_in.questions)

    quiz = create_quiz_doc(
        mongo_db,
        course_id=course_id,
        section_id=quiz_in.section_id,
        lesson_id=quiz_in.lesson_id,
        title=quiz_in.title,
        description=quiz_in.description,
        passing_score=quiz_in.passing_score,
        is_published=quiz_in.is_published,
        time_limit_minutes=quiz_in.time_limit_minutes,
        max_attempts=quiz_in.max_attempts,
        sqlite_db=sqlite_db,
    )
    created_q_pairs: List[tuple[MongoQuestion, List[MongoAnswerOption]]] = []
    for q_data in quiz_in.questions:
        q_obj, opt_objs = create_question_with_options_doc(
            mongo_db,
            quiz_id=quiz.id,
            question_text=q_data.question_text,
            order_index=q_data.order_index,
            points=q_data.points,
            options_data=[opt.model_dump() for opt in q_data.options],
            sqlite_db=sqlite_db,
        )
        created_q_pairs.append((q_obj, opt_objs))

    try:
        sync_quiz_to_sqlite_shadow(sqlite_db, quiz)
        for q_obj, opt_objs in created_q_pairs:
            sync_question_to_sqlite_shadow(sqlite_db, q_obj, opt_objs)
    except Exception:
        delete_quiz_cascade_mongo(mongo_db, quiz.id)
        raise

    questions = [p[0] for p in created_q_pairs]
    options_map = {q.id: opts for q, opts in created_q_pairs}
    return _build_quiz_detail(quiz, questions, options_map, total_attempts=0)


def update_instructor_quiz(
    mongo_db: Database,
    quiz_id: int,
    quiz_in: QuizUpdate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> QuizDetail:
    quiz = get_quiz_by_id(mongo_db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = get_course_by_id(mongo_db, quiz.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    updates: dict = {}
    if quiz_in.title is not None:
        updates["title"] = quiz_in.title.strip()
    if quiz_in.description is not None:
        updates["description"] = quiz_in.description.strip() if quiz_in.description else None
    if quiz_in.passing_score is not None:
        updates["passing_score"] = quiz_in.passing_score
    if quiz_in.is_published is not None:
        updates["is_published"] = quiz_in.is_published
    if quiz_in.time_limit_minutes is not None:
        updates["time_limit_minutes"] = quiz_in.time_limit_minutes
    if quiz_in.max_attempts is not None:
        updates["max_attempts"] = quiz_in.max_attempts
    if quiz_in.section_id is not None:
        if quiz_in.section_id > 0:
            _validate_quiz_course_links(mongo_db, quiz.course_id, quiz_in.section_id, None)
            updates["section_id"] = quiz_in.section_id
        else:
            updates["section_id"] = None
    if quiz_in.lesson_id is not None:
        if quiz_in.lesson_id > 0:
            _validate_quiz_course_links(mongo_db, quiz.course_id, None, quiz_in.lesson_id)
            updates["lesson_id"] = quiz_in.lesson_id
        else:
            updates["lesson_id"] = None

    updated = update_quiz_doc(mongo_db, quiz.id, updates) if updates else quiz
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    try:
        sync_quiz_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_quiz_snapshot(mongo_db, quiz)
        raise

    questions, options_map = _load_questions_and_options(mongo_db, updated.id)
    attempts_count = count_all_attempts_by_quiz_ids(mongo_db, [updated.id]).get(updated.id, 0)
    return _build_quiz_detail(updated, questions, options_map, total_attempts=attempts_count)


def toggle_publish_quiz(
    mongo_db: Database,
    quiz_id: int,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> QuizDetail:
    quiz = get_quiz_by_id(mongo_db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = get_course_by_id(mongo_db, quiz.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    questions, options_map = _load_questions_and_options(mongo_db, quiz.id)
    target_state = not quiz.is_published
    if target_state:
        if not questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot publish a quiz with no questions. Please add at least one question.",
            )
        for q in questions:
            if not any(opt.is_correct for opt in options_map.get(q.id, [])):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Question '{q.question_text}' has no correct option selected.",
                )

    updated = update_quiz_doc(mongo_db, quiz.id, {"is_published": target_state})
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    try:
        sync_quiz_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_quiz_snapshot(mongo_db, quiz)
        raise

    attempts_count = count_all_attempts_by_quiz_ids(mongo_db, [updated.id]).get(updated.id, 0)
    return _build_quiz_detail(updated, questions, options_map, total_attempts=attempts_count)


def delete_instructor_quiz(
    mongo_db: Database,
    quiz_id: int,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> None:
    quiz = get_quiz_by_id(mongo_db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = get_course_by_id(mongo_db, quiz.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    delete_quiz_cascade_mongo(mongo_db, quiz_id)
    delete_quiz_from_sqlite_shadow(sqlite_db, quiz_id)


def add_quiz_question(
    mongo_db: Database,
    quiz_id: int,
    question_in: QuestionCreate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> QuestionDetail:
    quiz = get_quiz_by_id(mongo_db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = get_course_by_id(mongo_db, quiz.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    if len(question_in.options) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question must have at least 2 options.")
    if not any(opt.is_correct for opt in question_in.options):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question must have at least one correct option.")

    question, options = create_question_with_options_doc(
        mongo_db,
        quiz_id=quiz.id,
        question_text=question_in.question_text,
        order_index=question_in.order_index,
        points=question_in.points,
        options_data=[opt.model_dump() for opt in question_in.options],
        sqlite_db=sqlite_db,
    )
    try:
        sync_question_to_sqlite_shadow(sqlite_db, question, options)
    except Exception:
        delete_question_cascade_mongo(mongo_db, question.id)
        raise

    opts = [
        AnswerOptionDetail(
            id=o.id,
            question_id=o.question_id,
            option_text=o.option_text,
            is_correct=o.is_correct,
        )
        for o in sorted(options, key=lambda x: x.id)
    ]
    return QuestionDetail(
        id=question.id,
        quiz_id=question.quiz_id,
        question_text=question.question_text,
        order_index=question.order_index,
        points=question.points,
        options=opts,
    )


def update_quiz_question(
    mongo_db: Database,
    question_id: int,
    question_in: QuestionCreate,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> QuestionDetail:
    question = get_question_by_id(mongo_db, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    quiz = get_quiz_by_id(mongo_db, question.quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = get_course_by_id(mongo_db, quiz.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    if len(question_in.options) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question must have at least 2 options.")
    if not any(opt.is_correct for opt in question_in.options):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question must have at least one correct option.")

    prev_opts = list_options_for_question_ids(mongo_db, [question.id]).get(question.id, [])
    replaced = replace_question_and_options_doc(
        mongo_db,
        question_id=question.id,
        question_text=question_in.question_text,
        order_index=question_in.order_index,
        points=question_in.points,
        options_data=[opt.model_dump() for opt in question_in.options],
        sqlite_db=sqlite_db,
    )
    if not replaced:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    updated_q, new_opts = replaced

    try:
        sync_question_to_sqlite_shadow(sqlite_db, updated_q, new_opts)
    except Exception:
        restore_question_snapshot(mongo_db, question, prev_opts)
        raise

    opts = [
        AnswerOptionDetail(
            id=o.id,
            question_id=o.question_id,
            option_text=o.option_text,
            is_correct=o.is_correct,
        )
        for o in sorted(new_opts, key=lambda x: x.id)
    ]
    return QuestionDetail(
        id=updated_q.id,
        quiz_id=updated_q.quiz_id,
        question_text=updated_q.question_text,
        order_index=updated_q.order_index,
        points=updated_q.points,
        options=opts,
    )


def delete_quiz_question(
    mongo_db: Database,
    question_id: int,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> None:
    question = get_question_by_id(mongo_db, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    quiz = get_quiz_by_id(mongo_db, question.quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = get_course_by_id(mongo_db, quiz.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    delete_question_cascade_mongo(mongo_db, question_id)
    delete_question_from_sqlite_shadow(sqlite_db, question_id)
