from typing import List
from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.dependencies import get_mongo_db, require_student
from app.repositories.course_repository import (
    get_course_by_id,
    list_enrollments_for_student,
)
from app.repositories.user_repository import MongoUser, get_users_by_ids
from app.schemas.enrollment import EnrollmentResponse
from app.services.course_service import enrich_course_response

router = APIRouter(prefix="/enrollments", tags=["Student Enrollments"])


@router.get(
    "/my-courses",
    response_model=List[EnrollmentResponse],
    summary="List courses currently enrolled by the authenticated user",
)
def get_my_enrollments(
    current_user: MongoUser = Depends(require_student),
    mongo_db: Database = Depends(get_mongo_db),
):
    enrollments = list_enrollments_for_student(mongo_db, current_user.id)
    courses = {}
    for enr in enrollments:
        if enr.course_id not in courses:
            c = get_course_by_id(mongo_db, enr.course_id)
            if c:
                courses[enr.course_id] = c

    instructor_map = get_users_by_ids(
        mongo_db,
        [c.instructor_id for c in courses.values()],
    )

    result = []
    for enr in enrollments:
        course = courses.get(enr.course_id)
        if course:
            enriched = enrich_course_response(mongo_db, course, instructor_cache=instructor_map)
            result.append(
                EnrollmentResponse(
                    id=enr.id,
                    student_id=enr.student_id,
                    course_id=enr.course_id,
                    enrolled_at=enr.enrolled_at,
                    completion_percentage=enr.completion_percentage,
                    status=enr.status,
                    student_name=current_user.full_name,
                    student_email=current_user.email,
                    course_name=course.title,
                    instructor_id=course.instructor_id,
                    reviewed_at=enr.reviewed_at,
                    reviewed_by_instructor_id=enr.reviewed_by_instructor_id,
                    course=enriched,
                )
            )
    return result
