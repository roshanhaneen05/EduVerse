from datetime import datetime, timezone
import math
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.quiz import Quiz, QuizAttempt
from app.models.user import User
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
    """Ensures datetime is timezone-aware UTC for safe comparisons in SQLite."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_continue_learning_lesson(
    db: Session, student_id: int, course_id: int
) -> ContinueLearningResponse:
    """
    Finds the exact next lesson for a student in a course:
    1. If student has an in-progress lesson, continue it.
    2. Otherwise, find the first incomplete lesson by order_index.
    3. If all lessons are completed, return the first lesson for review.
    4. If no lessons exist in the course, return None with reason 'no_lessons'.
    """
    enrollment = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.course_id == course_id,
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this course.",
        )

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    lessons = (
        db.query(Lesson)
        .filter(Lesson.course_id == course_id)
        .order_by(Lesson.order_index.asc(), Lesson.id.asc())
        .all()
    )

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
    progress_records = (
        db.query(LessonProgress)
        .filter(
            LessonProgress.student_id == student_id,
            LessonProgress.lesson_id.in_(lesson_ids),
        )
        .all()
    )
    completed_ids = {p.lesson_id for p in progress_records if p.is_completed}
    incomplete_lessons = [l for l in lessons if l.id not in completed_ids]

    if not incomplete_lessons:
        # All lessons are completed
        first_lesson = lessons[0]
        return ContinueLearningResponse(
            course_id=course.id,
            course_title=course.title,
            next_lesson_id=first_lesson.id,
            next_lesson_title=first_lesson.title,
            is_course_completed=True,
            reason="course_completed_first_lesson",
        )

    # Check if there is an in-progress lesson that was recently updated
    in_progress_records = [
        p for p in progress_records if not p.is_completed
    ]
    if in_progress_records:
        in_progress_records.sort(key=lambda p: p.updated_at, reverse=True)
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

    # Otherwise, pick the first incomplete lesson by order_index
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
    db: Session, student_id: int, status_filter: Optional[str] = None
) -> List[EnrolledCourseDetail]:
    """
    Returns the student's enrolled courses with progress breakdown,
    completed/remaining lesson counts, and next lesson action.
    """
    enrollments = (
        db.query(CourseEnrollment)
        .options(joinedload(CourseEnrollment.course).joinedload(Course.instructor))
        .filter(CourseEnrollment.student_id == student_id)
        .order_by(CourseEnrollment.enrolled_at.desc())
        .all()
    )

    if not enrollments:
        return []

    course_ids = [e.course_id for e in enrollments]

    # Batch lesson counts per course
    lesson_counts = dict(
        db.query(Lesson.course_id, func.count(Lesson.id))
        .filter(Lesson.course_id.in_(course_ids))
        .group_by(Lesson.course_id)
        .all()
    )

    # Batch completed lesson counts per course for this student
    completed_counts = dict(
        db.query(Lesson.course_id, func.count(LessonProgress.id))
        .join(LessonProgress, Lesson.id == LessonProgress.lesson_id)
        .filter(
            LessonProgress.student_id == student_id,
            Lesson.course_id.in_(course_ids),
            LessonProgress.is_completed == True,
        )
        .group_by(Lesson.course_id)
        .all()
    )

    # Batch last accessed timestamp per course
    last_accessed_times = dict(
        db.query(Lesson.course_id, func.max(LessonProgress.updated_at))
        .join(LessonProgress, Lesson.id == LessonProgress.lesson_id)
        .filter(
            LessonProgress.student_id == student_id,
            Lesson.course_id.in_(course_ids),
        )
        .group_by(Lesson.course_id)
        .all()
    )

    results: List[EnrolledCourseDetail] = []
    for enr in enrollments:
        c = enr.course
        if not c:
            continue

        tot_lessons = lesson_counts.get(c.id, 0)
        comp_lessons = completed_counts.get(c.id, 0)
        rem_lessons = max(0, tot_lessons - comp_lessons)
        last_accessed = last_accessed_times.get(c.id) or enr.enrolled_at

        # Determine next lesson helper
        try:
            cont = get_continue_learning_lesson(db, student_id, c.id)
            next_id = cont.next_lesson_id
            next_title = cont.next_lesson_title
        except HTTPException:
            next_id = None
            next_title = None

        status_val = "completed" if enr.completion_percentage >= 100.0 else "in_progress"

        if status_filter and status_filter.lower() != "all" and status_val != status_filter.lower():
            continue

        inst_name = c.instructor.full_name if c.instructor else "EduVerse Faculty"
        inst_email = c.instructor.email if c.instructor else "faculty@eduverse.io"

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
    db: Session, student_id: int, filter_status: Optional[str] = None
) -> List[StudentAssignmentOverviewItem]:
    """
    Retrieves all assignments across enrolled courses with personal submission status,
    grades, deadlines, and instructor feedback.
    """
    enrolled_courses = (
        db.query(CourseEnrollment.course_id)
        .filter(CourseEnrollment.student_id == student_id)
        .all()
    )
    enrolled_ids = [e[0] for e in enrolled_courses]
    if not enrolled_ids:
        return []

    assignments = (
        db.query(Assignment)
        .options(joinedload(Assignment.course))
        .filter(
            Assignment.course_id.in_(enrolled_ids),
            Assignment.is_published == True,
            Assignment.is_archived == False,
        )
        .order_by(Assignment.due_date.asc().nullslast(), Assignment.id.asc())
        .all()
    )

    if not assignments:
        return []

    assignment_ids = [a.id for a in assignments]
    submissions = (
        db.query(AssignmentSubmission)
        .filter(
            AssignmentSubmission.student_id == student_id,
            AssignmentSubmission.assignment_id.in_(assignment_ids),
        )
        .all()
    )
    sub_map = {s.assignment_id: s for s in submissions}

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

        # Apply optional filter
        if filter_status and filter_status != "all":
            if filter_status == "pending" and status_val != "not_submitted":
                continue
            elif filter_status == "submitted" and status_val != "submitted":
                continue
            elif filter_status == "graded" and status_val != "graded":
                continue
            elif filter_status == "past_due" and status_val != "past_due":
                continue

        course_title = a.course.title if a.course else "Course"

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
    db: Session, student_id: int
) -> List[StudentQuizHistoryItem]:
    """
    Returns the student's past quiz attempt history across courses,
    displaying score, pass/fail state, and attempt limits, strictly excluding answer keys.
    """
    attempts = (
        db.query(QuizAttempt)
        .options(joinedload(QuizAttempt.quiz).joinedload(Quiz.course))
        .filter(
            QuizAttempt.student_id == student_id,
            QuizAttempt.is_completed == True,
        )
        .order_by(QuizAttempt.submitted_at.desc().nullslast(), QuizAttempt.started_at.desc())
        .all()
    )

    if not attempts:
        return []

    # Count total attempts per quiz for remaining attempts calculation
    quiz_attempt_counts: dict[int, int] = {}
    for a in attempts:
        quiz_attempt_counts[a.quiz_id] = quiz_attempt_counts.get(a.quiz_id, 0) + 1

    items: List[StudentQuizHistoryItem] = []
    for a in attempts:
        quiz = a.quiz
        if not quiz:
            continue

        c_title = quiz.course.title if quiz.course else "Course"
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
    db: Session, student_id: int, limit: int = 3
) -> List[CourseResponse]:
    """
    Suggests published courses based on the student's enrolled categories.
    Excludes courses the student is already enrolled in.
    """
    enrolled_courses = (
        db.query(CourseEnrollment.course_id)
        .filter(CourseEnrollment.student_id == student_id)
        .all()
    )
    enrolled_ids = {e[0] for e in enrolled_courses}

    # Extract categories from enrolled courses
    enrolled_categories: set[str] = set()
    if enrolled_ids:
        cat_rows = (
            db.query(Course.category)
            .filter(Course.id.in_(list(enrolled_ids)))
            .all()
        )
        enrolled_categories = {c[0] for c in cat_rows if c[0]}

    # Find candidates
    query = db.query(Course).filter(Course.is_published == True)
    if enrolled_ids:
        query = query.filter(Course.id.not_in(list(enrolled_ids)))

    all_candidates = query.all()
    if not all_candidates:
        return []

    # Sort matching categories first
    matching = [c for c in all_candidates if c.category in enrolled_categories]
    others = [c for c in all_candidates if c.category not in enrolled_categories]

    selected = (matching + others)[:limit]
    return [enrich_course_response(db, c) for c in selected]


def get_student_dashboard_data(
    db: Session, student_id: int
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
    enrolled_courses = list_student_enrolled_courses(db, student_id)
    total_enrolled = len(enrolled_courses)
    completed_courses = sum(1 for e in enrolled_courses if e.completion_percentage >= 100.0)
    in_progress_courses = total_enrolled - completed_courses

    overall_progress = (
        round(sum(e.completion_percentage for e in enrolled_courses) / total_enrolled, 1)
        if total_enrolled > 0
        else 0.0
    )

    # Quiz statistics
    quiz_attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.student_id == student_id, QuizAttempt.is_completed == True)
        .all()
    )
    total_quizzes = len(quiz_attempts)
    passed_quizzes = sum(1 for a in quiz_attempts if a.passed)
    avg_quiz_score = (
        round(sum(a.score for a in quiz_attempts) / total_quizzes, 1)
        if total_quizzes > 0
        else 0.0
    )

    # Assignments overview
    assignments = list_student_assignments(db, student_id)
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

    # 1. Recently accessed lessons (real timestamps from LessonProgress)
    recent_progress = (
        db.query(LessonProgress)
        .options(joinedload(LessonProgress.lesson).joinedload(Lesson.course))
        .filter(LessonProgress.student_id == student_id)
        .order_by(LessonProgress.updated_at.desc())
        .limit(5)
        .all()
    )
    recent_lessons: List[StudentRecentLessonActivity] = []
    for rp in recent_progress:
        if rp.lesson and rp.lesson.course:
            recent_lessons.append(
                StudentRecentLessonActivity(
                    lesson_id=rp.lesson_id,
                    lesson_title=rp.lesson.title,
                    course_id=rp.lesson.course_id,
                    course_title=rp.lesson.course.title,
                    is_completed=rp.is_completed,
                    completed_at=rp.completed_at,
                    updated_at=rp.updated_at,
                )
            )

    # 2. Upcoming assignment deadlines
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

    # 3. Recent grades (quizzes + assignments)
    recent_grades: List[StudentRecentGrade] = []
    # Quiz attempts
    for qa in quiz_attempts:
        if qa.submitted_at and qa.quiz:
            c_title = qa.quiz.course.title if qa.quiz.course else "Course"
            recent_grades.append(
                StudentRecentGrade(
                    assessment_type="quiz",
                    title=qa.quiz.title,
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

    # Graded assignments
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

    # 4. Recommended courses
    recommended = get_recommended_courses(db, student_id, limit=3)

    return EnhancedStudentDashboardResponse(
        stats=stats,
        recently_accessed_lessons=recent_lessons,
        upcoming_deadlines=upcoming_deadlines,
        recent_grades=recent_grades,
        recommended_courses=recommended,
        enrolled_courses=enrolled_courses,
    )
