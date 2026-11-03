from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class AIChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000, description="User question or prompt")
    course_id: Optional[int] = Field(None, description="Optional course context ID")
    lesson_id: Optional[int] = Field(None, description="Optional lesson context ID for deep grounding")
    conversation_id: Optional[int] = Field(None, description="Existing conversation ID to continue")


class AIChatResponse(BaseModel):
    conversation_id: int
    message: str
    provider: str
    is_fallback: bool
    grounded_in: Optional[str] = None
    is_course_grounded: bool = False
    suggestions: List[str] = []
    created_at: datetime

    @computed_field
    @property
    def response(self) -> str:
        """Alias for backwards compatibility with frontend models."""
        return self.message


class AIMessageCreate(BaseModel):
    role: str = Field(description="'user', 'assistant', or 'system'")
    content: str = Field(min_length=1)


class AIMessageResponse(AIMessageCreate):
    id: int
    conversation_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", max_length=255)
    course_id: Optional[int] = None


class AIConversationResponse(BaseModel):
    id: int
    user_id: int
    course_id: Optional[int] = None
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[AIMessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AIConversationSummary(BaseModel):
    id: int
    title: str
    course_id: Optional[int] = None
    message_count: int
    created_at: datetime
    updated_at: datetime


class AIConversationDetail(BaseModel):
    id: int
    title: str
    course_id: Optional[int] = None
    messages: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# Phase 9: Summarization, Practice Questions & Study Recommendations Schemas
# ==============================================================================


class LessonSummaryResponse(BaseModel):
    lesson_id: int
    lesson_title: str
    course_id: int
    course_title: str
    summary: str
    key_takeaways: List[str]
    word_count: int
    provider: str
    generated_at: datetime


class PracticeQuestionItem(BaseModel):
    id: int
    question: str
    options: List[str] = Field(min_length=2, max_length=5)
    correct_index: int = Field(ge=0, le=4)
    explanation: str
    concept_tested: str


class PracticeQuestionsResponse(BaseModel):
    lesson_id: Optional[int] = None
    lesson_title: Optional[str] = None
    course_id: int
    course_title: str
    questions: List[PracticeQuestionItem]
    disclaimer: str = (
        "These AI-generated practice questions are for study and self-assessment only "
        "and are not official course exam questions."
    )
    provider: str
    generated_at: datetime


class StudyRecommendationItem(BaseModel):
    id: str
    type: str  # "continue_lesson", "review_quiz", "assignment_due", "take_quiz"
    priority: str  # "urgent", "high", "medium", "low"
    title: str
    description: str
    action_url: str
    course_id: int
    course_title: str
    context_meta: Optional[Dict[str, Any]] = None


class StudyRecommendationsResponse(BaseModel):
    student_id: int
    total_recommendations: int
    recommendations: List[StudyRecommendationItem]
    advisory_notice: str = (
        "Recommendations are advisory educational suggestions calculated from your real progress "
        "and assessment records to guide your self-paced learning."
    )
    generated_at: datetime
