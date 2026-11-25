from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_current_user, get_db, get_mongo_db
from app.repositories.communication_repository import (
    create_email_delivery_doc,
    delete_email_delivery_doc,
    delete_email_delivery_from_sqlite_shadow,
    get_email_delivery_by_id,
    sync_email_delivery_to_sqlite_shadow,
)
from app.repositories.course_repository import (
    create_enrollment_doc,
    delete_enrollment_doc,
    delete_enrollment_from_sqlite_shadow,
    get_course_by_id,
    get_enrollment_by_student_and_course,
    list_lessons_for_course,
    list_sections_for_course,
    sync_enrollment_to_sqlite_shadow,
)
from app.repositories.user_repository import MongoUser, get_user_by_id
from app.schemas.common import MessageResponse
from app.schemas.course import CourseDetailResponse, CourseResponse, LessonOutlineItem
from app.schemas.enrollment import EnrollmentResponse
from app.schemas.section import SectionDetailResponse
from app.security.rbac import get_token_from_request, require_student
from app.services.course_service import (
    enrich_course_response,
    get_course_detail,
    list_courses,
)
from app.services.email_service import (
    ENROLLMENT_REQUEST,
    send_email_delivery,
)

router = APIRouter(prefix="/courses", tags=["Courses & Catalog"])
settings = get_settings()


def get_optional_user(
    token: Optional[str] = Depends(get_token_from_request),
    mongo_db: Database = Depends(get_mongo_db),
) -> Optional[MongoUser]:
    """Soft auth dependency returning current User if token is present and valid, or None."""
    if not token:
        return None
    try:
        from app.security.jwt import decode_access_token
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
        user = get_user_by_id(mongo_db, user_id)
        if user and user.is_active:
            return user
        return None
    except Exception:
        return None


@router.get(
    "",
    response_model=List[CourseResponse],
    summary="Browse course catalog",
)
def get_courses(
    search: Optional[str] = Query(None, description="Search courses by title, description, or category"),
    category: Optional[str] = Query(None, description="Filter by category"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    mongo_db: Database = Depends(get_mongo_db),
):
    return list_courses(
        mongo_db=mongo_db,
        search=search,
        category=category,
        difficulty=difficulty,
        is_published=True,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{course_id}",
    response_model=CourseDetailResponse,
    summary="Get course detail by ID",
)
def get_course(
    course_id: int,
    current_user: Optional[MongoUser] = Depends(get_optional_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_course_detail(mongo_db, course_id, current_user=current_user)


@router.post(
    "/{course_id}/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll current student in a course",
)
def enroll_in_course(
    course_id: int,
    current_user: MongoUser = Depends(require_student),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )
    if not course.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot enroll in an unpublished course.",
        )
    instructor = get_user_by_id(mongo_db, course.instructor_id)
    if not instructor or instructor.role != "instructor" or not instructor.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This course does not have an active instructor assigned.",
        )

    existing = get_enrollment_by_student_and_course(mongo_db, current_user.id, course_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already enrolled in this course.",
        )

    enrollment = create_enrollment_doc(
        mongo_db,
        student_id=current_user.id,
        course_id=course_id,
        enrollment_status="pending",
        completion_percentage=0.0,
    )
    delivery = None
    try:
        delivery = create_email_delivery_doc(
            mongo_db,
            enrollment_id=enrollment.id,
            event_type=ENROLLMENT_REQUEST,
            recipient_email=instructor.email,
        )
        sync_enrollment_to_sqlite_shadow(db, enrollment)
        sync_email_delivery_to_sqlite_shadow(db, delivery)
    except Exception:
        if delivery is not None:
            delete_email_delivery_from_sqlite_shadow(db, delivery.id)
            delete_email_delivery_doc(mongo_db, delivery.id)
        delete_enrollment_from_sqlite_shadow(db, enrollment.id)
        delete_enrollment_doc(mongo_db, enrollment.id)
        raise

    email_notification_status = send_email_delivery(mongo_db, delivery, settings)
    latest_delivery = get_email_delivery_by_id(mongo_db, delivery.id)
    if latest_delivery is not None:
        sync_email_delivery_to_sqlite_shadow(db, latest_delivery)

    enriched_course = enrich_course_response(mongo_db, course)
    return EnrollmentResponse(
        id=enrollment.id,
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
        enrolled_at=enrollment.enrolled_at,
        completion_percentage=enrollment.completion_percentage,
        status=enrollment.status,
        student_name=current_user.full_name,
        student_email=current_user.email,
        course_name=course.title,
        instructor_id=instructor.id,
        email_notification_status=email_notification_status,
        email_delivery_id=delivery.id,
        reviewed_at=enrollment.reviewed_at,
        reviewed_by_instructor_id=enrollment.reviewed_by_instructor_id,
        course=enriched_course,
    )


@router.delete(
    "/{course_id}/enroll",
    response_model=MessageResponse,
    summary="Unenroll from a course",
)
def unenroll_course(
    course_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    enrollment = get_enrollment_by_student_and_course(mongo_db, current_user.id, course_id)
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not enrolled in this course.",
        )
    mongo_db["email_deliveries"].delete_many({"enrollment_id": int(enrollment.id)})
    delete_enrollment_doc(mongo_db, enrollment.id)
    delete_enrollment_from_sqlite_shadow(db, enrollment.id)
    return MessageResponse(message="Successfully unenrolled from course.")


@router.get(
    "/{course_id}/sections",
    response_model=List[SectionDetailResponse],
    summary="Get sections and lessons outline for a course",
)
def get_public_course_sections(
    course_id: int,
    mongo_db: Database = Depends(get_mongo_db),
):
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    sections = list_sections_for_course(mongo_db, course_id)
    lessons = list_lessons_for_course(mongo_db, course_id)
    lesson_map = {}
    for l in lessons:
        lesson_map.setdefault(l.section_id, []).append(
            LessonOutlineItem(
                id=l.id,
                course_id=l.course_id,
                section_id=l.section_id,
                title=l.title,
                order_index=l.order_index,
                is_completed=False,
            )
        )

    results = []
    for s in sections:
        sec_lessons = lesson_map.get(s.id, [])
        results.append(
            SectionDetailResponse(
                id=s.id,
                course_id=s.course_id,
                title=s.title,
                description=s.description,
                order_index=s.order_index,
                lesson_count=len(sec_lessons),
                created_at=s.created_at,
                updated_at=s.updated_at,
                lessons=sec_lessons,
            )
        )
    return results
