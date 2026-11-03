from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AnnouncementAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str


class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, description="Announcement title")
    content: str = Field(..., min_length=5, description="Announcement body content")
    is_published: bool = Field(default=True, description="Whether the announcement is published to enrolled students")


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    content: Optional[str] = Field(None, min_length=5)
    is_published: Optional[bool] = None


class AnnouncementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    instructor_id: int
    title: str
    content: str
    is_published: bool
    created_at: datetime
    updated_at: datetime
    author: Optional[AnnouncementAuthor] = None

