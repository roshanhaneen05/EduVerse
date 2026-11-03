from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DiscussionAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str


class ReplyCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Reply content")
    parent_reply_id: Optional[int] = Field(None, description="Optional parent reply ID for threaded discussion")


class ReplyUpdate(BaseModel):
    content: str = Field(..., min_length=1, description="Updated reply content")


class ReplyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: int
    user_id: int
    parent_reply_id: Optional[int] = None
    content: str
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime
    author: Optional[DiscussionAuthor] = None


class DiscussionCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Discussion thread title")
    content: str = Field(..., min_length=5, description="Opening discussion post content")


class DiscussionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    content: Optional[str] = Field(None, min_length=5)


class DiscussionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    user_id: int
    title: str
    content: str
    is_pinned: bool = False
    is_deleted: bool = False
    reply_count: int = 0
    created_at: datetime
    updated_at: datetime
    author: Optional[DiscussionAuthor] = None


class DiscussionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    user_id: int
    title: str
    content: str
    is_pinned: bool = False
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime
    author: Optional[DiscussionAuthor] = None
    replies: List[ReplyResponse] = []


class PaginatedDiscussionsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[DiscussionListItem]

