from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CourseBase(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10)
    category: str = Field(min_length=2, max_length=100)
    difficulty: str = Field(default="Beginner", max_length=50)


class CourseCreate(CourseBase):
    is_published: bool = False


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    category: Optional[str] = Field(None, min_length=2, max_length=100)
    difficulty: Optional[str] = Field(None, max_length=50)
    is_published: Optional[bool] = None


class InstructorSummary(BaseModel):
    id: int
    full_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class CourseResponse(CourseBase):
    id: int
    is_published: bool
    instructor_id: int
    instructor: Optional[InstructorSummary] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonOutlineItem(BaseModel):
    id: int
    course_id: int
    section_id: Optional[int] = None
    title: str
    video_url: Optional[str] = None
    order_index: int
    is_completed: bool = False

    model_config = ConfigDict(from_attributes=True)


class QuizOutlineItem(BaseModel):
    id: int
    course_id: int
    title: str
    description: Optional[str] = None
    passing_score: int
    is_published: bool = True
    time_limit_minutes: Optional[int] = None
    max_attempts: int = 3
    section_id: Optional[int] = None
    lesson_id: Optional[int] = None
    question_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class AssignmentOutlineItem(BaseModel):
    id: int
    course_id: int
    section_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    max_marks: int
    due_date: Optional[datetime] = None
    is_closed: bool = False
    my_status: Optional[str] = None
    my_grade: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class MaterialOutlineItem(BaseModel):
    id: int
    course_id: int
    section_id: Optional[int] = None
    lesson_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    original_filename: str
    mime_type: str
    file_size: int
    file_size_formatted: Optional[str] = None
    file_extension: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseDetailResponse(CourseResponse):
    lessons: List[LessonOutlineItem] = []
    quizzes: List[QuizOutlineItem] = []
    assignments: List[AssignmentOutlineItem] = []
    materials: List[MaterialOutlineItem] = []
    sections: List[Any] = []
    is_enrolled: bool = False
    enrollment_status: Optional[str] = None
    completion_percentage: float = 0.0
