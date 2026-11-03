from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class LessonBase(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    content: str = Field(min_length=10)
    video_url: Optional[str] = None
    order_index: int = Field(default=1, ge=1)
    section_id: Optional[int] = None


class LessonCreate(LessonBase):
    pass


class LessonUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    content: Optional[str] = Field(None, min_length=10)
    video_url: Optional[str] = None
    order_index: Optional[int] = Field(None, ge=1)
    section_id: Optional[int] = None


class LessonResponse(LessonBase):
    id: int
    course_id: int
    video_url: Optional[str] = None
    is_completed: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonProgressResponse(BaseModel):
    student_id: int
    lesson_id: int
    is_completed: bool
    completed_at: Optional[datetime] = None
    updated_at: datetime
    course_completion_percentage: float

    @computed_field
    @property
    def course_progress_percentage(self) -> float:
        return self.course_completion_percentage

    model_config = ConfigDict(from_attributes=True)
