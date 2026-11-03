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
    course: Optional[CourseResponse] = None

    model_config = ConfigDict(from_attributes=True)
