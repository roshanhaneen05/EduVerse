from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class StudentSummary(BaseModel):
    id: int
    full_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class AssignmentBase(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: Optional[str] = None
    instructions: str = Field(min_length=10)
    max_marks: int = Field(default=100, ge=1)
    due_date: Optional[datetime] = None
    section_id: Optional[int] = None
    allow_resubmission: bool = True


class AssignmentCreate(AssignmentBase):
    is_published: bool = False


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    instructions: Optional[str] = Field(None, min_length=10)
    max_marks: Optional[int] = Field(None, ge=1)
    due_date: Optional[datetime] = None
    section_id: Optional[int] = None
    allow_resubmission: Optional[bool] = None
    is_published: Optional[bool] = None
    is_closed: Optional[bool] = None
    is_archived: Optional[bool] = None


class SubmissionSummary(BaseModel):
    id: int
    student_id: int
    status: str
    submitted_at: datetime
    is_late: bool
    grade: Optional[float] = None
    feedback: Optional[str] = None
    graded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AssignmentResponse(AssignmentBase):
    id: int
    course_id: int
    is_published: bool
    is_closed: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    submission_count: int = 0
    graded_count: int = 0
    my_submission: Optional[SubmissionSummary] = None

    model_config = ConfigDict(from_attributes=True)


class AssignmentDetailResponse(AssignmentResponse):
    course_title: Optional[str] = None
    section_title: Optional[str] = None


class SubmissionCreate(BaseModel):
    submission_text: str = Field(min_length=5)
    attachments_json: Optional[str] = None


class SubmissionGradePayload(BaseModel):
    grade: float = Field(ge=0)
    feedback: Optional[str] = None


class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    student: Optional[StudentSummary] = None
    submission_text: str
    attachments_json: Optional[str] = None
    status: str
    is_late: bool
    submitted_at: datetime
    updated_at: datetime
    grade: Optional[float] = None
    feedback: Optional[str] = None
    graded_by_id: Optional[int] = None
    graded_at: Optional[datetime] = None
    assignment_title: Optional[str] = None
    max_marks: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

