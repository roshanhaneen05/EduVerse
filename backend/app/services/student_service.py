from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from pymongo.database import Database

from app.repositories.assignment_repository import (
    list_assignments_by_course_ids,
    list_submissions_for_student_assignments,
)
from app.repositories.course_repository import (
    get_course_by_id,
    get_courses_by_ids,
    get_enrollment_by_student_and_course,
    get_lessons_by_ids,
    list_all_courses,
    list_enrollments,
    list_lesson_progress,
    list_lessons_by_course_ids,
    list_lessons_for_course,
)
from app.repositories.quiz_repository import (
    get_quiz_by_id,
    list_quiz_attempts,
)
from app.repositories.user_repository import get_users_by_ids
from app.schemas.course import CourseResponse
from app.schemas.student import (
    ContinueLearningResponse,
    EnrolledCourseDetail,
    EnhancedStudentDashboardResponse,
    EnhancedStudentDashboardStats,
    StudentAssignmentOverviewItem,
    StudentQuizHistoryItem,
    StudentRecentGrade,
    StudentRecentLessonActivity,
    StudentUpcomingDeadline,
)
from app.services.course_service import enrich_course_response


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime is timezone-aware UTC for safe comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_continue_learning_lesson(
    mongo_db: Database, student_id: int, course_id: int
) -> ContinueLearningResponse:
    """
    Finds the exact next lesson for a student in a course:
    1. If student has an in-progress lesson, continue it.
    2. Otherwise, find the first incomplete lesson by order_index.
    3. If all lessons are completed, return the first lesson for review.
    4. If no lessons exist in the course, return None with reason 'no_lessons'.
    """
    enrollment = get_enrollment_by_student_and_course(mongo_db, student_id, course_id)
    if not enrollment or enrollment.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this course.",
        )

    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    lessons = list_lessons_for_course(mongo_db, course_id)
    if not lessons:
        return ContinueLearningResponse(
            course_id=course.id,
            course_title=course.title,
            next_lesson_id=None,
            next_lesson_title=None,
            is_course_completed=False,
            reason="no_lessons",
        )

    lesson_ids = [l.id for l in lessons]
    progress_records = list_lesson_progress(
        mongo_db, student_id=student_id, lesson_ids=lesson_ids
    )
    completed_ids = {p.lesson_id for p in progress_records if p.is_completed}
    incomplete_lessons = [l for l in lessons if l.id not in completed_ids]

    if not incomplete_lessons:
        first_lesson = lessons[0]
        return ContinueLearningResponse(
            course_id=course.id,
            course_title=course.title,
            next_lesson_id=first_lesson.id,
            next_lesson_title=first_lesson.title,
            is_course_completed=True,
            reason="course_completed_first_lesson",
        )

    in_progress_records = [p for p in progress_records if not p.is_completed]
    if in_progress_records:
        in_progress_records.sort(
            key=lambda p: _ensure_utc(p.updated_at) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        active_lesson_id = in_progress_records[0].lesson_id
        active_lesson = next((l for l in lessons if l.id == active_lesson_id), None)
        if active_lesson:
            return ContinueLearningResponse(
                course_id=course.id,
                course_title=course.title,
                next_lesson_id=active_lesson.id,
                next_lesson_title=active_lesson.title,
                is_course_completed=False,
                reason="latest_progress",
            )

    target = incomplete_lessons[0]
    return ContinueLearningResponse(
        course_id=course.id,
        course_title=course.title,
        next_lesson_id=target.id,
        next_lesson_title=target.title,
        is_course_completed=False,
        reason="first_incomplete",
    )


def list_student_enrolled_courses(
    mongo_db: Database, student_id: int, status_filter: Optional[str] = None
) -> List[EnrolledCourseDetail]:
    """
    Returns the student's enrolled courses with progress breakdown,
    completed/remaining lesson counts, and next lesson action.
    """
    enrollments = list_enrollments(mongo_db, student_id=student_id, sort_desc=True)
    if not enrollments:
        return []

    course_ids = [e.course_id for e in enrollments]
    courses_map = get_courses_by_ids(mongo_db, course_ids)
    instructor_ids = [c.instructor_id for c in courses_map.values()]
    instructors_map = get_users_by_ids(mongo_db, instructor_ids)

    lessons_all = list_lessons_by_course_ids(mongo_db, course_ids)
    lesson_counts: Dict[int, int] = {}
    lesson_to_course: Dict[int, int] = {}
    for lesson in lessons_all:
        lesson_counts[lesson.course_id] = lesson_counts.get(lesson.course_id, 0) + 1
        lesson_to_course[lesson.id] = lesson.course_id

    progress_all = list_lesson_progress(
        mongo_db, student_id=student_id, lesson_ids=list(lesson_to_course.keys())
    )
    completed_counts: Dict[int, int] = {}
    last_accessed_times: Dict[int, datetime] = {}
    for lp in progress_all:
        cid = lesson_to_course.get(lp.lesson_id)
        if cid is None:
            continue
        if lp.is_completed:
            completed_counts[cid] = completed_counts.get(cid, 0) + 1
        ts = _ensure_utc(lp.updated_at)
        if ts and (cid not in last_accessed_times or ts > last_accessed_times[cid]):
            last_accessed_times[cid] = ts

    results: List[EnrolledCourseDetail] = []
    for enr in enrollments:
        c = courses_map.get(enr.course_id)
        if not c:
            continue

        tot_lessons = lesson_counts.get(c.id, 0)
        comp_lessons = completed_counts.get(c.id, 0)
        rem_lessons = max(0, tot_lessons - comp_lessons)
        last_accessed = last_accessed_times.get(c.id) or enr.enrolled_at

        try:
            cont = get_continue_learning_lesson(mongo_db, student_id, c.id)
            next_id = cont.next_lesson_id
            next_title = cont.next_lesson_title
        except HTTPException:
            next_id = None
            next_title = None

        status_val = "completed" if enr.completion_percentage >= 100.0 else "in_progress"
        if status_filter and status_filter.lower() != "all" and status_val != status_filter.lower():
            continue

        instructor = instructors_map.get(c.instructor_id)
        inst_name = instructor.full_name if instructor else "EduVerse Faculty"
        inst_email = instructor.email if instructor else "faculty@eduverse.io"

        results.append(
            EnrolledCourseDetail(
                enrollment_id=enr.id,
                course_id=c.id,
                course_title=c.title,
                course_category=c.category,
                course_difficulty=c.difficulty,
                instructor_name=inst_name,
                instructor_email=inst_email,
                enrolled_at=enr.enrolled_at,
                completion_percentage=enr.completion_percentage,
                status=status_val,
                enrollment_status=enr.status,
                total_lessons=tot_lessons,
                completed_lessons=comp_lessons,
                remaining_lessons=rem_lessons,
                next_lesson_id=next_id,
                next_lesson_title=next_title,
                last_accessed_at=last_accessed,
            )
        )

    return results


def list_student_assignments(
    mongo_db: Database, student_id: int, filter_status: Optional[str] = None
) -> List[StudentAssignmentOverviewItem]:
    """
    Retrieves all assignments across enrolled courses with personal submission status,
    grades, deadlines, and instructor feedback.
    """
    enrollments = list_enrollments(
        mongo_db, student_id=student_id, status_filter="approved"
    )
    enrolled_ids = [e.course_id for e in enrollments]
    if not enrolled_ids:
        return []

    courses_map = get_courses_by_ids(mongo_db, enrolled_ids)
    assignments = list_assignments_by_course_ids(
        mongo_db, enrolled_ids, published_only=True, exclude_archived=True
    )
    if not assignments:
        return []

    # Sort due_date ascending with None last, then id ascending
    assignments.sort(
        key=lambda a: (
            1 if a.due_date is None else 0,
            _ensure_utc(a.due_date) or datetime.max.replace(tzinfo=timezone.utc),
            a.id,
        )
    )

    sub_map = list_submissions_for_student_assignments(
        mongo_db, student_id, [a.id for a in assignments]
    )

    now_utc = datetime.now(timezone.utc)
    items: List[StudentAssignmentOverviewItem] = []

    for a in assignments:
        sub = sub_map.get(a.id)
        if sub:
            status_val = "graded" if sub.grade is not None else "submitted"
            sub_id = sub.id
            sub_at = sub.submitted_at
            is_late = sub.is_late
            grade = sub.grade
            feedback = sub.feedback
        else:
            sub_id = None
            sub_at = None
            is_late = False
            grade = None
            feedback = None
            due_dt = _ensure_utc(a.due_date)
            if a.is_closed or (due_dt and due_dt < now_utc):
                status_val = "past_due"
            else:
                status_val = "not_submitted"

        if filter_status and filter_status != "all":
            if filter_status == "pending" and status_val != "not_submitted":
                continue
            elif filter_status == "submitted" and status_val != "submitted":
                continue
            elif filter_status == "graded" and status_val != "graded":
                continue
            elif filter_status == "past_due" and status_val != "past_due":
                continue

        course = courses_map.get(a.course_id)
        course_title = course.title if course else "Course"

        items.append(
            StudentAssignmentOverviewItem(
                assignment_id=a.id,
                assignment_title=a.title,
                course_id=a.course_id,
                course_title=course_title,
                instructions=a.instructions,
                max_marks=a.max_marks,
                due_date=a.due_date,
                is_closed=a.is_closed,
                submission_id=sub_id,
                submission_status=status_val,
                submitted_at=sub_at,
                is_late=is_late,
                grade=grade,
                feedback=feedback,
                allow_resubmission=a.allow_resubmission,
            )
        )

    return items


def list_student_quiz_history(
    mongo_db: Database, student_id: int
) -> List[StudentQuizHistoryItem]:
    """
    Returns the student's past quiz attempt history across courses,
    displaying score, pass/fail state, and attempt limits, strictly excluding answer keys.
    """
    attempts = list_quiz_attempts(
        mongo_db, student_id=student_id, completed_only=True, sort_desc=True
    )
    if not attempts:
        return []

    attempts.sort(
        key=lambda a: (
            _ensure_utc(a.submitted_at)
            or _ensure_utc(a.started_at)
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )

    quiz_attempt_counts: Dict[int, int] = {}
    quiz_cache: Dict[int, Optional[object]] = {}
    for a in attempts:
        if a.quiz_id is not None:
            quiz_attempt_counts[a.quiz_id] = quiz_attempt_counts.get(a.quiz_id, 0) + 1
            if a.quiz_id not in quiz_cache:
                quiz_cache[a.quiz_id] = get_quiz_by_id(mongo_db, a.quiz_id)

    course_ids = [q.course_id for q in quiz_cache.values() if q is not None]
    courses_map = get_courses_by_ids(mongo_db, course_ids)

    items: List[StudentQuizHistoryItem] = []
    for a in attempts:
        quiz = quiz_cache.get(a.quiz_id) if a.quiz_id is not None else None
        if not quiz:
            continue

        course = courses_map.get(quiz.course_id)
        c_title = course.title if course else "Course"
        rem_attempts = (
            max(0, quiz.max_attempts - quiz_attempt_counts.get(quiz.id, 0))
            if quiz.max_attempts > 0
            else None
        )

        items.append(
            StudentQuizHistoryItem(
                attempt_id=a.id,
                quiz_id=quiz.id,
                quiz_title=quiz.title,
                course_id=quiz.course_id,
                course_title=c_title,
                attempt_number=a.attempt_number,
                score=a.score,
                total_points=a.total_points,
                passing_score=quiz.passing_score,
                passed=a.passed,
                started_at=a.started_at,
                submitted_at=a.submitted_at,
                max_attempts=quiz.max_attempts,
                remaining_attempts=rem_attempts,
            )
        )

    return items


def get_recommended_courses(
    mongo_db: Database, student_id: int, limit: int = 3
) -> List[CourseResponse]:
    """
    Suggests published courses based on the student's enrolled categories.
    Excludes courses the student is already enrolled in.
    """
    enrollments = list_enrollments(mongo_db, student_id=student_id)
    enrolled_ids = {e.course_id for e in enrollments}

    enrolled_categories: set[str] = set()
    if enrolled_ids:
        enrolled_courses = get_courses_by_ids(mongo_db, enrolled_ids)
        enrolled_categories = {c.category for c in enrolled_courses.values() if c.category}

    all_candidates = list_all_courses(
        mongo_db, is_published=True, exclude_ids=list(enrolled_ids) if enrolled_ids else None
    )
    if not all_candidates:
        return []

    matching = [c for c in all_candidates if c.category in enrolled_categories]
    others = [c for c in all_candidates if c.category not in enrolled_categories]
    selected = (matching + others)[:limit]

    instructor_cache = get_users_by_ids(
        mongo_db, [c.instructor_id for c in selected]
    )
    return [
        enrich_course_response(mongo_db, c, instructor_cache=instructor_cache)
        for c in selected
    ]


def get_student_dashboard_data(
    mongo_db: Database, student_id: int
) -> EnhancedStudentDashboardResponse:
    """
    Aggregates comprehensive real student telemetry:
    - Overall learning progress across enrollments
    - Recently accessed lessons with real timestamps
    - Upcoming assignment deadlines
    - Recent grades (quizzes + assignments)
    - Enrolled courses with next lesson actions
    - Real course recommendations
    """
    enrolled_courses = list_student_enrolled_courses(mongo_db, student_id)
    approved_courses = [course for course in enrolled_courses if course.enrollment_status == "approved"]
    total_enrolled = len(enrolled_courses)
    completed_courses = sum(1 for e in approved_courses if e.completion_percentage >= 100.0)
    in_progress_courses = len(approved_courses) - completed_courses

    overall_progress = (
        round(sum(e.completion_percentage for e in approved_courses) / len(approved_courses), 1)
        if approved_courses
        else 0.0
    )

    quiz_attempts = list_quiz_attempts(
        mongo_db, student_id=student_id, completed_only=True, sort_desc=True
    )
    total_quizzes = len(quiz_attempts)
    passed_quizzes = sum(1 for a in quiz_attempts if a.passed)
    avg_quiz_score = (
        round(sum(a.score for a in quiz_attempts) / total_quizzes, 1)
        if total_quizzes > 0
        else 0.0
    )

    assignments = list_student_assignments(mongo_db, student_id)
    total_assign = len(assignments)
    submitted_assign = sum(1 for a in assignments if a.submission_status in ("submitted", "graded"))
    pending_assign = sum(1 for a in assignments if a.submission_status == "not_submitted")

    stats = EnhancedStudentDashboardStats(
        enrolled_courses_count=total_enrolled,
        in_progress_courses_count=in_progress_courses,
        completed_courses_count=completed_courses,
        overall_progress_percentage=overall_progress,
        total_quizzes_taken=total_quizzes,
        quizzes_passed=passed_quizzes,
        average_quiz_score=avg_quiz_score,
        total_assignments_count=total_assign,
        submitted_assignments_count=submitted_assign,
        pending_assignments_count=pending_assign,
    )

    all_progress = list_lesson_progress(mongo_db, student_id=student_id)
    all_progress.sort(
        key=lambda lp: _ensure_utc(lp.updated_at) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    recent_progress = all_progress[:5]
    lessons_map = get_lessons_by_ids(mongo_db, [rp.lesson_id for rp in recent_progress])
    progress_courses_map = get_courses_by_ids(
        mongo_db, [l.course_id for l in lessons_map.values()]
    )

    recent_lessons: List[StudentRecentLessonActivity] = []
    for rp in recent_progress:
        lesson = lessons_map.get(rp.lesson_id)
        if not lesson:
            continue
        course = progress_courses_map.get(lesson.course_id)
        if not course:
            continue
        recent_lessons.append(
            StudentRecentLessonActivity(
                lesson_id=rp.lesson_id,
                lesson_title=lesson.title,
                course_id=lesson.course_id,
                course_title=course.title,
                is_completed=rp.is_completed,
                completed_at=rp.completed_at,
                updated_at=rp.updated_at,
            )
        )

    now_utc = datetime.now(timezone.utc)
    upcoming_deadlines: List[StudentUpcomingDeadline] = []
    for a in assignments:
        due_dt = _ensure_utc(a.due_date)
        if due_dt and due_dt >= now_utc and a.submission_status != "graded":
            upcoming_deadlines.append(
                StudentUpcomingDeadline(
                    assignment_id=a.assignment_id,
                    assignment_title=a.assignment_title,
                    course_id=a.course_id,
                    course_title=a.course_title,
                    due_date=due_dt,
                    max_marks=a.max_marks,
                    is_submitted=(a.submission_status in ("submitted", "graded")),
                    submission_status=a.submission_status,
                    grade=a.grade,
                )
            )
    upcoming_deadlines.sort(key=lambda x: _ensure_utc(x.due_date) or now_utc)
    upcoming_deadlines = upcoming_deadlines[:5]

    recent_grades: List[StudentRecentGrade] = []
    quiz_cache: Dict[int, Optional[object]] = {}
    for qa in quiz_attempts:
        if qa.quiz_id is not None and qa.quiz_id not in quiz_cache:
            quiz_cache[qa.quiz_id] = get_quiz_by_id(mongo_db, qa.quiz_id)
    grade_courses_map = get_courses_by_ids(
        mongo_db, [q.course_id for q in quiz_cache.values() if q is not None]
    )

    for qa in quiz_attempts:
        quiz = quiz_cache.get(qa.quiz_id) if qa.quiz_id is not None else None
        if qa.submitted_at and quiz:
            course = grade_courses_map.get(quiz.course_id)
            c_title = course.title if course else "Course"
            recent_grades.append(
                StudentRecentGrade(
                    assessment_type="quiz",
                    title=quiz.title,
                    course_title=c_title,
                    score_or_grade=qa.score,
                    max_score_or_grade=100.0,
                    percentage=qa.score,
                    feedback=None,
                    date=qa.submitted_at,
                    passed=qa.passed,
                    reference_id=qa.id,
                )
            )

    for a in assignments:
        if a.grade is not None and a.submitted_at:
            pct = round((a.grade / a.max_marks) * 100.0, 1) if a.max_marks > 0 else 0.0
            recent_grades.append(
                StudentRecentGrade(
                    assessment_type="assignment",
                    title=a.assignment_title,
                    course_title=a.course_title,
                    score_or_grade=a.grade,
                    max_score_or_grade=float(a.max_marks),
                    percentage=pct,
                    feedback=a.feedback,
                    date=a.submitted_at,
                    passed=(pct >= 50.0),
                    reference_id=a.assignment_id,
                )
            )

    recent_grades.sort(key=lambda g: _ensure_utc(g.date) or now_utc, reverse=True)
    recent_grades = recent_grades[:5]

    recommended = get_recommended_courses(mongo_db, student_id, limit=3)

    return EnhancedStudentDashboardResponse(
        stats=stats,
        recently_accessed_lessons=recent_lessons,
        upcoming_deadlines=upcoming_deadlines,
        recent_grades=recent_grades,
        recommended_courses=recommended,
        enrolled_courses=enrolled_courses,
    )
