import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from pymongo.database import Database

from app.models.user import UserRole
from app.repositories.course_repository import (
    list_all_courses,
    list_enrollments,
    list_lesson_progress,
    list_lessons_by_course_ids,
)
from app.repositories.user_repository import list_all_users
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


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _validated_range(
    start_date: Optional[date], end_date: Optional[date]
) -> Tuple[datetime, datetime, date, date]:
    if (start_date is None) != (end_date is None):
        raise ValueError("Both start_date and end_date must be provided together.")

    end = end_date or datetime.now(timezone.utc).date()
    start = start_date or (end - timedelta(days=364))
    if start > end:
        raise ValueError("start_date must be on or before end_date.")

    start_at = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_exclusive = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_at, end_exclusive, start, end


def _in_range(dt: Optional[datetime], start_at: datetime, end_exclusive: datetime) -> bool:
    utc_dt = _ensure_utc(dt)
    if utc_dt is None:
        return False
    return start_at <= utc_dt < end_exclusive


def _month_keys(start: date, end: date):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield f"{year:04d}-{month:02d}"
        month += 1
        if month == 13:
            year += 1
            month = 1


def build_admin_analytics(
    mongo_db: Database,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> AdminAnalyticsDashboard:
    start_at, end_exclusive, start, end = _validated_range(start_date, end_date)

    users = list_all_users(mongo_db)
    users_by_id = {u.id: u for u in users}
    students = [u for u in users if u.role == UserRole.STUDENT.value]
    instructors = [u for u in users if u.role == UserRole.INSTRUCTOR.value]

    total_students = len(students)
    total_instructors = len(instructors)
    total_active_users = sum(1 for u in users if u.is_active)

    courses = list_all_courses(mongo_db)
    courses_by_id = {c.id: c for c in courses}
    total_courses = len(courses)
    published_courses = sum(1 for c in courses if c.is_published)

    all_enrollments = list_enrollments(mongo_db)
    period_enrollments = [
        e for e in all_enrollments if _in_range(e.enrolled_at, start_at, end_exclusive)
    ]

    course_enrollments: Dict[int, List[int]] = {}
    for e in period_enrollments:
        entry = course_enrollments.setdefault(e.course_id, [0, 0])
        entry[0] += 1
        if e.completion_percentage >= 100:
            entry[1] += 1
    total_enrollments = len(period_enrollments)
    completed_enrollments = sum(1 for e in period_enrollments if e.completion_percentage >= 100)

    active_students = sum(1 for s in students if s.is_active)
    inactive_students = sum(1 for s in students if not s.is_active)
    new_student_registrations = sum(
        1 for s in students if _in_range(s.created_at, start_at, end_exclusive)
    )

    student_enr_buckets: Dict[int, List[float]] = {}
    for e in period_enrollments:
        student_user = users_by_id.get(e.student_id)
        if student_user and student_user.role == UserRole.STUDENT.value:
            student_enr_buckets.setdefault(e.student_id, []).append(
                float(e.completion_percentage)
            )
    student_metrics = [
        StudentMetric(
            name=users_by_id[sid].full_name,
            enrollment_count=len(pcts),
            average_completion_rate=round(sum(pcts) / len(pcts), 1),
        )
        for sid, pcts in student_enr_buckets.items()
    ]
    top_students = sorted(
        student_metrics,
        key=lambda item: (item.enrollment_count, item.average_completion_rate),
        reverse=True,
    )[:10]
    highest_completion_students = sorted(
        (item for item in student_metrics if item.enrollment_count),
        key=lambda item: (item.average_completion_rate, item.enrollment_count),
        reverse=True,
    )[:10]
    distinct_enrolled_students = len(student_metrics)

    sorted_courses = sorted(courses, key=lambda c: c.title)
    category_counts: Dict[str, int] = {}
    course_metrics: List[CourseMetric] = []
    for course in sorted_courses:
        inst = users_by_id.get(course.instructor_id)
        if not inst:
            continue
        category_counts[course.category] = category_counts.get(course.category, 0) + 1
        enrollment_count, completed_count = course_enrollments.get(course.id, [0, 0])
        course_metrics.append(
            CourseMetric(
                course_id=course.id,
                course_name=course.title,
                instructor_name=inst.full_name,
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
        course_metrics,
        key=lambda item: (item.enrollment_count, item.course_name.lower()),
        reverse=True,
    )[:10]
    least_enrolled_courses = sorted(
        course_metrics,
        key=lambda item: (item.enrollment_count, item.course_name.lower()),
    )[:10]
    highest_completion_courses = sorted(
        (item for item in course_metrics if item.enrollment_count),
        key=lambda item: (item.completion_rate, item.enrollment_count),
        reverse=True,
    )[:10]

    all_course_counts: Dict[int, int] = {}
    period_course_counts: Dict[int, int] = {}
    for c in courses:
        all_course_counts[c.instructor_id] = all_course_counts.get(c.instructor_id, 0) + 1
        if _in_range(c.created_at, start_at, end_exclusive):
            period_course_counts[c.instructor_id] = (
                period_course_counts.get(c.instructor_id, 0) + 1
            )

    all_enrollment_counts: Dict[int, int] = {}
    period_enrollment_counts: Dict[int, int] = {}
    for e in all_enrollments:
        course = courses_by_id.get(e.course_id)
        if not course:
            continue
        all_enrollment_counts[course.instructor_id] = (
            all_enrollment_counts.get(course.instructor_id, 0) + 1
        )
        if _in_range(e.enrolled_at, start_at, end_exclusive):
            period_enrollment_counts[course.instructor_id] = (
                period_enrollment_counts.get(course.instructor_id, 0) + 1
            )

    all_instructors = sorted(instructors, key=lambda u: u.full_name)
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

    student_registration_by_month: Dict[str, int] = {}
    for s in students:
        if _in_range(s.created_at, start_at, end_exclusive):
            m = _ensure_utc(s.created_at).strftime("%Y-%m")
            student_registration_by_month[m] = student_registration_by_month.get(m, 0) + 1

    enrollment_by_month: Dict[str, int] = {}
    for e in period_enrollments:
        m = _ensure_utc(e.enrolled_at).strftime("%Y-%m")
        enrollment_by_month[m] = enrollment_by_month.get(m, 0) + 1

    all_lessons = list_lessons_by_course_ids(mongo_db, [c.id for c in courses])
    lesson_to_course = {l.id: l.course_id for l in all_lessons}
    all_progress = list_lesson_progress(mongo_db)

    active_students_by_month: Dict[str, set] = {}
    for lp in all_progress:
        if lp.lesson_id not in lesson_to_course:
            continue
        if _in_range(lp.updated_at, start_at, end_exclusive):
            m = _ensure_utc(lp.updated_at).strftime("%Y-%m")
            active_students_by_month.setdefault(m, set()).add(lp.student_id)
    activity_by_month = {m: len(sids) for m, sids in active_students_by_month.items()}

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

    activities: List[AdminAnalyticsActivity] = []

    def add_user_registrations(role_users: List, activity_type: str, activity_name: str):
        rows = sorted(
            (u for u in role_users if _in_range(u.created_at, start_at, end_exclusive)),
            key=lambda u: _ensure_utc(u.created_at) or start_at,
            reverse=True,
        )[:20]
        activities.extend(
            AdminAnalyticsActivity(
                activity_type=activity_type,
                activity_name=activity_name,
                user_name=user.full_name,
                date=user.created_at,
            )
            for user in rows
        )

    add_user_registrations(students, "student_registered", "Student registered")
    add_user_registrations(instructors, "instructor_registered", "Instructor registered")

    recent_courses = sorted(
        (
            c
            for c in courses
            if c.instructor_id in users_by_id and _in_range(c.created_at, start_at, end_exclusive)
        ),
        key=lambda c: _ensure_utc(c.created_at) or start_at,
        reverse=True,
    )[:20]
    activities.extend(
        AdminAnalyticsActivity(
            activity_type="course_created",
            activity_name=f"Course created: {course.title}",
            user_name=users_by_id[course.instructor_id].full_name,
            date=course.created_at,
        )
        for course in recent_courses
    )

    recent_enrollments = sorted(
        (
            e
            for e in period_enrollments
            if e.student_id in users_by_id and e.course_id in courses_by_id
        ),
        key=lambda e: _ensure_utc(e.enrolled_at) or start_at,
        reverse=True,
    )[:20]
    activities.extend(
        AdminAnalyticsActivity(
            activity_type="course_enrolled",
            activity_name=f"Enrolled in course: {courses_by_id[e.course_id].title}",
            user_name=users_by_id[e.student_id].full_name,
            date=e.enrolled_at,
        )
        for e in recent_enrollments
    )

    completed_pairs = {
        (e.student_id, e.course_id)
        for e in all_enrollments
        if e.completion_percentage >= 100
        and e.student_id in users_by_id
        and e.course_id in courses_by_id
    }
    max_completed_by_pair: Dict[Tuple[int, int], datetime] = {}
    for lp in all_progress:
        if not lp.is_completed or lp.completed_at is None:
            continue
        cid = lesson_to_course.get(lp.lesson_id)
        if cid is None:
            continue
        pair = (lp.student_id, cid)
        if pair not in completed_pairs:
            continue
        comp_dt = _ensure_utc(lp.completed_at)
        if comp_dt and (pair not in max_completed_by_pair or comp_dt > max_completed_by_pair[pair]):
            max_completed_by_pair[pair] = comp_dt

    completed_rows = sorted(
        (
            (users_by_id[sid].full_name, courses_by_id[cid].title, dt)
            for (sid, cid), dt in max_completed_by_pair.items()
            if _in_range(dt, start_at, end_exclusive)
        ),
        key=lambda item: item[2],
        reverse=True,
    )[:20]
    activities.extend(
        AdminAnalyticsActivity(
            activity_type="course_completed",
            activity_name=f"Completed course: {course_name}",
            user_name=student_name,
            date=completed_at,
        )
        for student_name, course_name, completed_at in completed_rows
    )
    activities.sort(key=lambda activity: _ensure_utc(activity.date) or start_at, reverse=True)

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
