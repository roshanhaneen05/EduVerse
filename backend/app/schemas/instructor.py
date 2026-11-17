from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InstructorCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone_number: str = Field(min_length=7, max_length=30, pattern=r"^[+()0-9\s.-]+$")
    qualification: str = Field(min_length=2, max_length=150)
    department: str = Field(min_length=2, max_length=150)
    subject_expertise: str = Field(min_length=2, max_length=255)
    experience_years: int = Field(ge=0, le=60)
    profile_photo_url: Optional[str] = Field(
        default=None,
        max_length=500,
        pattern=r"^https?://\S+$",
    )


class InstructorUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(
        default=None,
        min_length=7,
        max_length=30,
        pattern=r"^[+()0-9\s.-]+$",
    )
    qualification: Optional[str] = Field(default=None, min_length=2, max_length=150)
    department: Optional[str] = Field(default=None, min_length=2, max_length=150)
    subject_expertise: Optional[str] = Field(default=None, min_length=2, max_length=255)
    experience_years: Optional[int] = Field(default=None, ge=0, le=60)
    profile_photo_url: Optional[str] = Field(
        default=None,
        max_length=500,
        pattern=r"^https?://\S+$",
    )


class InstructorStatusUpdate(BaseModel):
    is_active: bool


class InstructorResponse(BaseModel):
    user_id: int
    instructor_id: str
    full_name: str
    email: EmailStr
    phone_number: str
    qualification: str
    department: str
    subject_expertise: str
    experience_years: int
    profile_photo_url: Optional[str]
    is_active: bool
    registered_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstructorCreatedResponse(InstructorResponse):
    email_delivery_status: str


class CourseInstructorAssignment(BaseModel):
    instructor_user_id: int = Field(gt=0)
