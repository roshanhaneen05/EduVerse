from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.quiz import (
    AnswerOption,
    Question,
    Quiz,
    QuizAttempt,
    QuizAttemptAnswer,
)
from app.models.user import User
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


def _check_course_instructor_or_admin(course: Course, user: User) -> None:
    """Ensure user is course instructor or system administrator."""
    if user.role == "admin":
        return
    if course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to manage assessments for this course.",
        )


def _build_quiz_detail(quiz: Quiz, total_attempts: int = 0) -> QuizDetail:
    """Helper to convert Quiz model to QuizDetail with full questions & options."""
    questions_detail = []
    for q in sorted(quiz.questions, key=lambda x: x.order_index):
        opts = [
            AnswerOptionDetail(
                id=opt.id,
                question_id=opt.question_id,
                option_text=opt.option_text,
                is_correct=opt.is_correct,
            )
            for opt in sorted(q.options, key=lambda x: x.id)
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


def get_quiz_for_student(db: Session, quiz_id: int, user: User) -> QuizResponse:
    """
    Fetch quiz and questions for student taking the quiz.
    CRITICAL SECURITY RULE: Never expose is_correct in student view before submission.
    """
    quiz = (
        db.query(Quiz)
        .options(
            joinedload(Quiz.questions).joinedload(Question.options)
        )
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    is_manager = user.role in ("instructor", "admin")
    if not quiz.is_published and not is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assessment is currently in draft mode and not published.",
        )

    if not is_manager:
        enrollment = (
            db.query(CourseEnrollment)
            .filter(
                CourseEnrollment.student_id == user.id,
                CourseEnrollment.course_id == quiz.course_id,
                CourseEnrollment.status == "approved",
            )
            .first()
        )
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in the course to take this quiz.",
            )

    # Calculate attempts metadata for student
    completed_attempts = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.student_id == user.id,
            QuizAttempt.is_completed == True,
        )
        .all()
    )
    attempts_count = len(completed_attempts)
    best_score = max([a.score for a in completed_attempts], default=None)
    can_attempt = True
    if quiz.max_attempts > 0 and attempts_count >= quiz.max_attempts:
        can_attempt = False

    questions_response = []
    for q in sorted(quiz.questions, key=lambda x: x.order_index):
        options_response = [
            AnswerOptionResponse(
                id=opt.id,
                question_id=opt.question_id,
                option_text=opt.option_text,
            )
            for opt in sorted(q.options, key=lambda x: x.id)
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


def start_quiz_attempt(db: Session, quiz_id: int, user: User) -> QuizStartResponse:
    """Start an authorized quiz attempt session with timer calculation."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    is_manager = user.role in ("instructor", "admin")
    if not quiz.is_published and not is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assessment is currently in draft mode and not published.",
        )

    if not is_manager:
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.student_id == user.id,
            CourseEnrollment.course_id == quiz.course_id,
            CourseEnrollment.status == "approved",
        ).first()
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in the course to take this quiz.",
            )

    completed_count = db.query(QuizAttempt).filter(
        QuizAttempt.quiz_id == quiz.id,
        QuizAttempt.student_id == user.id,
        QuizAttempt.is_completed == True,
    ).count()

    if quiz.max_attempts > 0 and completed_count >= quiz.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You have reached the maximum allowed attempts ({quiz.max_attempts}) for this quiz.",
        )

    # Check for active unfinished attempt
    active_attempt = db.query(QuizAttempt).filter(
        QuizAttempt.quiz_id == quiz.id,
        QuizAttempt.student_id == user.id,
        QuizAttempt.is_completed == False,
    ).order_by(QuizAttempt.started_at.desc()).first()

    now = datetime.now(timezone.utc)
    if active_attempt:
        # Check if time limit expired
        if quiz.time_limit_minutes:
            started = active_attempt.started_at.replace(tzinfo=timezone.utc) if active_attempt.started_at.tzinfo is None else active_attempt.started_at
            elapsed = (now - started).total_seconds()
            if elapsed > (quiz.time_limit_minutes * 60 + 120):
                # Auto-close expired attempt
                active_attempt.is_completed = True
                active_attempt.submitted_at = now
                db.commit()
                completed_count += 1
                if quiz.max_attempts > 0 and completed_count >= quiz.max_attempts:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Previous attempt expired. Maximum allowed attempts ({quiz.max_attempts}) reached.",
                    )
                active_attempt = None

    if not active_attempt:
        active_attempt = QuizAttempt(
            student_id=user.id,
            quiz_id=quiz.id,
            score=0.0,
            total_points=0,
            passed=False,
            attempt_number=completed_count + 1,
            is_completed=False,
            started_at=now,
            submitted_at=now,
        )
        db.add(active_attempt)
        db.commit()
        db.refresh(active_attempt)

    started_tz = active_attempt.started_at.replace(tzinfo=timezone.utc) if active_attempt.started_at.tzinfo is None else active_attempt.started_at
    expires_at = None
    if quiz.time_limit_minutes:
        expires_at = started_tz + timedelta(minutes=quiz.time_limit_minutes)

    return QuizStartResponse(
        attempt_id=active_attempt.id,
        quiz_id=quiz.id,
        attempt_number=active_attempt.attempt_number,
        max_attempts=quiz.max_attempts,
        time_limit_minutes=quiz.time_limit_minutes,
        started_at=started_tz,
        expires_at=expires_at,
    )


def evaluate_quiz_submission(
    db: Session,
    quiz_id: int,
    user: User,
    submission: QuizSubmission,
) -> QuizAttemptResult:
    """Evaluate quiz on server side and persist attempt."""
    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions).joinedload(Question.options))
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")

    is_manager = user.role in ("instructor", "admin")
    if not quiz.is_published and not is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assessment is currently in draft mode and not published.",
        )

    if not is_manager:
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.student_id == user.id,
            CourseEnrollment.course_id == quiz.course_id,
            CourseEnrollment.status == "approved",
        ).first()
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in the course to submit this quiz.",
            )

    questions = quiz.questions
    if not questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This quiz has no questions.")

    # Normalize answers dictionary
    if isinstance(submission.answers, list):
        answers_dict = {item.question_id: item.selected_option_id for item in submission.answers}
    elif isinstance(submission.answers, dict):
        answers_dict = {int(k): int(v) for k, v in submission.answers.items()}
    else:
        answers_dict = {}

    now = datetime.now(timezone.utc)
    attempt = None

    if submission.attempt_id:
        attempt = db.query(QuizAttempt).filter(QuizAttempt.id == submission.attempt_id).first()
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt session not found.")
        if attempt.student_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This attempt session belongs to another student.")
        if attempt.is_completed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This quiz attempt has already been submitted and graded.")

        # Time limit check
        if quiz.time_limit_minutes:
            started = attempt.started_at.replace(tzinfo=timezone.utc) if attempt.started_at.tzinfo is None else attempt.started_at
            elapsed = (now - started).total_seconds()
            max_allowed = (quiz.time_limit_minutes * 60) + 120  # 2-minute buffer
            if elapsed > max_allowed:
                attempt.is_completed = True
                attempt.submitted_at = now
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Time limit for this quiz has expired.",
                )

    if not attempt:
        # Check attempts limit
        completed_count = db.query(QuizAttempt).filter(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.student_id == user.id,
            QuizAttempt.is_completed == True,
        ).count()
        if quiz.max_attempts > 0 and completed_count >= quiz.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You have reached the maximum allowed attempts ({quiz.max_attempts}) for this quiz.",
            )
        attempt = QuizAttempt(
            student_id=user.id,
            quiz_id=quiz.id,
            score=0.0,
            total_points=0,
            passed=False,
            attempt_number=completed_count + 1,
            is_completed=False,
            started_at=now,
            submitted_at=now,
        )
        db.add(attempt)
        db.flush()

    points_earned = 0
    total_possible_points = sum(q.points for q in questions)
    answers_to_create = []
    answers_review = []
    review_items = []

    for q in sorted(questions, key=lambda x: x.order_index):
        selected_option_id = answers_dict.get(q.id)
        selected_opt = next((opt for opt in q.options if opt.id == selected_option_id), None)
        correct_option = next((opt for opt in q.options if opt.is_correct), None)
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
        round((points_earned / total_possible_points) * 100.0, 1) if total_possible_points > 0 else 100.0
    )
    passed = score_percentage >= quiz.passing_score

    attempt.score = score_percentage
    attempt.total_points = total_possible_points
    attempt.passed = passed
    attempt.submitted_at = now
    attempt.is_completed = True

    # Delete any previous answers if re-evaluating draft
    db.query(QuizAttemptAnswer).filter(QuizAttemptAnswer.attempt_id == attempt.id).delete()

    for ans in answers_to_create:
        db_answer = QuizAttemptAnswer(
            attempt_id=attempt.id,
            question_id=ans["question_id"],
            selected_option_id=ans["selected_option_id"],
            is_correct=ans["is_correct"],
            awarded_points=ans["awarded_points"],
        )
        db.add(db_answer)

    db.commit()
    db.refresh(attempt)

    return QuizAttemptResult(
        id=attempt.id,
        attempt_id=attempt.id,
        quiz_id=quiz.id,
        quiz_title=quiz.title,
        student_id=user.id,
        attempt_number=attempt.attempt_number,
        score=score_percentage,
        total_points=total_possible_points,
        total_questions=len(questions),
        passing_score=quiz.passing_score,
        passed=passed,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        answers=answers_review,
        questions_review=review_items,
    )


def get_attempt_detail(db: Session, attempt_id: int, user: User) -> QuizAttemptResult:
    """Retrieve private quiz attempt results with authorization check."""
    attempt = (
        db.query(QuizAttempt)
        .options(
            joinedload(QuizAttempt.quiz).joinedload(Quiz.course),
            joinedload(QuizAttempt.answers),
        )
        .filter(QuizAttempt.id == attempt_id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found.")

    course = attempt.quiz.course if attempt.quiz else None
    if user.id != attempt.student_id and user.role != "admin" and (not course or course.instructor_id != user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this assessment result.",
        )

    quiz = attempt.quiz
    questions = (
        db.query(Question)
        .options(joinedload(Question.options))
        .filter(Question.quiz_id == attempt.quiz_id)
        .order_by(Question.order_index.asc())
        .all()
    )
    answers_map = {a.question_id: a for a in attempt.answers}

    answers_review = []
    review_items = []
    for q in questions:
        ans = answers_map.get(q.id)
        selected_option_id = ans.selected_option_id if ans else None
        is_correct = ans.is_correct if ans else False
        awarded_points = ans.awarded_points if ans else 0

        selected_opt = next((opt for opt in q.options if opt.id == selected_option_id), None)
        correct_opt = next((opt for opt in q.options if opt.is_correct), None)
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
    db: Session,
    user_id: int,
    quiz_id: Optional[int] = None,
) -> List[QuizAttemptSummary]:
    query = (
        db.query(QuizAttempt)
        .options(joinedload(QuizAttempt.quiz))
        .filter(QuizAttempt.student_id == user_id, QuizAttempt.is_completed == True)
    )
    if quiz_id:
        query = query.filter(QuizAttempt.quiz_id == quiz_id)

    attempts = query.order_by(QuizAttempt.submitted_at.desc()).all()
    return [
        QuizAttemptSummary(
            id=a.id,
            quiz_id=a.quiz_id,
            quiz_title=a.quiz.title if a.quiz else "Quiz",
            course_id=a.quiz.course_id if a.quiz else 0,
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
    db: Session,
    course_id: int,
    user: User,
) -> List[QuizDetail]:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    quizzes = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions).joinedload(Question.options))
        .filter(Quiz.course_id == course_id)
        .order_by(Quiz.id.asc())
        .all()
    )

    results = []
    for q in quizzes:
        attempts_count = db.query(func.count(QuizAttempt.id)).filter(QuizAttempt.quiz_id == q.id).scalar() or 0
        results.append(_build_quiz_detail(q, total_attempts=attempts_count))
    return results


def get_quiz_detail_for_instructor(
    db: Session,
    quiz_id: int,
    user: User,
) -> QuizDetail:
    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions).joinedload(Question.options))
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = db.query(Course).filter(Course.id == quiz.course_id).first()
    _check_course_instructor_or_admin(course, user)

    attempts_count = db.query(func.count(QuizAttempt.id)).filter(QuizAttempt.quiz_id == quiz.id).scalar() or 0
    return _build_quiz_detail(quiz, total_attempts=attempts_count)


def create_instructor_quiz(
    db: Session,
    course_id: int,
    quiz_in: QuizCreate,
    user: User,
) -> QuizDetail:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_instructor_or_admin(course, user)

    quiz = Quiz(
        course_id=course_id,
        section_id=quiz_in.section_id,
        lesson_id=quiz_in.lesson_id,
        title=quiz_in.title.strip(),
        description=quiz_in.description.strip() if quiz_in.description else None,
        passing_score=quiz_in.passing_score,
        is_published=quiz_in.is_published,
        time_limit_minutes=quiz_in.time_limit_minutes,
        max_attempts=quiz_in.max_attempts,
    )
    db.add(quiz)
    db.flush()

    for q_data in quiz_in.questions:
        # Validate options: at least 2 options, at least 1 correct
        if len(q_data.options) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question '{q_data.question_text}' must have at least 2 answer options.",
            )
        has_correct = any(opt.is_correct for opt in q_data.options)
        if not has_correct:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question '{q_data.question_text}' must have at least one marked correct answer option.",
            )

        question = Question(
            quiz_id=quiz.id,
            question_text=q_data.question_text.strip(),
            order_index=q_data.order_index,
            points=q_data.points,
        )
        db.add(question)
        db.flush()

        for opt_data in q_data.options:
            option = AnswerOption(
                question_id=question.id,
                option_text=opt_data.option_text.strip(),
                is_correct=opt_data.is_correct,
            )
            db.add(option)

    db.commit()
    db.refresh(quiz)
    return _build_quiz_detail(quiz, total_attempts=0)


def update_instructor_quiz(
    db: Session,
    quiz_id: int,
    quiz_in: QuizUpdate,
    user: User,
) -> QuizDetail:
    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions).joinedload(Question.options))
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = db.query(Course).filter(Course.id == quiz.course_id).first()
    _check_course_instructor_or_admin(course, user)

    if quiz_in.title is not None:
        quiz.title = quiz_in.title.strip()
    if quiz_in.description is not None:
        quiz.description = quiz_in.description.strip() if quiz_in.description else None
    if quiz_in.passing_score is not None:
        quiz.passing_score = quiz_in.passing_score
    if quiz_in.is_published is not None:
        quiz.is_published = quiz_in.is_published
    if quiz_in.time_limit_minutes is not None:
        quiz.time_limit_minutes = quiz_in.time_limit_minutes
    if quiz_in.max_attempts is not None:
        quiz.max_attempts = quiz_in.max_attempts
    if quiz_in.section_id is not None:
        quiz.section_id = quiz_in.section_id if quiz_in.section_id > 0 else None
    if quiz_in.lesson_id is not None:
        quiz.lesson_id = quiz_in.lesson_id if quiz_in.lesson_id > 0 else None

    quiz.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(quiz)

    attempts_count = db.query(func.count(QuizAttempt.id)).filter(QuizAttempt.quiz_id == quiz.id).scalar() or 0
    return _build_quiz_detail(quiz, total_attempts=attempts_count)


def toggle_publish_quiz(
    db: Session,
    quiz_id: int,
    user: User,
) -> QuizDetail:
    quiz = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions).joinedload(Question.options))
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = db.query(Course).filter(Course.id == quiz.course_id).first()
    _check_course_instructor_or_admin(course, user)

    target_state = not quiz.is_published
    if target_state:
        if not quiz.questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot publish a quiz with no questions. Please add at least one question.",
            )
        for q in quiz.questions:
            if not any(opt.is_correct for opt in q.options):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Question '{q.question_text}' has no correct option selected.",
                )

    quiz.is_published = target_state
    quiz.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(quiz)

    attempts_count = db.query(func.count(QuizAttempt.id)).filter(QuizAttempt.quiz_id == quiz.id).scalar() or 0
    return _build_quiz_detail(quiz, total_attempts=attempts_count)


def delete_instructor_quiz(
    db: Session,
    quiz_id: int,
    user: User,
) -> None:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = db.query(Course).filter(Course.id == quiz.course_id).first()
    _check_course_instructor_or_admin(course, user)

    db.delete(quiz)
    db.commit()


def add_quiz_question(
    db: Session,
    quiz_id: int,
    question_in: QuestionCreate,
    user: User,
) -> QuestionDetail:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found.")
    course = db.query(Course).filter(Course.id == quiz.course_id).first()
    _check_course_instructor_or_admin(course, user)

    if len(question_in.options) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question must have at least 2 options.")
    if not any(opt.is_correct for opt in question_in.options):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question must have at least one correct option.")

    question = Question(
        quiz_id=quiz.id,
        question_text=question_in.question_text.strip(),
        order_index=question_in.order_index,
        points=question_in.points,
    )
    db.add(question)
    db.flush()

    for opt_in in question_in.options:
        opt = AnswerOption(
            question_id=question.id,
            option_text=opt_in.option_text.strip(),
            is_correct=opt_in.is_correct,
        )
        db.add(opt)

    db.commit()
    db.refresh(question)

    opts = [
        AnswerOptionDetail(
            id=o.id,
            question_id=o.question_id,
            option_text=o.option_text,
            is_correct=o.is_correct,
        )
        for o in sorted(question.options, key=lambda x: x.id)
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
    db: Session,
    question_id: int,
    question_in: QuestionCreate,
    user: User,
) -> QuestionDetail:
    question = (
        db.query(Question)
        .options(joinedload(Question.quiz))
        .filter(Question.id == question_id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    course = db.query(Course).filter(Course.id == question.quiz.course_id).first()
    _check_course_instructor_or_admin(course, user)

    if len(question_in.options) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question must have at least 2 options.")
    if not any(opt.is_correct for opt in question_in.options):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question must have at least one correct option.")

    question.question_text = question_in.question_text.strip()
    question.order_index = question_in.order_index
    question.points = question_in.points

    # Replace options
    db.query(AnswerOption).filter(AnswerOption.question_id == question.id).delete()
    for opt_in in question_in.options:
        opt = AnswerOption(
            question_id=question.id,
            option_text=opt_in.option_text.strip(),
            is_correct=opt_in.is_correct,
        )
        db.add(opt)

    db.commit()
    db.refresh(question)

    opts = [
        AnswerOptionDetail(
            id=o.id,
            question_id=o.question_id,
            option_text=o.option_text,
            is_correct=o.is_correct,
        )
        for o in sorted(question.options, key=lambda x: x.id)
    ]
    return QuestionDetail(
        id=question.id,
        quiz_id=question.quiz_id,
        question_text=question.question_text,
        order_index=question.order_index,
        points=question.points,
        options=opts,
    )


def delete_quiz_question(
    db: Session,
    question_id: int,
    user: User,
) -> None:
    question = (
        db.query(Question)
        .options(joinedload(Question.quiz))
        .filter(Question.id == question_id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    course = db.query(Course).filter(Course.id == question.quiz.course_id).first()
    _check_course_instructor_or_admin(course, user)

    db.delete(question)
    db.commit()
