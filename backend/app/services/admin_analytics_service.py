import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.user import User, UserRole
from app.schemas.admin_analytics import (
    AdminAnalyticsActivity,
    AdminAnalyticsDashboard,
    AdminAnalyticsOverview,
    AdminAnalyticsTrends,
    AdminCourseAnalytics,
    AdminInstructorAnalytics,
    AdminStudentAnalytics,
    CourseCategoryMetric,
    CourseMetric,
    InstructorMetric,
    MonthlyAnalyticsPoint,
    StudentMetric,
)


def _validated_range(
    start_date: Optional[date], end_date: Optional[date]
) -> Tuple[datetime, datetime, date, date]:
    if (start_date is None) != (end_date is None):
        raise ValueError("Both start_date and end_date must be provided together.")

    end = end_date or datetime.now(timezone.utc).date()
    start = start_date or (end - timedelta(days=364))
    if start > end:
        raise ValueError("start_date must be on or before end_date.")

    start_at = datetime.combine(start, time.min)
    end_exclusive = datetime.combine(end + timedelta(days=1), time.min)
    return start_at, end_exclusive, start, end


def _range_filter(query, column, start_at: datetime, end_exclusive: datetime):
    return query.filter(column >= start_at, column < end_exclusive)


def _month_keys(start: date, end: date):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield f"{year:04d}-{month:02d}"
        month += 1
        if month == 13:
            year += 1
            month = 1


def build_admin_analytics(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> AdminAnalyticsDashboard:
    start_at, end_exclusive, start, end = _validated_range(start_date, end_date)

    total_students = db.query(func.count(User.id)).filter(
        User.role == UserRole.STUDENT.value
    ).scalar() or 0
    total_instructors = db.query(func.count(User.id)).filter(
        User.role == UserRole.INSTRUCTOR.value
    ).scalar() or 0
    total_active_users = db.query(func.count(User.id)).filter(
        User.is_active.is_(True)
    ).scalar() or 0

    total_courses = db.query(func.count(Course.id)).scalar() or 0
    published_courses = db.query(func.count(Course.id)).filter(
        Course.is_published.is_(True)
    ).scalar() or 0

    period_enrollment_rows = db.query(
        CourseEnrollment.course_id,
        func.count(CourseEnrollment.id).label("enrollment_count"),
        func.sum(case((CourseEnrollment.completion_percentage >= 100, 1), else_=0)).label(
            "completed_count"
        ),
    )
    period_enrollment_rows = _range_filter(
        period_enrollment_rows, CourseEnrollment.enrolled_at, start_at, end_exclusive
    )
    period_enrollment_rows = period_enrollment_rows.group_by(CourseEnrollment.course_id).all()
    course_enrollments = {
        row.course_id: (int(row.enrollment_count or 0), int(row.completed_count or 0))
        for row in period_enrollment_rows
    }
    total_enrollments = sum(count for count, _ in course_enrollments.values())
    completed_enrollments = sum(count for _, count in course_enrollments.values())

    active_students = db.query(func.count(User.id)).filter(
        User.role == UserRole.STUDENT.value, User.is_active.is_(True)
    ).scalar() or 0
    inactive_students = db.query(func.count(User.id)).filter(
        User.role == UserRole.STUDENT.value, User.is_active.is_(False)
    ).scalar() or 0
    new_student_registrations = _range_filter(
        db.query(func.count(User.id)).filter(User.role == UserRole.STUDENT.value),
        User.created_at,
        start_at,
        end_exclusive,
    ).scalar() or 0

    student_enrollment_rows = db.query(
        User.full_name,
        func.count(CourseEnrollment.id).label("enrollment_count"),
        func.coalesce(func.avg(CourseEnrollment.completion_percentage), 0.0).label(
            "average_completion"
        ),
    ).join(CourseEnrollment, CourseEnrollment.student_id == User.id)
    student_enrollment_rows = _range_filter(
        student_enrollment_rows, CourseEnrollment.enrolled_at, start_at, end_exclusive
    )
    student_enrollment_rows = (
        student_enrollment_rows.filter(User.role == UserRole.STUDENT.value)
        .group_by(User.id, User.full_name)
        .all()
    )
    student_metrics = [
        StudentMetric(
            name=row.full_name,
            enrollment_count=int(row.enrollment_count),
            average_completion_rate=round(float(row.average_completion or 0.0), 1),
        )
        for row in student_enrollment_rows
    ]
    top_students = sorted(
        student_metrics, key=lambda item: (item.enrollment_count, item.average_completion_rate), reverse=True
    )[:10]
    highest_completion_students = sorted(
        (item for item in student_metrics if item.enrollment_count),
        key=lambda item: (item.average_completion_rate, item.enrollment_count),
        reverse=True,
    )[:10]
    distinct_enrolled_students = len(student_metrics)

    course_rows = (
        db.query(Course, User.full_name)
        .join(User, User.id == Course.instructor_id)
        .order_by(Course.title)
        .all()
    )
    category_counts = {}
    course_metrics = []
    for course, instructor_name in course_rows:
        category_counts[course.category] = category_counts.get(course.category, 0) + 1
        enrollment_count, completed_count = course_enrollments.get(course.id, (0, 0))
        course_metrics.append(
            CourseMetric(
                course_id=course.id,
                course_name=course.title,
                instructor_name=instructor_name,
                category=course.category,
                is_published=course.is_published,
                enrollment_count=enrollment_count,
                completed_enrollments=completed_count,
                completion_rate=round(completed_count * 100.0 / enrollment_count, 1)
                if enrollment_count
                else 0.0,
            )
        )

    categories = [
        CourseCategoryMetric(category=category, course_count=count)
        for category, count in sorted(category_counts.items())
    ]
    most_popular_courses = sorted(
        course_metrics, key=lambda item: (item.enrollment_count, item.course_name.lower()), reverse=True
    )[:10]
    least_enrolled_courses = sorted(
        course_metrics, key=lambda item: (item.enrollment_count, item.course_name.lower())
    )[:10]
    highest_completion_courses = sorted(
        (item for item in course_metrics if item.enrollment_count),
        key=lambda item: (item.completion_rate, item.enrollment_count),
        reverse=True,
    )[:10]

    instructor_course_rows = db.query(
        Course.instructor_id,
        func.count(Course.id).label("course_count"),
    ).group_by(Course.instructor_id).all()
    instructor_enrollment_rows = db.query(
        Course.instructor_id,
        func.count(CourseEnrollment.id).label("enrollment_count"),
    ).join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
    instructor_enrollment_rows = _range_filter(
        instructor_enrollment_rows,
        CourseEnrollment.enrolled_at,
        start_at,
        end_exclusive,
    ).group_by(Course.instructor_id).all()
    period_course_rows = db.query(
        Course.instructor_id, func.count(Course.id).label("course_count")
    )
    period_course_rows = _range_filter(
        period_course_rows, Course.created_at, start_at, end_exclusive
    ).group_by(Course.instructor_id).all()
    all_instructors = db.query(User).filter(
        User.role == UserRole.INSTRUCTOR.value
    ).order_by(User.full_name).all()
    all_course_counts = {row.instructor_id: int(row.course_count) for row in instructor_course_rows}
    period_enrollment_counts = {
        row.instructor_id: int(row.enrollment_count) for row in instructor_enrollment_rows
    }
    period_course_counts = {row.instructor_id: int(row.course_count) for row in period_course_rows}
    all_enrollment_counts = {
        row.instructor_id: int(row.enrollment_count)
        for row in db.query(
            Course.instructor_id, func.count(CourseEnrollment.id).label("enrollment_count")
        )
        .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
        .group_by(Course.instructor_id)
        .all()
    }
    instructor_metrics = [
        InstructorMetric(
            name=instructor.full_name,
            course_count=all_course_counts.get(instructor.id, 0),
            student_enrollments=all_enrollment_counts.get(instructor.id, 0),
            period_course_creations=period_course_counts.get(instructor.id, 0),
            period_enrollments=period_enrollment_counts.get(instructor.id, 0),
        )
        for instructor in all_instructors
    ]
    instructor_metrics.sort(
        key=lambda item: (item.student_enrollments, item.course_count, item.name.lower()),
        reverse=True,
    )

    student_registration_by_month = dict(
        _range_filter(
            db.query(func.strftime("%Y-%m", User.created_at), func.count(User.id))
            .filter(User.role == UserRole.STUDENT.value),
            User.created_at,
            start_at,
            end_exclusive,
        )
        .group_by(func.strftime("%Y-%m", User.created_at))
        .all()
    )
    enrollment_by_month = dict(
        _range_filter(
            db.query(
                func.strftime("%Y-%m", CourseEnrollment.enrolled_at),
                func.count(CourseEnrollment.id),
            ),
            CourseEnrollment.enrolled_at,
            start_at,
            end_exclusive,
        )
        .group_by(func.strftime("%Y-%m", CourseEnrollment.enrolled_at))
        .all()
    )
    activity_by_month = dict(
        _range_filter(
            db.query(
                func.strftime("%Y-%m", LessonProgress.updated_at),
                func.count(func.distinct(LessonProgress.student_id)),
            )
            .join(Lesson, Lesson.id == LessonProgress.lesson_id),
            LessonProgress.updated_at,
            start_at,
            end_exclusive,
        )
        .group_by(func.strftime("%Y-%m", LessonProgress.updated_at))
        .all()
    )
    trends = AdminAnalyticsTrends(
        monthly=[
            MonthlyAnalyticsPoint(
                month=month,
                student_registrations=int(student_registration_by_month.get(month, 0)),
                enrollments=int(enrollment_by_month.get(month, 0)),
                active_students=int(activity_by_month.get(month, 0)),
            )
            for month in _month_keys(start, end)
        ]
    )

    activities = []

    def add_user_registrations(role: str, activity_type: str, activity_name: str):
        rows = _range_filter(
            db.query(User).filter(User.role == role),
            User.created_at,
            start_at,
            end_exclusive,
        ).order_by(User.created_at.desc()).limit(20).all()
        activities.extend(
            AdminAnalyticsActivity(
                activity_type=activity_type,
                activity_name=activity_name,
                user_name=user.full_name,
                date=user.created_at,
            )
            for user in rows
        )

    add_user_registrations(
        UserRole.STUDENT.value, "student_registered", "Student registered"
    )
    add_user_registrations(
        UserRole.INSTRUCTOR.value, "instructor_registered", "Instructor registered"
    )

    recent_courses = _range_filter(
        db.query(Course, User.full_name)
        .join(User, User.id == Course.instructor_id),
        Course.created_at,
        start_at,
        end_exclusive,
    ).order_by(Course.created_at.desc()).limit(20).all()
    activities.extend(
        AdminAnalyticsActivity(
            activity_type="course_created",
            activity_name=f"Course created: {course.title}",
            user_name=instructor_name,
            date=course.created_at,
        )
        for course, instructor_name in recent_courses
    )

    recent_enrollments = _range_filter(
        db.query(CourseEnrollment, User.full_name, Course.title)
        .join(User, User.id == CourseEnrollment.student_id)
        .join(Course, Course.id == CourseEnrollment.course_id),
        CourseEnrollment.enrolled_at,
        start_at,
        end_exclusive,
    ).order_by(CourseEnrollment.enrolled_at.desc()).limit(20).all()
    activities.extend(
        AdminAnalyticsActivity(
            activity_type="course_enrolled",
            activity_name=f"Enrolled in course: {course_name}",
            user_name=student_name,
            date=enrollment.enrolled_at,
        )
        for enrollment, student_name, course_name in recent_enrollments
    )

    completed_rows = (
        db.query(
            User.full_name,
            Course.title,
            func.max(LessonProgress.completed_at).label("completed_at"),
        )
        .join(CourseEnrollment, CourseEnrollment.student_id == User.id)
        .join(Course, Course.id == CourseEnrollment.course_id)
        .join(Lesson, Lesson.course_id == Course.id)
        .join(
            LessonProgress,
            (LessonProgress.lesson_id == Lesson.id)
            & (LessonProgress.student_id == User.id),
        )
        .filter(
            CourseEnrollment.completion_percentage >= 100,
            LessonProgress.is_completed.is_(True),
            LessonProgress.completed_at.isnot(None),
        )
        .group_by(User.id, User.full_name, Course.id, Course.title)
    )
    completed_rows = _range_filter(
        completed_rows, LessonProgress.completed_at, start_at, end_exclusive
    ).order_by(func.max(LessonProgress.completed_at).desc()).limit(20).all()
    activities.extend(
        AdminAnalyticsActivity(
            activity_type="course_completed",
            activity_name=f"Completed course: {course_name}",
            user_name=student_name,
            date=completed_at,
        )
        for student_name, course_name, completed_at in completed_rows
    )
    activities.sort(key=lambda activity: activity.date, reverse=True)

    return AdminAnalyticsDashboard(
        overview=AdminAnalyticsOverview(
            total_registered_students=int(total_students),
            total_registered_instructors=int(total_instructors),
            total_published_courses=int(published_courses),
            total_enrollments=total_enrollments,
            total_completed_courses=completed_enrollments,
            total_active_users=int(total_active_users),
        ),
        students=AdminStudentAnalytics(
            total_students=int(total_students),
            new_student_registrations=int(new_student_registrations),
            active_students=int(active_students),
            inactive_students=int(inactive_students),
            total_enrollments=total_enrollments,
            average_enrollments_per_student=round(
                total_enrollments / distinct_enrolled_students, 1
            )
            if distinct_enrolled_students
            else 0.0,
            top_students=top_students,
            highest_completion_students=highest_completion_students,
        ),
        courses=AdminCourseAnalytics(
            total_courses=int(total_courses),
            published_courses=int(published_courses),
            unpublished_courses=int(total_courses - published_courses),
            categories=categories,
            courses=course_metrics,
            most_popular_courses=most_popular_courses,
            least_enrolled_courses=least_enrolled_courses,
            highest_completion_courses=highest_completion_courses,
        ),
        instructors=AdminInstructorAnalytics(
            total_instructors=int(total_instructors),
            instructors=instructor_metrics,
            popular_courses=most_popular_courses,
        ),
        trends=trends,
        recent_activities=activities[:30],
    )


def _csv_safe(value) -> str:
    text = "" if value is None else str(value)
    if text.lstrip(" ")[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def analytics_csv_report(data: AdminAnalyticsDashboard) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Section", "Metric", "Value", "Details"])
    overview = data.overview.model_dump()
    for name, value in overview.items():
        writer.writerow(["Overview", name, _csv_safe(value), ""])
    for name, value in data.students.model_dump(exclude={"top_students", "highest_completion_students"}).items():
        writer.writerow(["Students", name, _csv_safe(value), ""])
    for name, value in data.courses.model_dump(exclude={"courses", "categories", "most_popular_courses", "least_enrolled_courses", "highest_completion_courses"}).items():
        writer.writerow(["Courses", name, _csv_safe(value), ""])
    writer.writerow(["Course", "Name", "Enrollments", "Completion rate"])
    for course in data.courses.courses:
        writer.writerow(
            [
                "Course",
                _csv_safe(course.course_name),
                course.enrollment_count,
                course.completion_rate,
            ]
        )
    writer.writerow(["Instructor", "Name", "Courses", "Student enrollments"])
    for instructor in data.instructors.instructors:
        writer.writerow(
            ["Instructor", _csv_safe(instructor.name), instructor.course_count, instructor.student_enrollments]
        )
    for student in data.students.top_students:
        writer.writerow(
            ["Student", _csv_safe(student.name), student.enrollment_count, student.average_completion_rate]
        )
    return output.getvalue().encode("utf-8-sig")


def _pdf_text(value: str) -> str:
    safe = value.encode("ascii", "replace").decode("ascii")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def analytics_pdf_report(data: AdminAnalyticsDashboard) -> bytes:
    lines = [
        "EduVerse - Admin Analytics Report",
        "",
        "Overview",
        f"Registered students: {data.overview.total_registered_students}",
        f"Registered instructors: {data.overview.total_registered_instructors}",
        f"Published courses: {data.overview.total_published_courses}",
        f"Enrollments in selected period: {data.overview.total_enrollments}",
        f"Completed enrollments in selected period: {data.overview.total_completed_courses}",
        f"Active users: {data.overview.total_active_users}",
        "",
        "Student statistics",
        f"Active students: {data.students.active_students}",
        f"Inactive students: {data.students.inactive_students}",
        f"New registrations in selected period: {data.students.new_student_registrations}",
        "",
        "Course statistics (enrollment and completion counts reflect the selected period)",
    ]
    lines.extend(
        f"{course.course_name} ({course.instructor_name or 'Unknown instructor'}) | "
        f"{course.enrollment_count} enrollments | "
        f"{course.completed_enrollments} completions | {course.completion_rate}% completion"
        for course in data.courses.courses
    )
    lines.extend(["", "Instructor statistics"])
    lines.extend(
        f"{instructor.name} | {instructor.course_count} courses | "
        f"{instructor.student_enrollments} enrollments"
        for instructor in data.instructors.instructors
    )
    lines.extend(["", "Top student statistics"])
    lines.extend(
        f"{student.name} | {student.enrollment_count} enrollments | "
        f"{student.average_completion_rate}% average completion"
        for student in data.students.top_students
    )

    pages = [lines[index : index + 48] for index in range(0, len(lines), 48)] or [[]]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    page_ids = []
    for page_index, page_lines in enumerate(pages):
        page_id = 3 + page_index * 2
        content_id = page_id + 1
        page_ids.append(page_id)
        commands = ["BT", "/F1 10 Tf", "50 760 Td", "14 TL"]
        for line in page_lines:
            commands.append(f"({_pdf_text(line[:150])}) Tj")
            commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("ascii")
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 "
                    f"/BaseFont /Helvetica >> >> >> /Contents {content_id} 0 R >>"
                ).encode("ascii"),
                f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
                + stream
                + b"\nendstream",
            ]
        )
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF".encode("ascii")
    )
    return bytes(pdf)
