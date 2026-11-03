from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_current_user, get_db
from app.models.enrollment import CourseEnrollment
from app.models.user import User
from app.schemas.enrollment import EnrollmentResponse
from app.services.course_service import enrich_course_response

router = APIRouter(prefix="/enrollments", tags=["Student Enrollments"])


@router.get(
    "/my-courses",
    response_model=List[EnrollmentResponse],
    summary="List courses currently enrolled by the authenticated user",
)
def get_my_enrollments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enrollments = (
        db.query(CourseEnrollment)
        .options(joinedload(CourseEnrollment.course))
        .filter(CourseEnrollment.student_id == current_user.id)
        .order_by(CourseEnrollment.enrolled_at.desc())
        .all()
    )

    result = []
    for enr in enrollments:
        if enr.course:
            enriched = enrich_course_response(db, enr.course)
            result.append(
                EnrollmentResponse(
                    id=enr.id,
                    student_id=enr.student_id,
                    course_id=enr.course_id,
                    enrolled_at=enr.enrolled_at,
                    completion_percentage=enr.completion_percentage,
                    course=enriched,
                )
            )
    return result
