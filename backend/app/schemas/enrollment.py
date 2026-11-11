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
    email_delivery_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by_instructor_id: Optional[int] = None
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
    reviewed_at: Optional[datetime] = None


class EnrollmentDecisionResponse(BaseModel):
    enrollment_id: int
    status: str
    email_notification_status: str
    email_delivery_id: int


class EmailDeliveryResponse(BaseModel):
    id: int
    enrollment_id: int
    event_type: str
    recipient_email: str
    status: str
    attempts: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
