from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class QuizAnalyticsItem(BaseModel):
    quiz_id: int
    quiz_title: str
    passing_score: int
    total_questions: int
    time_limit_minutes: Optional[int] = None
    is_published: bool
    total_attempts: int
    unique_students_attempted: int
    pass_count: int
    fail_count: int
    pass_rate: float
    average_score: float

    model_config = ConfigDict(from_attributes=True)


class AssignmentAnalyticsItem(BaseModel):
    assignment_id: int
    title: str
    max_marks: int
    due_date: Optional[datetime] = None
    is_published: bool
    total_submissions: int
    pending_grading: int
    graded_count: int
    average_grade: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class CourseOverviewItem(BaseModel):
    course_id: int
    title: str
    category: str
    difficulty: str
    is_published: bool
    student_count: int
    lesson_count: int
    assignment_count: int
    quiz_count: int
    average_progress: float
    completion_rate: float
    pending_grading_count: int


class EnhancedInstructorDashboardStats(BaseModel):
    total_courses: int
    published_courses: int
    total_students_enrolled: int
    unique_students_count: int
    total_assignments: int
    total_assignment_submissions: int
    pending_grading_count: int
    total_quizzes: int
    total_quiz_attempts: int
    average_quiz_score: float
    average_student_progress: float
    completed_enrollments_count: int
    course_completion_rate: float
    recent_enrollments: List[dict] = []
    courses_overview: List[CourseOverviewItem] = []


class CourseAnalyticsResponse(BaseModel):
    course_id: int
    course_title: str
    category: str
    difficulty: str
    is_published: bool
    total_students: int
    total_lessons: int
    average_completion_percentage: float
    completed_students_count: int
    course_completion_rate: float
    total_assignments: int
    total_assignment_submissions: int
    pending_grading_count: int
    graded_submissions_count: int
    assignment_submission_rate: float
    average_assignment_grade: Optional[float] = None
    total_quizzes: int
    total_quiz_attempts: int
    average_quiz_score: float
    quiz_pass_rate: float
    quizzes_breakdown: List[QuizAnalyticsItem] = []
    assignments_breakdown: List[AssignmentAnalyticsItem] = []


class StudentPerformanceItem(BaseModel):
    student_id: int
    full_name: str
    email: str
    enrolled_at: datetime
    completion_percentage: float
    completed_lessons_count: int
    total_lessons_count: int
    assignments_submitted_count: int
    total_assignments_count: int
    pending_grading_count: int
    average_assignment_grade: Optional[float] = None
    quizzes_taken_count: int
    total_quizzes_count: int
    quizzes_passed_count: int
    average_quiz_score: Optional[float] = None
    status: str  # "Completed", "In Progress", "Needs Attention"
    assistance_reasons: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class CourseStudentReportResponse(BaseModel):
    course_id: int
    course_title: str
    total_students: int
    average_completion_percentage: float
    students: List[StudentPerformanceItem] = []


class StudentLessonProgressDetail(BaseModel):
    lesson_id: int
    title: str
    section_title: Optional[str] = None
    order_index: int
    is_completed: bool
    completed_at: Optional[datetime] = None


class StudentAssignmentSubmissionDetail(BaseModel):
    assignment_id: int
    title: str
    max_marks: int
    due_date: Optional[datetime] = None
    status: str  # "not_submitted", "submitted", "graded"
    is_submitted: bool
    submitted_at: Optional[datetime] = None
    grade: Optional[float] = None
    feedback: Optional[str] = None
    is_late: bool = False


class StudentQuizAttemptDetail(BaseModel):
    quiz_id: int
    title: str
    passing_score: int
    attempt_id: int
    attempt_number: int
    score: float
    passed: bool
    submitted_at: datetime


class StudentDetailedProgressResponse(BaseModel):
    student_id: int
    full_name: str
    email: str
    course_id: int
    course_title: str
    enrolled_at: datetime
    completion_percentage: float
    total_lessons: int
    completed_lessons: int
    total_assignments: int
    submitted_assignments: int
    average_assignment_grade: Optional[float] = None
    total_quizzes: int
    attempted_quizzes: int
    average_quiz_score: Optional[float] = None
    status: str
    assistance_reasons: List[str] = []
    lessons_progress: List[StudentLessonProgressDetail] = []
    assignment_submissions: List[StudentAssignmentSubmissionDetail] = []
    quiz_attempts: List[StudentQuizAttemptDetail] = []

