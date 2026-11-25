import logging
import math
import smtplib
from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db, get_mongo_db, require_admin
from app.models.user import UserRole
from app.repositories.assignment_repository import (
    count_all_assignments,
    count_all_submissions,
    count_assignments_by_course_ids,
)
from app.repositories.communication_repository import (
    get_email_delivery_by_id,
    list_email_deliveries_by_status,
    sync_email_delivery_to_sqlite_shadow,
)
from app.repositories.course_repository import (
    count_enrollments_by_course_ids,
    count_lessons_by_course_ids,
    get_course_by_id,
    get_courses_by_ids,
    get_distinct_course_categories,
    list_all_courses,
    list_courses_paginated,
    list_enrollments,
    restore_course_snapshot,
    sync_course_to_sqlite_shadow,
    update_course_doc,
)
from app.repositories.material_repository import count_all_materials
from app.repositories.quiz_repository import (
    count_quiz_attempts,
    count_quizzes_by_course_ids,
    get_quiz_by_id,
    list_quiz_attempts,
)
from app.repositories.user_repository import (
    MongoUser,
    count_users,
    ensure_instructor_profile_for_user,
    get_user_by_id,
    get_users_by_ids,
    list_recent_users,
    list_users_paginated,
    sync_or_rollback_user_shadow,
    update_user_fields,
)
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
from app.schemas.enrollment import EmailDeliveryResponse
from app.schemas.user import UserAdminUpdate, UserResponse
from app.services.course_service import enrich_course_response
from app.services.email_service import (
    EmailNotConfiguredError,
    send_email_delivery,
    send_test_email,
)
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
    current_user: MongoUser = Depends(require_admin),
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


@router.post(
    "/email/deliveries/{delivery_id}/retry",
    response_model=MessageResponse,
    summary="Retry a failed enrollment email notification",
)
def retry_email_delivery(
    delivery_id: int,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    delivery = get_email_delivery_by_id(mongo_db, delivery_id)
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email delivery not found.")
    if delivery.status not in ("failed", "pending"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending or failed email notifications can be retried.",
        )

    result = send_email_delivery(mongo_db, delivery, settings)
    latest = get_email_delivery_by_id(mongo_db, delivery_id)
    if latest is not None:
        sync_email_delivery_to_sqlite_shadow(db, latest)
    if result == "sent":
        return MessageResponse(message="Email server accepted the notification for delivery.")
    if result == "not_configured":
        return MessageResponse(message="Email remains queued; configure SMTP credentials before retrying.")
    return MessageResponse(message="Email delivery failed and can be retried after resolving the SMTP issue.")


@router.get(
    "/email/deliveries",
    response_model=List[EmailDeliveryResponse],
    summary="List pending or failed enrollment email notifications",
)
def list_email_deliveries(
    delivery_status: str = Query("failed", alias="status"),
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    if delivery_status not in ("pending", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delivery status must be pending or failed.",
        )
    return list_email_deliveries_by_status(mongo_db, delivery_status)


@router.get(
    "/stats",
    response_model=PlatformStats,
    summary="Get overall platform statistics and recent activity for administrator dashboard",
)
def get_platform_statistics(
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    total_users = count_users(mongo_db)
    total_students = count_users(mongo_db, role=UserRole.STUDENT.value)
    total_instructors = count_users(mongo_db, role=UserRole.INSTRUCTOR.value)
    total_admins = count_users(mongo_db, role=UserRole.ADMIN.value)

    all_courses = list_all_courses(mongo_db)
    total_courses = len(all_courses)
    published_courses = sum(1 for c in all_courses if c.is_published)
    total_enrollments = int(mongo_db["course_enrollments"].count_documents({}))

    total_attempts = count_quiz_attempts(mongo_db)
    passed_attempts = count_quiz_attempts(mongo_db, passed_only=True)
    avg_pass_rate = (
        round((passed_attempts / total_attempts) * 100.0, 1)
        if total_attempts > 0
        else 0.0
    )

    total_assignments = count_all_assignments(mongo_db)
    total_submissions = count_all_submissions(mongo_db)
    total_materials = count_all_materials(mongo_db)

    activities: List[AdminRecentActivity] = []

    recent_users = list_recent_users(mongo_db, limit=5)
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

    recent_enrollments = list_enrollments(mongo_db, sort_desc=True, limit=5)
    recent_courses = all_courses[:5]
    recent_quiz_attempts = sorted(
        list_quiz_attempts(mongo_db),
        key=lambda qa: qa.started_at,
        reverse=True,
    )[:5]

    user_ids_needed = (
        [e.student_id for e in recent_enrollments]
        + [c.instructor_id for c in recent_courses]
        + [qa.student_id for qa in recent_quiz_attempts]
    )
    users_map = get_users_by_ids(mongo_db, user_ids_needed)
    courses_map = {c.id: c for c in all_courses}

    for e in recent_enrollments:
        student = users_map.get(e.student_id)
        course = courses_map.get(e.course_id)
        if not student or not course:
            continue
        activities.append(
            AdminRecentActivity(
                activity_type="course_enrolled",
                title=f"Enrollment: {student.full_name}",
                description=f"Enrolled in '{course.title}'",
                timestamp=e.enrolled_at,
                user_name=student.full_name,
                user_email=student.email,
                reference_id=e.id,
            )
        )

    for c in recent_courses:
        inst = users_map.get(c.instructor_id)
        if not inst:
            continue
        activities.append(
            AdminRecentActivity(
                activity_type="course_created",
                title=f"Course Created: {c.title}",
                description=f"Authored by {inst.full_name} ({c.category})",
                timestamp=c.created_at,
                user_name=inst.full_name,
                user_email=inst.email,
                reference_id=c.id,
            )
        )

    quiz_cache = {}
    for qa in recent_quiz_attempts:
        user_obj = users_map.get(qa.student_id)
        if not user_obj or qa.quiz_id is None:
            continue
        if qa.quiz_id not in quiz_cache:
            quiz_cache[qa.quiz_id] = get_quiz_by_id(mongo_db, qa.quiz_id)
        quiz_obj = quiz_cache.get(qa.quiz_id)
        if not quiz_obj:
            continue
        activities.append(
            AdminRecentActivity(
                activity_type="quiz_attempt",
                title=f"Assessment: {user_obj.full_name}",
                description=f"{'Passed' if qa.passed else 'Attempted'} '{quiz_obj.title}' with score {qa.score:.1f}%",
                timestamp=qa.started_at,
                user_name=user_obj.full_name,
                user_email=user_obj.email,
                reference_id=qa.id,
            )
        )

    activities.sort(
        key=lambda x: x.timestamp
        if x.timestamp.tzinfo is not None
        else x.timestamp.replace(tzinfo=timezone.utc),
        reverse=True,
    )
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
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    total, total_pages, users = list_users_paginated(
        mongo_db,
        search=search,
        role=role,
        is_active=is_active,
        page=page,
        page_size=page_size,
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
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(mongo_db, user_id)
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

    updates: dict = {}
    if user_update.role is not None:
        valid_roles = [r.value for r in UserRole]
        if user_update.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of {valid_roles}",
            )
        updates["role"] = user_update.role

    if user_update.is_active is not None:
        updates["is_active"] = user_update.is_active

    if user_update.full_name is not None:
        updates["full_name"] = user_update.full_name.strip()

    updated_user = update_user_fields(mongo_db, user.id, updates) if updates else user
    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    profile = None
    if updated_user.role == UserRole.INSTRUCTOR.value:
        profile = ensure_instructor_profile_for_user(mongo_db, updated_user)

    sync_or_rollback_user_shadow(mongo_db, db, user, updated_user, profile=profile)
    return UserResponse.model_validate(updated_user)


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
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    total, courses = list_courses_paginated(
        mongo_db,
        search=search,
        category=category,
        difficulty=difficulty,
        is_published=is_published,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    if not courses:
        return PaginatedAdminCourseResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=[],
        )

    course_ids = [c.id for c in courses]
    instructor_map = get_users_by_ids(mongo_db, [c.instructor_id for c in courses])

    enrollment_counts = count_enrollments_by_course_ids(mongo_db, course_ids)
    lesson_counts = count_lessons_by_course_ids(mongo_db, course_ids)
    quiz_counts = count_quizzes_by_course_ids(mongo_db, course_ids)
    assignment_counts = count_assignments_by_course_ids(mongo_db, course_ids)

    items: List[AdminCourseItem] = []
    for c in courses:
        inst = instructor_map.get(c.instructor_id)
        inst_name = inst.full_name if inst else "Unknown Instructor"
        inst_email = inst.email if inst else "unknown@eduverse.io"
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
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_distinct_course_categories(mongo_db)


@router.patch(
    "/courses/{course_id}/publish",
    response_model=AdminCourseItem,
    summary="Admin toggle course publication status",
)
def admin_toggle_publish(
    course_id: int,
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    updated = update_course_doc(mongo_db, course.id, {"is_published": not course.is_published})
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    try:
        sync_course_to_sqlite_shadow(db, updated)
    except Exception:
        restore_course_snapshot(mongo_db, course)
        raise

    enrolled = count_enrollments_by_course_ids(mongo_db, [updated.id]).get(updated.id, 0)
    lessons = count_lessons_by_course_ids(mongo_db, [updated.id]).get(updated.id, 0)
    quizzes = count_quizzes_by_course_ids(mongo_db, [updated.id]).get(updated.id, 0)
    assignments = count_assignments_by_course_ids(mongo_db, [updated.id]).get(updated.id, 0)

    inst = get_user_by_id(mongo_db, updated.instructor_id)
    inst_name = inst.full_name if inst else "Unknown Instructor"
    inst_email = inst.email if inst else "unknown@eduverse.io"

    return AdminCourseItem(
        id=updated.id,
        title=updated.title,
        description=updated.description,
        category=updated.category,
        difficulty=updated.difficulty,
        is_published=updated.is_published,
        instructor_id=updated.instructor_id,
        instructor_name=inst_name,
        instructor_email=inst_email,
        enrolled_students_count=enrolled,
        lesson_count=lessons,
        quiz_count=quizzes,
        assignment_count=assignments,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


def _admin_analytics(
    mongo_db: Database, start_date: Optional[date], end_date: Optional[date]
) -> AdminAnalyticsDashboard:
    try:
        return build_admin_analytics(mongo_db, start_date, end_date)
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
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    return _admin_analytics(mongo_db, start_date, end_date)


@router.get(
    "/analytics/overview",
    response_model=AdminAnalyticsOverview,
    summary="Get administrator overview statistics",
)
def get_admin_analytics_overview(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    return _admin_analytics(mongo_db, start_date, end_date).overview


@router.get(
    "/analytics/students",
    response_model=AdminStudentAnalytics,
    summary="Get student analytics and performance rankings",
)
def get_admin_student_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    return _admin_analytics(mongo_db, start_date, end_date).students


@router.get(
    "/analytics/courses",
    response_model=AdminCourseAnalytics,
    summary="Get course analytics and course rankings",
)
def get_admin_course_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    return _admin_analytics(mongo_db, start_date, end_date).courses


@router.get(
    "/analytics/instructors",
    response_model=AdminInstructorAnalytics,
    summary="Get instructor analytics and enrollment totals",
)
def get_admin_instructor_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    return _admin_analytics(mongo_db, start_date, end_date).instructors


@router.get(
    "/analytics/trends",
    response_model=AdminAnalyticsTrends,
    summary="Get monthly registration, enrollment, and student activity trends",
)
def get_admin_analytics_trends(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    return _admin_analytics(mongo_db, start_date, end_date).trends


@router.get(
    "/analytics/activities",
    response_model=List[AdminAnalyticsActivity],
    summary="Get recent administrative activity",
)
def get_admin_analytics_activities(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    return _admin_analytics(mongo_db, start_date, end_date).recent_activities


@router.get(
    "/analytics/export",
    summary="Export administrative analytics as CSV or PDF",
)
def export_admin_analytics(
    report_format: str = Query("csv", alias="format", pattern="^(csv|pdf)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: MongoUser = Depends(require_admin),
    mongo_db: Database = Depends(get_mongo_db),
):
    data = _admin_analytics(mongo_db, start_date, end_date)
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
