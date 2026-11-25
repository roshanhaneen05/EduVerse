import csv
import io
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from pymongo.database import Database

from app.repositories.assignment_repository import (
    list_assignments_by_course_ids,
    list_submissions_by_assignment_ids,
    list_submissions_for_student_assignments,
)
from app.repositories.course_repository import (
    MongoCourse,
    get_course_by_id,
    get_enrollment_by_student_and_course,
    list_all_courses,
    list_enrollments,
    list_lesson_progress,
    list_lessons_by_course_ids,
    list_lessons_for_course,
    list_sections_for_course,
)
from app.repositories.quiz_repository import (
    count_questions_by_quiz_ids,
    list_quiz_attempts,
    list_quizzes_by_course_ids,
)
from app.repositories.user_repository import (
    MongoUser,
    get_user_by_id,
    get_users_by_ids,
)
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


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _check_course_ownership(course: MongoCourse, user: MongoUser) -> None:
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
    stripped = val_str.lstrip(" ")
    if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val_str}"
    return val_str


def get_instructor_dashboard_analytics(
    mongo_db: Database,
    current_user: MongoUser,
) -> EnhancedInstructorDashboardStats:
    """Aggregate high-level faculty metrics across all instructor-managed courses."""
    managed_courses = list_all_courses(
        mongo_db,
        instructor_id=None if current_user.role == "admin" else current_user.id,
    )
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
    course_map = {c.id: c for c in managed_courses}

    enrollments = list_enrollments(mongo_db, course_ids=course_ids, sort_desc=True)
    total_enrollments = len(enrollments)
    unique_students = len({e.student_id for e in enrollments})
    completed_enrollments = sum(1 for e in enrollments if e.completion_percentage >= 100.0)
    avg_progress = (
        sum(e.completion_percentage for e in enrollments) / total_enrollments
        if total_enrollments > 0
        else 0.0
    )

    assignments = list_assignments_by_course_ids(
        mongo_db, course_ids, exclude_archived=True
    )
    total_assignments = len(assignments)
    assignment_ids = [a.id for a in assignments]
    assignment_to_course = {a.id: a.course_id for a in assignments}

    submissions = list_submissions_by_assignment_ids(mongo_db, assignment_ids)
    total_submissions = len(submissions)
    pending_grading = sum(1 for s in submissions if s.status == "submitted")

    quizzes = list_quizzes_by_course_ids(mongo_db, course_ids)
    total_quizzes = len(quizzes)
    quiz_ids = [q.id for q in quizzes]

    quiz_attempts = list_quiz_attempts(
        mongo_db, quiz_ids=quiz_ids, completed_only=True
    )
    total_quiz_attempts = len(quiz_attempts)
    avg_quiz_score = (
        round(sum(a.score for a in quiz_attempts) / total_quiz_attempts, 1)
        if total_quiz_attempts > 0
        else 0.0
    )

    recent_enrollments_db = enrollments[:5]
    recent_students_map = get_users_by_ids(
        mongo_db, [e.student_id for e in recent_enrollments_db]
    )
    recent_enrollments = []
    for e in recent_enrollments_db:
        student = recent_students_map.get(e.student_id)
        course = course_map.get(e.course_id)
        recent_enrollments.append(
            {
                "enrollment_id": e.id,
                "student_name": student.full_name if student else "Unknown",
                "student_email": student.email if student else "",
                "course_title": course.title if course else "",
                "completion_percentage": e.completion_percentage,
                "enrolled_at": e.enrolled_at.isoformat(),
            }
        )

    lessons_all = list_lessons_by_course_ids(mongo_db, course_ids)
    lessons_by_course: Dict[int, int] = {}
    for l in lessons_all:
        lessons_by_course[l.course_id] = lessons_by_course.get(l.course_id, 0) + 1

    enrollments_by_course: Dict[int, list] = {}
    for e in enrollments:
        enrollments_by_course.setdefault(e.course_id, []).append(e)

    assignments_by_course: Dict[int, int] = {}
    for a in assignments:
        assignments_by_course[a.course_id] = assignments_by_course.get(a.course_id, 0) + 1

    quizzes_by_course: Dict[int, int] = {}
    for q in quizzes:
        quizzes_by_course[q.course_id] = quizzes_by_course.get(q.course_id, 0) + 1

    pending_by_course: Dict[int, int] = {}
    for s in submissions:
        if s.status == "submitted":
            cid = assignment_to_course.get(s.assignment_id)
            if cid is not None:
                pending_by_course[cid] = pending_by_course.get(cid, 0) + 1

    courses_overview = []
    for c in managed_courses:
        c_enrs = enrollments_by_course.get(c.id, [])
        c_students = len(c_enrs)
        c_avg_prog = (
            sum(e.completion_percentage for e in c_enrs) / c_students if c_students > 0 else 0.0
        )
        c_completed = sum(1 for e in c_enrs if e.completion_percentage >= 100.0)
        c_rate = round((c_completed / c_students * 100.0), 1) if c_students > 0 else 0.0

        courses_overview.append(
            CourseOverviewItem(
                course_id=c.id,
                title=c.title,
                category=c.category,
                difficulty=c.difficulty,
                is_published=c.is_published,
                student_count=c_students,
                lesson_count=lessons_by_course.get(c.id, 0),
                assignment_count=assignments_by_course.get(c.id, 0),
                quiz_count=quizzes_by_course.get(c.id, 0),
                average_progress=round(float(c_avg_prog), 1),
                completion_rate=c_rate,
                pending_grading_count=pending_by_course.get(c.id, 0),
            )
        )

    completion_rate = (
        round((completed_enrollments / total_enrollments * 100.0), 1)
        if total_enrollments > 0
        else 0.0
    )

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
    mongo_db: Database,
    course_id: int,
    current_user: MongoUser,
) -> CourseAnalyticsResponse:
    """Retrieve detailed, real-time analytics for a specific course."""
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_ownership(course, current_user)

    enrollments = list_enrollments(mongo_db, course_ids=[course_id])
    total_students = len(enrollments)
    completed_students = sum(1 for e in enrollments if e.completion_percentage >= 100.0)
    avg_completion = (
        round(sum(e.completion_percentage for e in enrollments) / total_students, 1)
        if total_students > 0
        else 0.0
    )
    completion_rate = (
        round((completed_students / total_students) * 100.0, 1) if total_students > 0 else 0.0
    )

    lessons = list_lessons_for_course(mongo_db, course_id)
    total_lessons = len(lessons)

    assignments = sorted(
        list_assignments_by_course_ids(mongo_db, [course_id], exclude_archived=True),
        key=lambda a: a.id,
    )
    total_assignments = len(assignments)
    submissions_all = list_submissions_by_assignment_ids(
        mongo_db, [a.id for a in assignments]
    )
    subs_by_assignment: Dict[int, list] = {}
    for s in submissions_all:
        subs_by_assignment.setdefault(s.assignment_id, []).append(s)

    assignments_breakdown = []
    total_submissions = 0
    pending_grading_total = 0
    graded_submissions_total = 0
    grades_sum = 0.0
    graded_count_for_avg = 0

    for a in assignments:
        subs = subs_by_assignment.get(a.id, [])
        sub_count = len(subs)
        pending = sum(1 for s in subs if s.status == "submitted")
        graded = sum(1 for s in subs if s.status == "graded")

        grades = [s.grade for s in subs if s.grade is not None and a.max_marks > 0]
        avg_grade = (
            round(sum((g / a.max_marks * 100.0) for g in grades) / len(grades), 1)
            if grades
            else None
        )

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

    avg_assignment_grade = (
        round(grades_sum / graded_count_for_avg, 1) if graded_count_for_avg > 0 else None
    )
    max_possible_submissions = total_students * total_assignments
    assignment_submission_rate = (
        round((total_submissions / max_possible_submissions) * 100.0, 1)
        if max_possible_submissions > 0
        else 0.0
    )

    quizzes = sorted(
        list_quizzes_by_course_ids(mongo_db, [course_id]), key=lambda q: q.id
    )
    total_quizzes = len(quizzes)
    question_counts = count_questions_by_quiz_ids(mongo_db, [q.id for q in quizzes])
    attempts_all = list_quiz_attempts(
        mongo_db, quiz_ids=[q.id for q in quizzes], completed_only=True
    )
    attempts_by_quiz: Dict[int, list] = {}
    for att in attempts_all:
        if att.quiz_id is not None:
            attempts_by_quiz.setdefault(att.quiz_id, []).append(att)

    quizzes_breakdown = []
    total_quiz_attempts = 0
    passed_attempts_total = 0
    all_scores = []

    for q in quizzes:
        attempts = attempts_by_quiz.get(q.id, [])
        att_count = len(attempts)
        unique_att = len({a.student_id for a in attempts})
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
                total_questions=question_counts.get(q.id, 0),
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
        round((passed_attempts_total / total_quiz_attempts) * 100.0, 1)
        if total_quiz_attempts > 0
        else 0.0
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
    mongo_db: Database,
    course_id: int,
    current_user: MongoUser,
) -> CourseStudentReportResponse:
    """Generate a course-level student roster report with batch querying."""
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_ownership(course, current_user)

    enrollments = list_enrollments(mongo_db, course_ids=[course_id], sort_desc=True)
    if not enrollments:
        return CourseStudentReportResponse(
            course_id=course.id,
            course_title=course.title,
            total_students=0,
            average_completion_percentage=0.0,
            students=[],
        )

    student_ids = [e.student_id for e in enrollments]
    students_map = get_users_by_ids(mongo_db, student_ids)

    lessons = list_lessons_for_course(mongo_db, course_id)
    total_lessons = len(lessons)
    lesson_ids = [l.id for l in lessons]

    completed_lessons_by_student: Dict[int, int] = {}
    if lesson_ids:
        progress_rows = list_lesson_progress(
            mongo_db,
            student_ids=student_ids,
            lesson_ids=lesson_ids,
            completed_only=True,
        )
        for lp in progress_rows:
            completed_lessons_by_student[lp.student_id] = (
                completed_lessons_by_student.get(lp.student_id, 0) + 1
            )

    assignments = list_assignments_by_course_ids(
        mongo_db, [course_id], exclude_archived=True
    )
    total_assignments = len(assignments)
    assignment_ids = [a.id for a in assignments]
    max_marks_map = {a.id: a.max_marks for a in assignments}

    submissions_by_student: Dict[int, list] = {sid: [] for sid in student_ids}
    if assignment_ids:
        subs = list_submissions_by_assignment_ids(
            mongo_db, assignment_ids, student_ids=student_ids
        )
        for s in subs:
            submissions_by_student.setdefault(s.student_id, []).append(s)

    quizzes = list_quizzes_by_course_ids(mongo_db, [course_id])
    total_quizzes = len(quizzes)
    quiz_ids = [q.id for q in quizzes]

    attempts_by_student: Dict[int, list] = {sid: [] for sid in student_ids}
    if quiz_ids:
        atts = list_quiz_attempts(
            mongo_db,
            quiz_ids=quiz_ids,
            student_ids=student_ids,
            completed_only=True,
        )
        for a in atts:
            attempts_by_student.setdefault(a.student_id, []).append(a)

    students_report = []
    now = datetime.now(timezone.utc)

    for enr in enrollments:
        sid = enr.student_id
        student = students_map.get(sid)
        if not student:
            continue

        c_lessons = completed_lessons_by_student.get(sid, 0)
        s_subs = submissions_by_student.get(sid, [])
        s_attempts = attempts_by_student.get(sid, [])

        submitted_assignments = len(s_subs)
        pending_grading = sum(1 for s in s_subs if s.status == "submitted")

        graded_subs = [
            s for s in s_subs if s.grade is not None and max_marks_map.get(s.assignment_id, 0) > 0
        ]
        avg_assign_grade = (
            round(
                sum((s.grade / max_marks_map[s.assignment_id]) * 100.0 for s in graded_subs)
                / len(graded_subs),
                1,
            )
            if graded_subs
            else None
        )

        quizzes_taken = len({a.quiz_id for a in s_attempts})
        quizzes_passed = len({a.quiz_id for a in s_attempts if a.passed})
        avg_quiz_score = (
            round(sum(a.score for a in s_attempts) / len(s_attempts), 1)
            if s_attempts
            else None
        )

        reasons = []
        enrolled_utc = _ensure_utc(enr.enrolled_at)
        days_enrolled = (now - enrolled_utc).days if enrolled_utc else 0

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
    mongo_db: Database,
    course_id: int,
    student_id: int,
    current_user: MongoUser,
) -> StudentDetailedProgressResponse:
    """Retrieve full curriculum breakdown, assignments, and quiz attempts for a specific student."""
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    _check_course_ownership(course, current_user)

    student = get_user_by_id(mongo_db, student_id)
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    enrollment = get_enrollment_by_student_and_course(mongo_db, student_id, course_id)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student is not enrolled in this course.",
        )

    sections_map = {s.id: s for s in list_sections_for_course(mongo_db, course_id)}
    lessons = list_lessons_for_course(mongo_db, course_id)
    lesson_ids = [l.id for l in lessons]
    progress_map = {}
    if lesson_ids:
        records = list_lesson_progress(
            mongo_db, student_id=student_id, lesson_ids=lesson_ids
        )
        progress_map = {r.lesson_id: r for r in records}

    lessons_detail = []
    completed_lessons_count = 0
    for l in lessons:
        prog = progress_map.get(l.id)
        is_done = bool(prog and prog.is_completed)
        if is_done:
            completed_lessons_count += 1
        section = sections_map.get(l.section_id) if l.section_id is not None else None
        lessons_detail.append(
            StudentLessonProgressDetail(
                lesson_id=l.id,
                title=l.title,
                section_title=section.title if section else None,
                order_index=l.order_index,
                is_completed=is_done,
                completed_at=prog.completed_at if prog else None,
            )
        )

    assignments = sorted(
        list_assignments_by_course_ids(mongo_db, [course_id], exclude_archived=True),
        key=lambda a: a.id,
    )
    assign_ids = [a.id for a in assignments]
    subs_map = (
        list_submissions_for_student_assignments(mongo_db, student_id, assign_ids)
        if assign_ids
        else {}
    )

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

    quizzes = sorted(
        list_quizzes_by_course_ids(mongo_db, [course_id]), key=lambda q: q.id
    )
    quiz_ids = [q.id for q in quizzes]
    quiz_map = {q.id: q for q in quizzes}

    quiz_attempts_detail = []
    quiz_scores = []
    if quiz_ids:
        attempts = list_quiz_attempts(
            mongo_db,
            quiz_ids=quiz_ids,
            student_id=student_id,
            completed_only=True,
            sort_desc=True,
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
    attempted_quizzes_count = len({a.quiz_id for a in quiz_attempts_detail})

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
    mongo_db: Database,
    course_id: int,
    current_user: MongoUser,
) -> str:
    """
    Generate CSV string of the student performance report.
    Applies formula-injection protection on all exported text fields.
    """
    report = get_course_student_report(mongo_db, course_id, current_user)

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

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
