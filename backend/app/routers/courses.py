from datetime import datetime, timezone
import logging
import smtplib
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson
from app.models.section import CourseSection
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.course import CourseDetailResponse, CourseResponse, LessonOutlineItem
from app.schemas.enrollment import EnrollmentResponse
from app.schemas.section import SectionDetailResponse
from app.security.rbac import get_token_from_request, require_student
from app.config import get_settings
from app.services.email_service import EmailNotConfiguredError, send_enrollment_email
from app.services.course_service import (
    enrich_course_response,
    get_course_detail,
    list_courses,
)

router = APIRouter(prefix="/courses", tags=["Courses & Catalog"])
logger = logging.getLogger(__name__)
settings = get_settings()


def get_optional_user(
    token: Optional[str] = Depends(get_token_from_request),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Soft auth dependency returning current User if token is present and valid, or None."""
    if not token:
        return None
    try:
        from app.security.jwt import decode_access_token
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
        return db.query(User).filter(User.id == user_id, User.is_active == True).first()
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
    db: Session = Depends(get_db),
):
    return list_courses(
        db=db,
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
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    return get_course_detail(db, course_id, current_user=current_user)


@router.post(
    "/{course_id}/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll current student in a course",
)
def enroll_in_course(
    course_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
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
    instructor = course.instructor
    if not instructor or instructor.role != "instructor" or not instructor.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This course does not have an active instructor assigned.",
        )

    # Prevent duplicate enrollment
    existing = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.student_id == current_user.id,
            CourseEnrollment.course_id == course_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already enrolled in this course.",
        )

    enrollment = CourseEnrollment(
        student_id=current_user.id,
        course_id=course_id,
        enrolled_at=datetime.now(timezone.utc),
        completion_percentage=0.0,
        status="active",
    )
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        duplicate = db.query(CourseEnrollment).filter(
            CourseEnrollment.student_id == current_user.id,
            CourseEnrollment.course_id == course_id,
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You are already enrolled in this course.",
            ) from exc
        raise
    db.refresh(enrollment)

    email_notification_status = "sent"
    try:
        send_enrollment_email(enrollment, current_user, course, instructor, settings)
    except EmailNotConfiguredError as exc:
        email_notification_status = "not_configured"
        logger.warning(
            "Enrollment %s saved, but instructor email is not configured: %s",
            enrollment.id,
            exc,
        )
    except (smtplib.SMTPException, OSError, ValueError):
        email_notification_status = "failed"
        logger.exception(
            "Enrollment %s was saved, but instructor email delivery failed",
            enrollment.id,
        )

    enriched_course = enrich_course_response(db, course)
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
        course=enriched_course,
    )


@router.delete(
    "/{course_id}/enroll",
    response_model=MessageResponse,
    summary="Unenroll from a course",
)
def unenroll_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enrollment = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.student_id == current_user.id,
            CourseEnrollment.course_id == course_id,
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not enrolled in this course.",
        )
    db.delete(enrollment)
    db.commit()
    return MessageResponse(message="Successfully unenrolled from course.")


@router.get(
    "/{course_id}/sections",
    response_model=List[SectionDetailResponse],
    summary="Get sections and lessons outline for a course",
)
def get_public_course_sections(
    course_id: int,
    db: Session = Depends(get_db),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    sections = (
        db.query(CourseSection)
        .filter(CourseSection.course_id == course_id)
        .order_by(CourseSection.order_index.asc())
        .all()
    )
    lessons = (
        db.query(Lesson)
        .filter(Lesson.course_id == course_id)
        .order_by(Lesson.order_index.asc())
        .all()
    )
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
