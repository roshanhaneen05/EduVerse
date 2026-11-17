from datetime import date, datetime, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator


QuizDifficulty = Literal["easy", "medium", "hard"]
QuizQuestionType = Literal["mcq", "true_false", "short_answer", "mixed"]
QuestionKind = Literal["mcq", "true_false", "short_answer"]
StudyPriority = Literal["high", "medium", "low"]
StudyTaskStatus = Literal["pending", "completed", "missed"]
PreferredStudyTime = Literal["morning", "afternoon", "evening", "night"]


class AIQuizGenerationRequest(BaseModel):
    course_id: int = Field(gt=0)
    section_id: Optional[int] = Field(default=None, gt=0)
    lesson_id: Optional[int] = Field(default=None, gt=0)
    difficulty: QuizDifficulty
    question_count: Literal[5, 10, 15, 20]
    question_type: QuizQuestionType

    @model_validator(mode="after")
    def require_one_content_scope(self):
        if (self.section_id is None) == (self.lesson_id is None):
            raise ValueError("Select exactly one module or lesson.")
        return self


class GeneratedQuizOption(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class GeneratedQuizQuestion(BaseModel):
    question: str = Field(min_length=5, max_length=3000)
    question_type: QuestionKind
    options: list[GeneratedQuizOption] = Field(default_factory=list)
    correct_answer: str = Field(min_length=1, max_length=3000)
    explanation: str = Field(min_length=3, max_length=3000)
    difficulty: QuizDifficulty

    @field_validator("options", mode="before")
    @classmethod
    def normalize_option_strings(cls, value):
        if isinstance(value, list):
            return [{"text": option} if isinstance(option, str) else option for option in value]
        return value


class GeneratedQuizPayload(BaseModel):
    questions: list[GeneratedQuizQuestion]


class AIQuizOptionView(BaseModel):
    id: int
    text: str


class AIQuizQuestionView(BaseModel):
    id: int
    question: str
    question_type: QuestionKind
    options: list[AIQuizOptionView]
    difficulty: QuizDifficulty
    order_index: int


class AIQuizSummary(BaseModel):
    id: int
    title: str
    course_id: int
    course_title: str
    section_id: Optional[int]
    lesson_id: Optional[int]
    difficulty: QuizDifficulty
    question_type: QuizQuestionType
    question_count: int
    created_at: datetime


class AIQuizGeneratedResponse(BaseModel):
    quiz: AIQuizSummary
    questions: list[AIQuizQuestionView]


class AIQuizStartResponse(BaseModel):
    attempt_id: int
    started_at: datetime


class AIQuizAnswerSubmission(BaseModel):
    question_id: int = Field(gt=0)
    selected_option_id: Optional[int] = Field(default=None, gt=0)
    answer_text: Optional[str] = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def require_answer_shape(self):
        if self.selected_option_id is not None and self.answer_text is not None:
            raise ValueError("Provide either an option selection or a written answer, not both.")
        return self


class AIQuizSubmitRequest(BaseModel):
    answers: list[AIQuizAnswerSubmission]


class AIQuizAnswerReview(BaseModel):
    question_id: int
    question: str
    question_type: QuestionKind
    submitted_answer: Optional[str]
    correct_answer: str
    is_correct: bool
    awarded_points: float
    total_points: float
    explanation: str
    automated_evaluation: bool
    automated_feedback: Optional[str]


class AIQuizAttemptResponse(BaseModel):
    id: int
    quiz_id: int
    quiz_title: str
    course_title: str
    started_at: datetime
    submitted_at: Optional[datetime]
    awarded_points: float
    total_points: float
    percentage: float
    duration_seconds: Optional[int]
    performance_level: Optional[str]
    review_requested_at: Optional[datetime]
    answers: list[AIQuizAnswerReview] = Field(default_factory=list)


class AIQuizHistoryItem(BaseModel):
    attempt_id: int
    quiz_id: int
    quiz_name: str
    course_name: str
    attempted_at: datetime
    total_marks: float
    awarded_marks: float
    percentage: float
    difficulty: QuizDifficulty
    time_taken_seconds: Optional[int]


class AIQuizReviewRequestResponse(BaseModel):
    message: str
    review_requested_at: datetime


class AILessonOutline(BaseModel):
    id: int
    title: str
    order_index: int


class AISectionOutline(BaseModel):
    id: int
    title: str
    order_index: int
    lessons: list[AILessonOutline]


class AICourseOutline(BaseModel):
    id: int
    title: str
    sections: list[AISectionOutline]
    lessons: list[AILessonOutline]


class AIPlannerDeadlineInput(BaseModel):
    course_id: int = Field(gt=0)
    title: str = Field(min_length=2, max_length=255)
    deadline_type: Literal["exam", "deadline"] = "exam"
    due_at: datetime


class StudyPlanGenerationRequest(BaseModel):
    course_ids: list[int] = Field(min_length=1, max_length=20)
    available_hours_per_day: float = Field(ge=0.25, le=16)
    preferred_time: PreferredStudyTime
    time_zone: str = Field(default="UTC", min_length=1, max_length=64)
    daily_duration_minutes: int = Field(ge=15, le=240)
    target_completion_date: date
    deadlines: list[AIPlannerDeadlineInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_plan_preferences(self):
        if len(set(self.course_ids)) != len(self.course_ids):
            raise ValueError("Course selections must be unique.")
        if self.target_completion_date <= date.today():
            raise ValueError("Target completion date must be in the future.")
        if any(deadline.course_id not in self.course_ids for deadline in self.deadlines):
            raise ValueError("Each deadline must belong to a selected course.")
        try:
            ZoneInfo(self.time_zone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Choose a valid time zone.") from exc
        now = datetime.now(timezone.utc)
        for deadline in self.deadlines:
            if deadline.due_at.tzinfo is None:
                deadline.due_at = deadline.due_at.replace(tzinfo=timezone.utc)
            if deadline.due_at <= now:
                raise ValueError("Exam and deadline dates must be in the future.")
        return self


class StudyPreferenceResponse(BaseModel):
    course_ids: list[int]
    deadlines: list[AIPlannerDeadlineInput]
    available_hours_per_day: float
    preferred_time: PreferredStudyTime
    time_zone: str
    daily_duration_minutes: int
    target_completion_date: Optional[date]


class GeneratedStudyTask(BaseModel):
    lesson_id: int = Field(gt=0)
    duration_minutes: int = Field(ge=15, le=240)
    priority: StudyPriority
    rationale: str = Field(min_length=3, max_length=1000)


class GeneratedStudyPlanPayload(BaseModel):
    tasks: list[GeneratedStudyTask]
    recommendations: list[str] = Field(min_length=1, max_length=10)


class StudyTaskResponse(BaseModel):
    id: int
    course_id: int
    course_name: str
    section_name: Optional[str]
    lesson_id: int
    lesson_name: str
    scheduled_at: datetime
    scheduled_date: date
    start_time: str
    end_time: str
    duration_minutes: int
    priority: StudyPriority
    status: StudyTaskStatus
    rationale: str
    completed_at: Optional[datetime]


class StudyTaskStatusUpdate(BaseModel):
    status: Literal["completed"]


class StudyTaskRescheduleRequest(BaseModel):
    scheduled_at: datetime


class StudyReminderResponse(BaseModel):
    id: int
    notification_type: str
    message: str
    remind_at: datetime
    is_read: bool
    task_id: Optional[int]
    deadline_id: Optional[int]


class StudyDeadlineResponse(BaseModel):
    id: Optional[int] = None
    course_id: int
    title: str
    deadline_type: Literal["exam", "deadline"]
    due_at: datetime


class StudyCourseProgress(BaseModel):
    course_id: int
    course_name: str
    completed_lessons: int
    total_lessons: int
    completion_percentage: float


class StudyPlanDashboardResponse(BaseModel):
    preferences: Optional[StudyPreferenceResponse]
    plan_id: Optional[int]
    generation_mode: Optional[Literal["ai", "rules"]]
    target_completion_date: Optional[date]
    tasks: list[StudyTaskResponse]
    deadlines: list[StudyDeadlineResponse]
    course_progress: list["StudyCourseProgress"]
    recommendations: list[str]
    reminders: list[StudyReminderResponse]
    overall_progress: float


class StudyPlanGenerationResponse(StudyPlanDashboardResponse):
    pass


