from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.course import CourseResponse


class EnrollmentResponse(BaseModel):
    id: int
    student_id: int
    course_id: int
    enrolled_at: datetime
    completion_percentage: float
    status: str
    student_name: str
    student_email: str
    course_name: str
    instructor_id: int
    email_notification_status: Optional[str] = None
    course: Optional[CourseResponse] = None

    model_config = ConfigDict(from_attributes=True)


class InstructorEnrollmentResponse(BaseModel):
    enrollment_id: int
    student_id: int
    student_name: str
    student_email: str
    course_id: int
    course_name: str
    instructor_id: int
    enrolled_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)
