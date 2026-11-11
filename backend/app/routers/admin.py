import logging
import math
import smtplib
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db, require_admin
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson
from app.models.material import LearningMaterial
from app.models.quiz import Quiz, QuizAttempt
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminCourseItem,
    AdminRecentActivity,
    PaginatedAdminCourseResponse,
    PaginatedUserResponse,
    PlatformStats,
)
from app.schemas.admin_analytics import (
    AdminAnalyticsActivity,
    AdminAnalyticsDashboard,
    AdminAnalyticsOverview,
    AdminAnalyticsTrends,
    AdminCourseAnalytics,
    AdminInstructorAnalytics,
    AdminStudentAnalytics,
)
from app.schemas.common import MessageResponse
from app.schemas.course import CourseResponse
from app.schemas.user import UserAdminUpdate, UserResponse
from app.services.course_service import enrich_course_response
from app.services.email_service import EmailNotConfiguredError, send_test_email
from app.services.admin_analytics_service import (
    analytics_csv_report,
    analytics_pdf_report,
    build_admin_analytics,
)

router = APIRouter(prefix="/admin", tags=["Administrator Management"])
logger = logging.getLogger(__name__)
settings = get_settings()


class EmailTestRequest(BaseModel):
    recipient_email: EmailStr


@router.post(
    "/email/test",
    response_model=MessageResponse,
    summary="Send a development SMTP test message",
)
def test_email_configuration(
    request: EmailTestRequest,
    current_user: User = Depends(require_admin),
):
    if settings.ENVIRONMENT.lower() != "development":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This endpoint is available only in development.",
        )

    try:
        send_test_email(str(request.recipient_email), settings)
    except EmailNotConfiguredError as exc:
        logger.error("SMTP test email is not configured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except smtplib.SMTPAuthenticationError as exc:
        logger.exception("SMTP test email authentication failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="SMTP authentication failed. Verify EMAIL_HOST_USER and the Google App Password.",
        ) from exc
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        logger.exception("SMTP test email delivery failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SMTP test email failed: {exc}",
        ) from exc

    return MessageResponse(message="SMTP accepted the test email for delivery.")


@router.get(
    "/stats",
    response_model=PlatformStats,
    summary="Get overall platform statistics and recent activity for administrator dashboard",
)
def get_platform_statistics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_students = db.query(func.count(User.id)).filter(User.role == UserRole.STUDENT.value).scalar() or 0
    total_instructors = db.query(func.count(User.id)).filter(User.role == UserRole.INSTRUCTOR.value).scalar() or 0
    total_admins = db.query(func.count(User.id)).filter(User.role == UserRole.ADMIN.value).scalar() or 0

    total_courses = db.query(func.count(Course.id)).scalar() or 0
    published_courses = db.query(func.count(Course.id)).filter(Course.is_published == True).scalar() or 0
    total_enrollments = db.query(func.count(CourseEnrollment.id)).scalar() or 0

    total_attempts = db.query(func.count(QuizAttempt.id)).scalar() or 0
    passed_attempts = db.query(func.count(QuizAttempt.id)).filter(QuizAttempt.passed == True).scalar() or 0
    avg_pass_rate = round((passed_attempts / total_attempts) * 100.0, 1) if total_attempts > 0 else 0.0

    total_assignments = db.query(func.count(Assignment.id)).scalar() or 0
    total_submissions = db.query(func.count(AssignmentSubmission.id)).scalar() or 0
    total_materials = db.query(func.count(LearningMaterial.id)).scalar() or 0

    # Collect recent platform activities across models
    activities: List[AdminRecentActivity] = []

    # 1. Recent user registrations
    recent_users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .limit(5)
        .all()
    )
    for u in recent_users:
        activities.append(
            AdminRecentActivity(
                activity_type="user_registered",
                title=f"User Registered: {u.full_name}",
                description=f"Account created with role '{u.role}'",
                timestamp=u.created_at,
                user_name=u.full_name,
                user_email=u.email,
                reference_id=u.id,
            )
        )

    # 2. Recent course enrollments
    recent_enrollments = (
        db.query(CourseEnrollment)
        .join(User, CourseEnrollment.student_id == User.id)
        .join(Course, CourseEnrollment.course_id == Course.id)
        .order_by(CourseEnrollment.enrolled_at.desc())
        .limit(5)
        .all()
    )
    for e in recent_enrollments:
        student_name = e.student.full_name if e.student else "Student"
        student_email = e.student.email if e.student else None
        course_title = e.course.title if e.course else "Course"
        activities.append(
            AdminRecentActivity(
                activity_type="course_enrolled",
                title=f"Enrollment: {student_name}",
                description=f"Enrolled in '{course_title}'",
                timestamp=e.enrolled_at,
                user_name=student_name,
                user_email=student_email,
                reference_id=e.id,
            )
        )

    # 3. Recent course creations
    recent_courses = (
        db.query(Course)
        .join(User, Course.instructor_id == User.id)
        .order_by(Course.created_at.desc())
        .limit(5)
        .all()
    )
    for c in recent_courses:
        inst_name = c.instructor.full_name if c.instructor else "Instructor"
        inst_email = c.instructor.email if c.instructor else None
        activities.append(
            AdminRecentActivity(
                activity_type="course_created",
                title=f"Course Created: {c.title}",
                description=f"Authored by {inst_name} ({c.category})",
                timestamp=c.created_at,
                user_name=inst_name,
                user_email=inst_email,
                reference_id=c.id,
            )
        )

    # 4. Recent quiz attempts
    recent_quiz_attempts = (
        db.query(QuizAttempt)
        .join(User, QuizAttempt.student_id == User.id)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .order_by(QuizAttempt.started_at.desc())
        .limit(5)
        .all()
    )
    for qa in recent_quiz_attempts:
        uname = qa.student.full_name if qa.student else "Student"
        uemail = qa.student.email if qa.student else None
        qtitle = qa.quiz.title if qa.quiz else "Assessment"
        activities.append(
            AdminRecentActivity(
                activity_type="quiz_attempt",
                title=f"Assessment: {uname}",
                description=f"{'Passed' if qa.passed else 'Attempted'} '{qtitle}' with score {qa.score:.1f}%",
                timestamp=qa.started_at,
                user_name=uname,
                user_email=uemail,
                reference_id=qa.id,
            )
        )

    # Sort all blended activities chronologically
    activities.sort(key=lambda x: x.timestamp, reverse=True)
    recent_activities = activities[:10]

    return PlatformStats(
        total_users=total_users,
        total_students=total_students,
        total_instructors=total_instructors,
        total_admins=total_admins,
        total_courses=total_courses,
        published_courses=published_courses,
        total_enrollments=total_enrollments,
        total_quiz_attempts=total_attempts,
        average_quiz_pass_rate=avg_pass_rate,
        total_assignments=total_assignments,
        total_submissions=total_submissions,
        total_learning_materials=total_materials,
        recent_activities=recent_activities,
    )


@router.get(
    "/users",
    response_model=PaginatedUserResponse,
    summary="List, search, filter, and paginate platform users",
)
def list_platform_users(
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[str] = Query(None, description="Filter by role (student, instructor, admin)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter((User.email.ilike(s)) | (User.full_name.ilike(s)))

    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedUserResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=[UserResponse.model_validate(u) for u in users],
    )


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update a user's role, active status, or profile as administrator",
)
def update_user_status_or_role(
    user_id: int,
    user_update: UserAdminUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Protect against self-deactivation
    if user.id == current_user.id and user_update.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    # Protect against self-demotion
    if (
        user.id == current_user.id
        and user_update.role is not None
        and user_update.role != UserRole.ADMIN.value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot demote their own account role.",
        )

    if user_update.role is not None:
        valid_roles = [r.value for r in UserRole]
        if user_update.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of {valid_roles}",
            )
        user.role = user_update.role

    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    if user_update.full_name is not None:
        user.full_name = user_update.full_name.strip()

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get(
    "/courses",
    response_model=PaginatedAdminCourseResponse,
    summary="List, search, filter, and paginate all platform courses for administrative oversight",
)
def list_platform_courses(
    search: Optional[str] = Query(None, description="Search by title or description"),
    category: Optional[str] = Query(None, description="Filter by category"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    is_published: Optional[bool] = Query(None, description="Filter by published status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Course)
    if is_published is not None:
        query = query.filter(Course.is_published == is_published)
    if category:
        query = query.filter(Course.category == category)
    if difficulty:
        query = query.filter(Course.difficulty == difficulty)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter((Course.title.ilike(s)) | (Course.description.ilike(s)))

    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    courses = (
        query.order_by(Course.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    if not courses:
        return PaginatedAdminCourseResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=[],
        )

    course_ids = [c.id for c in courses]

    # Batch aggregation queries (O(1) database trips)
    enrollment_counts = dict(
        db.query(CourseEnrollment.course_id, func.count(CourseEnrollment.id))
        .filter(CourseEnrollment.course_id.in_(course_ids))
        .group_by(CourseEnrollment.course_id)
        .all()
    )

    lesson_counts = dict(
        db.query(Lesson.course_id, func.count(Lesson.id))
        .filter(Lesson.course_id.in_(course_ids))
        .group_by(Lesson.course_id)
        .all()
    )

    quiz_counts = dict(
        db.query(Quiz.course_id, func.count(Quiz.id))
        .filter(Quiz.course_id.in_(course_ids))
        .group_by(Quiz.course_id)
        .all()
    )

    assignment_counts = dict(
        db.query(Assignment.course_id, func.count(Assignment.id))
        .filter(Assignment.course_id.in_(course_ids))
        .group_by(Assignment.course_id)
        .all()
    )

    items: List[AdminCourseItem] = []
    for c in courses:
        inst_name = c.instructor.full_name if c.instructor else "Unknown Instructor"
        inst_email = c.instructor.email if c.instructor else "unknown@eduverse.io"
        items.append(
            AdminCourseItem(
                id=c.id,
                title=c.title,
                description=c.description,
                category=c.category,
                difficulty=c.difficulty,
                is_published=c.is_published,
                instructor_id=c.instructor_id,
                instructor_name=inst_name,
                instructor_email=inst_email,
                enrolled_students_count=enrollment_counts.get(c.id, 0),
                lesson_count=lesson_counts.get(c.id, 0),
                quiz_count=quiz_counts.get(c.id, 0),
                assignment_count=assignment_counts.get(c.id, 0),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )

    return PaginatedAdminCourseResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.get(
    "/courses/categories",
    response_model=List[str],
    summary="Get list of distinct course categories for filter controls",
)
def get_admin_course_categories(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(Course.category).distinct().all()
    return sorted([r[0] for r in rows if r[0]])


@router.patch(
    "/courses/{course_id}/publish",
    response_model=AdminCourseItem,
    summary="Admin toggle course publication status",
)
def admin_toggle_publish(
    course_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    course.is_published = not course.is_published
    db.commit()
    db.refresh(course)

    enrolled = db.query(func.count(CourseEnrollment.id)).filter(CourseEnrollment.course_id == course.id).scalar() or 0
    lessons = db.query(func.count(Lesson.id)).filter(Lesson.course_id == course.id).scalar() or 0
    quizzes = db.query(func.count(Quiz.id)).filter(Quiz.course_id == course.id).scalar() or 0
    assignments = db.query(func.count(Assignment.id)).filter(Assignment.course_id == course.id).scalar() or 0

    inst_name = course.instructor.full_name if course.instructor else "Unknown Instructor"
    inst_email = course.instructor.email if course.instructor else "unknown@eduverse.io"

    return AdminCourseItem(
        id=course.id,
        title=course.title,
        description=course.description,
        category=course.category,
        difficulty=course.difficulty,
        is_published=course.is_published,
        instructor_id=course.instructor_id,
        instructor_name=inst_name,
        instructor_email=inst_email,
        enrolled_students_count=enrolled,
        lesson_count=lessons,
        quiz_count=quizzes,
        assignment_count=assignments,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


def _admin_analytics(
    db: Session, start_date: Optional[date], end_date: Optional[date]
) -> AdminAnalyticsDashboard:
    try:
        return build_admin_analytics(db, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get(
    "/analytics/dashboard",
    response_model=AdminAnalyticsDashboard,
    summary="Get all administrator analytics for the selected date range",
)
def get_admin_analytics_dashboard(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _admin_analytics(db, start_date, end_date)


@router.get(
    "/analytics/overview",
    response_model=AdminAnalyticsOverview,
    summary="Get administrator overview statistics",
)
def get_admin_analytics_overview(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _admin_analytics(db, start_date, end_date).overview


@router.get(
    "/analytics/students",
    response_model=AdminStudentAnalytics,
    summary="Get student analytics and performance rankings",
)
def get_admin_student_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _admin_analytics(db, start_date, end_date).students


@router.get(
    "/analytics/courses",
    response_model=AdminCourseAnalytics,
    summary="Get course analytics and course rankings",
)
def get_admin_course_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _admin_analytics(db, start_date, end_date).courses


@router.get(
    "/analytics/instructors",
    response_model=AdminInstructorAnalytics,
    summary="Get instructor analytics and enrollment totals",
)
def get_admin_instructor_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _admin_analytics(db, start_date, end_date).instructors


@router.get(
    "/analytics/trends",
    response_model=AdminAnalyticsTrends,
    summary="Get monthly registration, enrollment, and student activity trends",
)
def get_admin_analytics_trends(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _admin_analytics(db, start_date, end_date).trends


@router.get(
    "/analytics/activities",
    response_model=List[AdminAnalyticsActivity],
    summary="Get recent administrative activity",
)
def get_admin_analytics_activities(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _admin_analytics(db, start_date, end_date).recent_activities


@router.get(
    "/analytics/export",
    summary="Export administrative analytics as CSV or PDF",
)
def export_admin_analytics(
    report_format: str = Query("csv", alias="format", pattern="^(csv|pdf)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    data = _admin_analytics(db, start_date, end_date)
    if report_format == "csv":
        return Response(
            content=analytics_csv_report(data),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="eduverse-analytics.csv"'},
        )
    return Response(
        content=analytics_pdf_report(data),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="eduverse-analytics.pdf"'},
    )
