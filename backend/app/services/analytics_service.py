import csv
import io
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.quiz import Question, Quiz, QuizAttempt
from app.models.section import CourseSection
from app.models.user import User
from app.schemas.analytics import (
    AssignmentAnalyticsItem,
    CourseAnalyticsResponse,
    CourseOverviewItem,
    CourseStudentReportResponse,
    EnhancedInstructorDashboardStats,
    QuizAnalyticsItem,
    StudentAssignmentSubmissionDetail,
    StudentDetailedProgressResponse,
    StudentLessonProgressDetail,
    StudentPerformanceItem,
    StudentQuizAttemptDetail,
)


def _check_course_ownership(course: Course, user: User) -> None:
    """Ensure current user is course instructor or platform administrator."""
    if user.role == "admin":
        return
    if course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view analytics for this course.",
        )


def _sanitize_csv_cell(value: any) -> str:
    """
    Sanitize cell value against CSV / Spreadsheet Formula Injection.
    Prefixes cells starting with =, +, -, @, \\t, \\r with a single quote.
    """
    if value is None:
        return ""
    val_str = str(value)
    if val_str and val_str[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val_str}"
    # Also check if leading spaces precede a formula trigger
    stripped = val_str.lstrip(" ")
    if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val_str}"
    return val_str


def get_instructor_dashboard_analytics(
    db: Session,
    current_user: User,
) -> EnhancedInstructorDashboardStats:
    """Aggregate high-level faculty metrics across all instructor-managed courses."""
    course_query = db.query(Course)
    if current_user.role != "admin":
        course_query = course_query.filter(Course.instructor_id == current_user.id)
    managed_courses = course_query.order_by(Course.created_at.desc()).all()
    course_ids = [c.id for c in managed_courses]

    if not course_ids:
        return EnhancedInstructorDashboardStats(
            total_courses=0,
            published_courses=0,
            total_students_enrolled=0,
            unique_students_count=0,
            total_assignments=0,
            total_assignment_submissions=0,
            pending_grading_count=0,
            total_quizzes=0,
            total_quiz_attempts=0,
            average_quiz_score=0.0,
            average_student_progress=0.0,
            completed_enrollments_count=0,
            course_completion_rate=0.0,
            recent_enrollments=[],
            courses_overview=[],
        )

    published_courses = sum(1 for c in managed_courses if c.is_published)

    # Enrollments & students
    enrollments_query = db.query(CourseEnrollment).filter(CourseEnrollment.course_id.in_(course_ids))
    total_enrollments = enrollments_query.count()
    unique_students = (
        db.query(func.count(func.distinct(CourseEnrollment.student_id)))
        .filter(CourseEnrollment.course_id.in_(course_ids))
        .scalar()
        or 0
    )
    completed_enrollments = (
        db.query(func.count(CourseEnrollment.id))
        .filter(CourseEnrollment.course_id.in_(course_ids), CourseEnrollment.completion_percentage >= 100.0)
        .scalar()
        or 0
    )
    avg_progress = (
        db.query(func.coalesce(func.avg(CourseEnrollment.completion_percentage), 0.0))
        .filter(CourseEnrollment.course_id.in_(course_ids))
        .scalar()
        or 0.0
    )

    # Assignments & submissions
    assignments = db.query(Assignment).filter(Assignment.course_id.in_(course_ids), Assignment.is_archived == False).all()
    total_assignments = len(assignments)
    assignment_ids = [a.id for a in assignments]

    total_submissions = 0
    pending_grading = 0
    if assignment_ids:
        total_submissions = (
            db.query(func.count(AssignmentSubmission.id))
            .filter(AssignmentSubmission.assignment_id.in_(assignment_ids))
            .scalar()
            or 0
        )
        pending_grading = (
            db.query(func.count(AssignmentSubmission.id))
            .filter(
                AssignmentSubmission.assignment_id.in_(assignment_ids),
                AssignmentSubmission.status == "submitted",
            )
            .scalar()
            or 0
        )

    # Quizzes & attempts
    quizzes = db.query(Quiz).filter(Quiz.course_id.in_(course_ids)).all()
    total_quizzes = len(quizzes)
    quiz_ids = [q.id for q in quizzes]

    total_quiz_attempts = 0
    avg_quiz_score = 0.0
    if quiz_ids:
        attempts_stats = (
            db.query(
                func.count(QuizAttempt.id),
                func.coalesce(func.avg(QuizAttempt.score), 0.0),
            )
            .filter(QuizAttempt.quiz_id.in_(quiz_ids), QuizAttempt.is_completed == True)
            .first()
        )
        if attempts_stats:
            total_quiz_attempts = attempts_stats[0] or 0
            avg_quiz_score = round(float(attempts_stats[1] or 0.0), 1)

    # Recent enrollments
    recent_enrollments_db = (
        db.query(CourseEnrollment)
        .options(joinedload(CourseEnrollment.student), joinedload(CourseEnrollment.course))
        .filter(CourseEnrollment.course_id.in_(course_ids))
        .order_by(CourseEnrollment.enrolled_at.desc())
        .limit(5)
        .all()
    )
    recent_enrollments = [
        {
            "enrollment_id": e.id,
            "student_name": e.student.full_name if e.student else "Unknown",
            "student_email": e.student.email if e.student else "",
            "course_title": e.course.title if e.course else "",
            "completion_percentage": e.completion_percentage,
            "enrolled_at": e.enrolled_at.isoformat(),
        }
        for e in recent_enrollments_db
    ]

    # Per-course overview
    courses_overview = []
    for c in managed_courses:
        c_students = db.query(func.count(CourseEnrollment.id)).filter(CourseEnrollment.course_id == c.id).scalar() or 0
        c_lessons = db.query(func.count(Lesson.id)).filter(Lesson.course_id == c.id).scalar() or 0
        c_assignments = db.query(func.count(Assignment.id)).filter(Assignment.course_id == c.id, Assignment.is_archived == False).scalar() or 0
        c_quizzes = db.query(func.count(Quiz.id)).filter(Quiz.course_id == c.id).scalar() or 0
        c_avg_prog = db.query(func.coalesce(func.avg(CourseEnrollment.completion_percentage), 0.0)).filter(CourseEnrollment.course_id == c.id).scalar() or 0.0
        c_completed = db.query(func.count(CourseEnrollment.id)).filter(CourseEnrollment.course_id == c.id, CourseEnrollment.completion_percentage >= 100.0).scalar() or 0
        c_pending = (
            db.query(func.count(AssignmentSubmission.id))
            .join(Assignment, AssignmentSubmission.assignment_id == Assignment.id)
            .filter(Assignment.course_id == c.id, AssignmentSubmission.status == "submitted")
            .scalar()
            or 0
        )
        c_rate = round((c_completed / c_students * 100.0), 1) if c_students > 0 else 0.0

        courses_overview.append(
            CourseOverviewItem(
                course_id=c.id,
                title=c.title,
                category=c.category,
                difficulty=c.difficulty,
                is_published=c.is_published,
                student_count=c_students,
                lesson_count=c_lessons,
                assignment_count=c_assignments,
                quiz_count=c_quizzes,
                average_progress=round(float(c_avg_prog), 1),
                completion_rate=c_rate,
                pending_grading_count=c_pending,
            )
        )

    completion_rate = round((completed_enrollments / total_enrollments * 100.0), 1) if total_enrollments > 0 else 0.0

    return EnhancedInstructorDashboardStats(
        total_courses=len(managed_courses),
        published_courses=published_courses,
        total_students_enrolled=total_enrollments,
        unique_students_count=unique_students,
        total_assignments=total_assignments,
        total_assignment_submissions=total_submissions,
        pending_grading_count=pending_grading,
        total_quizzes=total_quizzes,
        total_quiz_attempts=total_quiz_attempts,
        average_quiz_score=avg_quiz_score,
        average_student_progress=round(float(avg_progress), 1),
        completed_enrollments_count=completed_enrollments,
        course_completion_rate=completion_rate,
        recent_enrollments=recent_enrollments,
        courses_overview=courses_overview,
    )


def get_course_analytics(
    db: Session,
    course_id: int,
    current_user: User,
) -> CourseAnalyticsResponse:
    """Retrieve detailed, real-time analytics for a specific course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_ownership(course, current_user)

    # 1. Students & completion metrics
    enrollments = db.query(CourseEnrollment).filter(CourseEnrollment.course_id == course_id).all()
    total_students = len(enrollments)
    completed_students = sum(1 for e in enrollments if e.completion_percentage >= 100.0)
    avg_completion = round(sum(e.completion_percentage for e in enrollments) / total_students, 1) if total_students > 0 else 0.0
    completion_rate = round((completed_students / total_students) * 100.0, 1) if total_students > 0 else 0.0

    # 2. Lessons
    total_lessons = db.query(func.count(Lesson.id)).filter(Lesson.course_id == course_id).scalar() or 0

    # 3. Assignments breakdown
    assignments = (
        db.query(Assignment)
        .filter(Assignment.course_id == course_id, Assignment.is_archived == False)
        .order_by(Assignment.id.asc())
        .all()
    )
    total_assignments = len(assignments)

    assignments_breakdown = []
    total_submissions = 0
    pending_grading_total = 0
    graded_submissions_total = 0
    grades_sum = 0.0
    graded_count_for_avg = 0

    for a in assignments:
        subs = db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == a.id).all()
        sub_count = len(subs)
        pending = sum(1 for s in subs if s.status == "submitted")
        graded = sum(1 for s in subs if s.status == "graded")

        grades = [s.grade for s in subs if s.grade is not None and a.max_marks > 0]
        avg_grade = round(sum((g / a.max_marks * 100.0) for g in grades) / len(grades), 1) if grades else None

        total_submissions += sub_count
        pending_grading_total += pending
        graded_submissions_total += graded
        if avg_grade is not None:
            grades_sum += avg_grade
            graded_count_for_avg += 1

        assignments_breakdown.append(
            AssignmentAnalyticsItem(
                assignment_id=a.id,
                title=a.title,
                max_marks=a.max_marks,
                due_date=a.due_date,
                is_published=a.is_published,
                total_submissions=sub_count,
                pending_grading=pending,
                graded_count=graded,
                average_grade=avg_grade,
            )
        )

    avg_assignment_grade = round(grades_sum / graded_count_for_avg, 1) if graded_count_for_avg > 0 else None
    max_possible_submissions = total_students * total_assignments
    assignment_submission_rate = (
        round((total_submissions / max_possible_submissions) * 100.0, 1) if max_possible_submissions > 0 else 0.0
    )

    # 4. Quizzes breakdown
    quizzes = (
        db.query(Quiz)
        .options(joinedload(Quiz.questions))
        .filter(Quiz.course_id == course_id)
        .order_by(Quiz.id.asc())
        .all()
    )
    total_quizzes = len(quizzes)

    quizzes_breakdown = []
    total_quiz_attempts = 0
    passed_attempts_total = 0
    all_scores = []

    for q in quizzes:
        attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == q.id, QuizAttempt.is_completed == True).all()
        att_count = len(attempts)
        unique_att = len(set(a.student_id for a in attempts))
        passes = sum(1 for a in attempts if a.passed)
        fails = att_count - passes
        pass_rate = round((passes / att_count) * 100.0, 1) if att_count > 0 else 0.0
        avg_score = round(sum(a.score for a in attempts) / att_count, 1) if att_count > 0 else 0.0

        total_quiz_attempts += att_count
        passed_attempts_total += passes
        all_scores.extend([a.score for a in attempts])

        quizzes_breakdown.append(
            QuizAnalyticsItem(
                quiz_id=q.id,
                quiz_title=q.title,
                passing_score=q.passing_score,
                total_questions=len(q.questions) if q.questions else 0,
                time_limit_minutes=q.time_limit_minutes,
                is_published=q.is_published,
                total_attempts=att_count,
                unique_students_attempted=unique_att,
                pass_count=passes,
                fail_count=fails,
                pass_rate=pass_rate,
                average_score=avg_score,
            )
        )

    avg_quiz_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
    overall_quiz_pass_rate = (
        round((passed_attempts_total / total_quiz_attempts) * 100.0, 1) if total_quiz_attempts > 0 else 0.0
    )

    return CourseAnalyticsResponse(
        course_id=course.id,
        course_title=course.title,
        category=course.category,
        difficulty=course.difficulty,
        is_published=course.is_published,
        total_students=total_students,
        total_lessons=total_lessons,
        average_completion_percentage=avg_completion,
        completed_students_count=completed_students,
        course_completion_rate=completion_rate,
        total_assignments=total_assignments,
        total_assignment_submissions=total_submissions,
        pending_grading_count=pending_grading_total,
        graded_submissions_count=graded_submissions_total,
        assignment_submission_rate=assignment_submission_rate,
        average_assignment_grade=avg_assignment_grade,
        total_quizzes=total_quizzes,
        total_quiz_attempts=total_quiz_attempts,
        average_quiz_score=avg_quiz_score,
        quiz_pass_rate=overall_quiz_pass_rate,
        quizzes_breakdown=quizzes_breakdown,
        assignments_breakdown=assignments_breakdown,
    )


def get_course_student_report(
    db: Session,
    course_id: int,
    current_user: User,
) -> CourseStudentReportResponse:
    """Generate a course-level student roster report with batch querying."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_ownership(course, current_user)

    enrollments = (
        db.query(CourseEnrollment)
        .options(joinedload(CourseEnrollment.student))
        .filter(CourseEnrollment.course_id == course_id)
        .order_by(CourseEnrollment.enrolled_at.desc())
        .all()
    )

    if not enrollments:
        return CourseStudentReportResponse(
            course_id=course.id,
            course_title=course.title,
            total_students=0,
            average_completion_percentage=0.0,
            students=[],
        )

    student_ids = [e.student_id for e in enrollments]

    # Lessons
    lessons = db.query(Lesson).filter(Lesson.course_id == course_id).all()
    total_lessons = len(lessons)
    lesson_ids = [l.id for l in lessons]

    completed_lessons_by_student: Dict[int, int] = {}
    if lesson_ids:
        progress_counts = (
            db.query(LessonProgress.student_id, func.count(LessonProgress.id))
            .filter(
                LessonProgress.lesson_id.in_(lesson_ids),
                LessonProgress.student_id.in_(student_ids),
                LessonProgress.is_completed == True,
            )
            .group_by(LessonProgress.student_id)
            .all()
        )
        completed_lessons_by_student = {p[0]: p[1] for p in progress_counts}

    # Assignments
    assignments = db.query(Assignment).filter(Assignment.course_id == course_id, Assignment.is_archived == False).all()
    total_assignments = len(assignments)
    assignment_ids = [a.id for a in assignments]
    max_marks_map = {a.id: a.max_marks for a in assignments}

    submissions_by_student: Dict[int, List[AssignmentSubmission]] = {sid: [] for sid in student_ids}
    if assignment_ids:
        subs = (
            db.query(AssignmentSubmission)
            .filter(
                AssignmentSubmission.assignment_id.in_(assignment_ids),
                AssignmentSubmission.student_id.in_(student_ids),
            )
            .all()
        )
        for s in subs:
            submissions_by_student.setdefault(s.student_id, []).append(s)

    # Quizzes
    quizzes = db.query(Quiz).filter(Quiz.course_id == course_id).all()
    total_quizzes = len(quizzes)
    quiz_ids = [q.id for q in quizzes]

    attempts_by_student: Dict[int, List[QuizAttempt]] = {sid: [] for sid in student_ids}
    if quiz_ids:
        atts = (
            db.query(QuizAttempt)
            .filter(
                QuizAttempt.quiz_id.in_(quiz_ids),
                QuizAttempt.student_id.in_(student_ids),
                QuizAttempt.is_completed == True,
            )
            .all()
        )
        for a in atts:
            attempts_by_student.setdefault(a.student_id, []).append(a)

    students_report = []
    now = datetime.now(timezone.utc)

    for enr in enrollments:
        sid = enr.student_id
        student = enr.student
        if not student:
            continue

        c_lessons = completed_lessons_by_student.get(sid, 0)
        s_subs = submissions_by_student.get(sid, [])
        s_attempts = attempts_by_student.get(sid, [])

        submitted_assignments = len(s_subs)
        pending_grading = sum(1 for s in s_subs if s.status == "submitted")

        # Average assignment percentage
        graded_subs = [s for s in s_subs if s.grade is not None and max_marks_map.get(s.assignment_id, 0) > 0]
        avg_assign_grade = (
            round(
                sum((s.grade / max_marks_map[s.assignment_id]) * 100.0 for s in graded_subs) / len(graded_subs), 1
            )
            if graded_subs
            else None
        )

        quizzes_taken = len(set(a.quiz_id for a in s_attempts))
        quizzes_passed = len(set(a.quiz_id for a in s_attempts if a.passed))
        avg_quiz_score = (
            round(sum(a.score for a in s_attempts) / len(s_attempts), 1) if s_attempts else None
        )

        # Clear, objective criteria for assistance indicators
        reasons = []
        days_enrolled = (
            (now - enr.enrolled_at.replace(tzinfo=timezone.utc if enr.enrolled_at.tzinfo is None else enr.enrolled_at.tzinfo)).days
            if enr.enrolled_at
            else 0
        )

        if total_quizzes > 0 and s_attempts and quizzes_passed == 0:
            reasons.append("Failed all attempted assessments")

        if total_assignments > 0 and days_enrolled > 7 and submitted_assignments == 0:
            reasons.append("No assignments submitted after 7+ days")

        if total_lessons > 0 and days_enrolled > 14 and enr.completion_percentage < 20.0:
            reasons.append(f"Low progress ({enr.completion_percentage}% after {days_enrolled} days)")

        if enr.completion_percentage >= 100.0:
            status_label = "Completed"
        elif reasons:
            status_label = "Needs Attention"
        else:
            status_label = "In Progress"

        students_report.append(
            StudentPerformanceItem(
                student_id=student.id,
                full_name=student.full_name,
                email=student.email,
                enrolled_at=enr.enrolled_at,
                completion_percentage=enr.completion_percentage,
                completed_lessons_count=c_lessons,
                total_lessons_count=total_lessons,
                assignments_submitted_count=submitted_assignments,
                total_assignments_count=total_assignments,
                pending_grading_count=pending_grading,
                average_assignment_grade=avg_assign_grade,
                quizzes_taken_count=quizzes_taken,
                total_quizzes_count=total_quizzes,
                quizzes_passed_count=quizzes_passed,
                average_quiz_score=avg_quiz_score,
                status=status_label,
                assistance_reasons=reasons,
            )
        )

    avg_course_comp = round(sum(e.completion_percentage for e in enrollments) / len(enrollments), 1)

    return CourseStudentReportResponse(
        course_id=course.id,
        course_title=course.title,
        total_students=len(students_report),
        average_completion_percentage=avg_course_comp,
        students=students_report,
    )


def get_student_detailed_progress(
    db: Session,
    course_id: int,
    student_id: int,
    current_user: User,
) -> StudentDetailedProgressResponse:
    """Retrieve full curriculum breakdown, assignments, and quiz attempts for a specific student."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_ownership(course, current_user)

    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    enrollment = (
        db.query(CourseEnrollment)
        .filter(CourseEnrollment.course_id == course_id, CourseEnrollment.student_id == student_id)
        .first()
    )
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student is not enrolled in this course.",
        )

    # 1. Lessons progress
    lessons = (
        db.query(Lesson)
        .options(joinedload(Lesson.section))
        .filter(Lesson.course_id == course_id)
        .order_by(Lesson.order_index.asc())
        .all()
    )
    lesson_ids = [l.id for l in lessons]
    progress_map = {}
    if lesson_ids:
        records = (
            db.query(LessonProgress)
            .filter(LessonProgress.student_id == student_id, LessonProgress.lesson_id.in_(lesson_ids))
            .all()
        )
        progress_map = {r.lesson_id: r for r in records}

    lessons_detail = []
    completed_lessons_count = 0
    for l in lessons:
        prog = progress_map.get(l.id)
        is_done = bool(prog and prog.is_completed)
        if is_done:
            completed_lessons_count += 1
        lessons_detail.append(
            StudentLessonProgressDetail(
                lesson_id=l.id,
                title=l.title,
                section_title=l.section.title if l.section else None,
                order_index=l.order_index,
                is_completed=is_done,
                completed_at=prog.completed_at if prog else None,
            )
        )

    # 2. Assignments
    assignments = (
        db.query(Assignment)
        .filter(Assignment.course_id == course_id, Assignment.is_archived == False)
        .order_by(Assignment.id.asc())
        .all()
    )
    assign_ids = [a.id for a in assignments]
    subs_map = {}
    if assign_ids:
        subs = (
            db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.assignment_id.in_(assign_ids), AssignmentSubmission.student_id == student_id)
            .all()
        )
        subs_map = {s.assignment_id: s for s in subs}

    assignments_detail = []
    submitted_count = 0
    grades = []
    for a in assignments:
        sub = subs_map.get(a.id)
        if sub:
            submitted_count += 1
            if sub.grade is not None and a.max_marks > 0:
                grades.append((sub.grade / a.max_marks) * 100.0)

        assignments_detail.append(
            StudentAssignmentSubmissionDetail(
                assignment_id=a.id,
                title=a.title,
                max_marks=a.max_marks,
                due_date=a.due_date,
                status=sub.status if sub else "not_submitted",
                is_submitted=sub is not None,
                submitted_at=sub.submitted_at if sub else None,
                grade=sub.grade if sub else None,
                feedback=sub.feedback if sub else None,
                is_late=sub.is_late if sub else False,
            )
        )

    avg_assign_grade = round(sum(grades) / len(grades), 1) if grades else None

    # 3. Quizzes
    quizzes = db.query(Quiz).filter(Quiz.course_id == course_id).order_by(Quiz.id.asc()).all()
    quiz_ids = [q.id for q in quizzes]
    quiz_map = {q.id: q for q in quizzes}

    quiz_attempts_detail = []
    quiz_scores = []
    if quiz_ids:
        attempts = (
            db.query(QuizAttempt)
            .filter(
                QuizAttempt.quiz_id.in_(quiz_ids),
                QuizAttempt.student_id == student_id,
                QuizAttempt.is_completed == True,
            )
            .order_by(QuizAttempt.submitted_at.desc())
            .all()
        )
        for att in attempts:
            q = quiz_map.get(att.quiz_id)
            quiz_scores.append(att.score)
            quiz_attempts_detail.append(
                StudentQuizAttemptDetail(
                    quiz_id=att.quiz_id,
                    title=q.title if q else "Quiz",
                    passing_score=q.passing_score if q else 70,
                    attempt_id=att.id,
                    attempt_number=att.attempt_number,
                    score=att.score,
                    passed=att.passed,
                    submitted_at=att.submitted_at,
                )
            )

    avg_quiz_score = round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else None
    attempted_quizzes_count = len(set(a.quiz_id for a in quiz_attempts_detail))

    # Reasons & status
    reasons = []
    if len(quizzes) > 0 and quiz_attempts_detail and not any(a.passed for a in quiz_attempts_detail):
        reasons.append("Failed all attempted assessments")
    if len(assignments) > 0 and submitted_count == 0:
        reasons.append("No course assignments submitted")
    if len(lessons) > 0 and enrollment.completion_percentage < 25.0:
        reasons.append(f"Low completion percentage ({enrollment.completion_percentage}%)")

    if enrollment.completion_percentage >= 100.0:
        status_label = "Completed"
    elif reasons:
        status_label = "Needs Attention"
    else:
        status_label = "In Progress"

    return StudentDetailedProgressResponse(
        student_id=student.id,
        full_name=student.full_name,
        email=student.email,
        course_id=course.id,
        course_title=course.title,
        enrolled_at=enrollment.enrolled_at,
        completion_percentage=enrollment.completion_percentage,
        total_lessons=len(lessons),
        completed_lessons=completed_lessons_count,
        total_assignments=len(assignments),
        submitted_assignments=submitted_count,
        average_assignment_grade=avg_assign_grade,
        total_quizzes=len(quizzes),
        attempted_quizzes=attempted_quizzes_count,
        average_quiz_score=avg_quiz_score,
        status=status_label,
        assistance_reasons=reasons,
        lessons_progress=lessons_detail,
        assignment_submissions=assignments_detail,
        quiz_attempts=quiz_attempts_detail,
    )


def generate_student_report_csv(
    db: Session,
    course_id: int,
    current_user: User,
) -> str:
    """
    Generate CSV string of the student performance report.
    Applies formula-injection protection on all exported text fields.
    """
    report = get_course_student_report(db, course_id, current_user)

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header
    headers = [
        "Student ID",
        "Student Name",
        "Email",
        "Enrolled Date",
        "Progress (%)",
        "Completed Lessons",
        "Total Lessons",
        "Assignments Submitted",
        "Total Assignments",
        "Avg Assignment Grade (%)",
        "Quizzes Taken",
        "Quizzes Passed",
        "Avg Quiz Score (%)",
        "Status",
        "Assistance Notes",
    ]
    writer.writerow([_sanitize_csv_cell(h) for h in headers])

    for s in report.students:
        enrolled_date_str = s.enrolled_at.strftime("%Y-%m-%d %H:%M") if s.enrolled_at else ""
        avg_assign_str = f"{s.average_assignment_grade}%" if s.average_assignment_grade is not None else "N/A"
        avg_quiz_str = f"{s.average_quiz_score}%" if s.average_quiz_score is not None else "N/A"
        notes_str = "; ".join(s.assistance_reasons) if s.assistance_reasons else "None"

        row = [
            _sanitize_csv_cell(s.student_id),
            _sanitize_csv_cell(s.full_name),
            _sanitize_csv_cell(s.email),
            _sanitize_csv_cell(enrolled_date_str),
            _sanitize_csv_cell(s.completion_percentage),
            _sanitize_csv_cell(s.completed_lessons_count),
            _sanitize_csv_cell(s.total_lessons_count),
            _sanitize_csv_cell(s.assignments_submitted_count),
            _sanitize_csv_cell(s.total_assignments_count),
            _sanitize_csv_cell(avg_assign_str),
            _sanitize_csv_cell(s.quizzes_taken_count),
            _sanitize_csv_cell(s.quizzes_passed_count),
            _sanitize_csv_cell(avg_quiz_str),
            _sanitize_csv_cell(s.status),
            _sanitize_csv_cell(notes_str),
        ]
        writer.writerow(row)

    return output.getvalue()
