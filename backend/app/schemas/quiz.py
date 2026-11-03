from datetime import datetime
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class AnswerOptionBase(BaseModel):
    option_text: str = Field(min_length=1)


class AnswerOptionCreate(AnswerOptionBase):
    is_correct: bool = False


class AnswerOptionResponse(AnswerOptionBase):
    """Public / student view - completely excludes is_correct."""
    id: int
    question_id: int

    model_config = ConfigDict(from_attributes=True)


class AnswerOptionDetail(AnswerOptionBase):
    """Internal / management view with answer key."""
    id: int
    question_id: int
    is_correct: bool

    model_config = ConfigDict(from_attributes=True)


class QuestionBase(BaseModel):
    question_text: str = Field(min_length=3)
    order_index: int = Field(default=1, ge=1)
    points: int = Field(default=1, ge=1)


class QuestionCreate(QuestionBase):
    options: List[AnswerOptionCreate] = Field(min_length=2)


class QuestionResponse(QuestionBase):
    """Student view - options do not include is_correct."""
    id: int
    quiz_id: int
    options: List[AnswerOptionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class QuestionDetail(QuestionBase):
    """Instructor view with answer keys."""
    id: int
    quiz_id: int
    options: List[AnswerOptionDetail] = []

    model_config = ConfigDict(from_attributes=True)


class QuizBase(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: Optional[str] = None
    passing_score: int = Field(default=70, ge=0, le=100)
    is_published: bool = False
    time_limit_minutes: Optional[int] = Field(default=None, ge=1)
    max_attempts: int = Field(default=3, ge=0)
    section_id: Optional[int] = None
    lesson_id: Optional[int] = None


class QuizCreate(QuizBase):
    questions: List[QuestionCreate] = []


class QuizUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=255)
    description: Optional[str] = None
    passing_score: Optional[int] = Field(default=None, ge=0, le=100)
    is_published: Optional[bool] = None
    time_limit_minutes: Optional[int] = Field(default=None, ge=1)
    max_attempts: Optional[int] = Field(default=None, ge=0)
    section_id: Optional[int] = None
    lesson_id: Optional[int] = None


class QuizResponse(QuizBase):
    id: int
    course_id: int
    created_at: datetime
    updated_at: datetime
    questions: List[QuestionResponse] = []
    attempts_count: Optional[int] = 0
    can_attempt: Optional[bool] = True
    best_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class QuizDetail(QuizBase):
    """Instructor view with answer keys and statistics."""
    id: int
    course_id: int
    created_at: datetime
    updated_at: datetime
    questions: List[QuestionDetail] = []
    total_attempts: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class QuizStartResponse(BaseModel):
    attempt_id: int
    quiz_id: int
    attempt_number: int
    max_attempts: int
    time_limit_minutes: Optional[int] = None
    started_at: datetime
    expires_at: Optional[datetime] = None


class QuizAnswerItem(BaseModel):
    question_id: int
    selected_option_id: int


class QuizSubmission(BaseModel):
    attempt_id: Optional[int] = None
    answers: Union[Dict[int, int], List[QuizAnswerItem]]


class QuestionReviewItem(BaseModel):
    question_id: int
    question_text: str
    selected_option_id: Optional[int] = None
    correct_option_id: int
    is_correct: bool


class QuizAttemptAnswerReview(BaseModel):
    question_id: int
    question_text: str
    selected_option_id: Optional[int] = None
    selected_option_text: Optional[str] = None
    correct_option_id: int
    correct_option_text: str = ""
    is_correct: bool = False
    awarded_points: int = 0
    points: int = 1


class QuizAttemptResult(BaseModel):
    id: int
    attempt_id: Optional[int] = None
    quiz_id: Optional[int] = None
    quiz_title: str = ""
    student_id: Optional[int] = None
    attempt_number: int = 1
    score: float
    total_points: int
    total_questions: int = 0
    passing_score: int = 70
    passed: bool
    started_at: datetime
    submitted_at: datetime
    answers: List[QuizAttemptAnswerReview] = []
    questions_review: List[QuestionReviewItem] = []

    model_config = ConfigDict(from_attributes=True)


class QuizAttemptSummary(BaseModel):
    id: int
    quiz_id: Optional[int] = None
    quiz_title: str
    course_id: Optional[int] = None
    score: float
    total_points: int
    passed: bool
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)
