from datetime import date, datetime
import math
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


EvaluationStatus = Literal["pending_review", "approved"]
PaperDifficulty = Literal["easy", "medium", "hard", "mixed"]
QuestionDifficulty = Literal["easy", "medium", "hard"]
QuestionType = Literal["mcq", "true_false", "short_answer", "long_answer", "fill_blank"]


class RubricCriterionInput(BaseModel):
    criterion_name: str = Field(min_length=2, max_length=255)
    maximum_marks: float = Field(gt=0, le=10000)
    description: str = Field(min_length=3, max_length=5000)
    guidelines: str = Field(default="", max_length=5000)


class RubricInput(BaseModel):
    expected_answer: str = Field(min_length=3, max_length=20000)
    criteria: list[RubricCriterionInput] = Field(min_length=1, max_length=30)


class RubricCriterionResponse(RubricCriterionInput):
    id: int
    order_index: int


class RubricResponse(BaseModel):
    assignment_id: int
    assignment_title: str
    max_marks: int
    expected_answer: str
    criteria: list[RubricCriterionResponse]


class GeneratedEvaluationCriterion(BaseModel):
    criterion_name: str = Field(min_length=2, max_length=255)
    maximum_marks: float = Field(gt=0)
    suggested_marks: float = Field(ge=0)
    feedback: str = Field(min_length=2, max_length=5000)


class GeneratedEvaluationPayload(BaseModel):
    criteria: list[GeneratedEvaluationCriterion] = Field(min_length=1, max_length=30)
    feedback: str = Field(min_length=3, max_length=15000)
    missing_concepts: list[str] = Field(default_factory=list, max_length=50)
    incorrect_explanations: list[str] = Field(default_factory=list, max_length=50)
    improvements: list[str] = Field(default_factory=list, max_length=50)


class EvaluationCriterionResponse(BaseModel):
    id: int
    criterion_name: str
    maximum_marks: float
    suggested_marks: float
    final_marks: Optional[float]
    feedback: str
    order_index: int


class AssignmentEvaluationResponse(BaseModel):
    id: int
    submission_id: int
    assignment_id: int
    assignment_title: str
    student_id: int
    student_name: str
    instructor_id: int
    ai_suggested_marks: float
    final_marks: Optional[float]
    ai_feedback: str
    instructor_feedback: Optional[str]
    evaluation_status: EvaluationStatus
    created_at: datetime
    approved_at: Optional[datetime]
    criteria: list[EvaluationCriterionResponse]


class EvaluationCriterionEdit(BaseModel):
    id: Optional[int] = None
    criterion_name: str = Field(min_length=2, max_length=255)
    maximum_marks: float = Field(gt=0)
    final_marks: float = Field(ge=0)
    feedback: str = Field(min_length=2, max_length=5000)


class EvaluationEdit(BaseModel):
    final_marks: float = Field(ge=0)
    instructor_feedback: str = Field(min_length=1, max_length=15000)
    criteria: list[EvaluationCriterionEdit] = Field(min_length=1, max_length=30)


class InstructorSubmissionItem(BaseModel):
    id: int
    assignment_id: int
    assignment_title: str
    course_id: int
    course_title: str
    student_id: int
    student_name: str
    student_email: str
    submission_text: str
    attachments_json: Optional[str]
    submitted_at: datetime
    status: str
    grade: Optional[float]
    max_marks: int
    latest_evaluation_id: Optional[int]
    evaluation_status: Optional[EvaluationStatus]


class InstructorCourseOption(BaseModel):
    id: int
    title: str


class PaperOutlineLesson(BaseModel):
    id: int
    title: str


class PaperOutlineSection(BaseModel):
    id: int
    title: str
    lessons: list[PaperOutlineLesson]


class PaperOutlineResponse(BaseModel):
    course_id: int
    sections: list[PaperOutlineSection]


class QuestionPaperGenerationRequest(BaseModel):
    course_id: int = Field(gt=0)
    section_ids: list[int] = Field(min_length=1, max_length=50)
    lesson_ids: list[int] = Field(min_length=1, max_length=200)
    title: str = Field(min_length=3, max_length=255)
    difficulty: PaperDifficulty
    question_types: list[QuestionType] = Field(min_length=1, max_length=5)
    question_count: int = Field(ge=1, le=100)
    total_marks: float = Field(gt=0, le=10000)
    duration_minutes: int = Field(ge=1, le=600)
    exam_date: Optional[date] = None

    @model_validator(mode="after")
    def selections_are_unique(self):
        if len(set(self.section_ids)) != len(self.section_ids):
            raise ValueError("Selected modules must be unique.")
        if len(set(self.lesson_ids)) != len(self.lesson_ids):
            raise ValueError("Selected lessons must be unique.")
        if len(set(self.question_types)) != len(self.question_types):
            raise ValueError("Question types must be unique.")
        return self


class PaperQuestionInput(BaseModel):
    question_text: str = Field(min_length=5, max_length=5000)
    question_type: QuestionType
    difficulty: QuestionDifficulty
    marks: float = Field(gt=0, le=10000)
    options: list[str] = Field(default_factory=list, max_length=20)
    correct_answer: str = Field(min_length=1, max_length=10000)
    explanation: str = Field(min_length=2, max_length=10000)
    question_order: int = Field(ge=1, le=100)


class GeneratedPaperQuestion(PaperQuestionInput):
    pass


class PaperQuestionResponse(PaperQuestionInput):
    id: int


class GeneratedQuestionPaperPayload(BaseModel):
    questions: list[GeneratedPaperQuestion] = Field(min_length=1, max_length=100)


class QuestionPaperUpdate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    total_marks: float = Field(gt=0, le=10000)
    duration_minutes: int = Field(ge=1, le=600)
    difficulty: PaperDifficulty
    exam_date: Optional[date] = None
    questions: list[PaperQuestionInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_order_and_marks(self):
        if not math.isclose(sum(item.marks for item in self.questions), self.total_marks, abs_tol=0.01):
            raise ValueError("Question marks must add up to the paper's total marks.")
        orders = [item.question_order for item in self.questions]
        if len(set(orders)) != len(orders):
            raise ValueError("Question order values must be unique.")
        return self


class QuestionPaperResponse(BaseModel):
    id: int
    course_id: int
    course_title: str
    title: str
    total_marks: float
    duration_minutes: int
    difficulty: PaperDifficulty
    section_ids: list[int]
    lesson_ids: list[int]
    exam_date: Optional[date]
    status: Literal["draft", "published"]
    created_at: datetime
    updated_at: datetime
    questions: list[PaperQuestionResponse]


class QuestionPaperSummary(BaseModel):
    id: int
    course_id: int
    course_title: str
    title: str
    total_marks: float
    duration_minutes: int
    difficulty: PaperDifficulty
    status: Literal["draft", "published"]
    exam_date: Optional[date]
    updated_at: datetime
