from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.course import LessonOutlineItem


class SectionBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    order_index: int = Field(default=1, ge=1)


class SectionCreate(SectionBase):
    pass


class SectionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    order_index: Optional[int] = Field(None, ge=1)


class SectionOrderUpdate(BaseModel):
    section_id: int
    order_index: int = Field(ge=1)


class LessonAssignSection(BaseModel):
    section_id: Optional[int] = None
    order_index: Optional[int] = Field(None, ge=1)


class SectionResponse(SectionBase):
    id: int
    course_id: int
    lesson_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SectionDetailResponse(SectionResponse):
    lessons: List[LessonOutlineItem] = []

