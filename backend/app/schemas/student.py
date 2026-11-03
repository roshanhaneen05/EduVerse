from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.course import CourseResponse
from app.schemas.enrollment import EnrollmentResponse


class StudentRecentLessonActivity(BaseModel):
    lesson_id: int
    lesson_title: str
    course_id: int
    course_title: str
    is_completed: bool
    completed_at: Optional[datetime] = None
    updated_at: datetime


class StudentUpcomingDeadline(BaseModel):
    assignment_id: int
    assignment_title: str
    course_id: int
    course_title: str
    due_date: datetime
    max_marks: int
    is_submitted: bool
    submission_status: Optional[str] = None
    grade: Optional[float] = None


class StudentRecentGrade(BaseModel):
    assessment_type: str  # "quiz" or "assignment"
    title: str
    course_title: str
    score_or_grade: float
    max_score_or_grade: float
    percentage: float
    feedback: Optional[str] = None
    date: datetime
    passed: Optional[bool] = None
    reference_id: int


class EnrolledCourseDetail(BaseModel):
    enrollment_id: int
    course_id: int
    course_title: str
    course_category: str
    course_difficulty: str
    instructor_name: str
    instructor_email: str
    enrolled_at: datetime
    completion_percentage: float
    status: str  # "in_progress" or "completed"
    total_lessons: int
    completed_lessons: int
    remaining_lessons: int
    next_lesson_id: Optional[int] = None
    next_lesson_title: Optional[str] = None
    last_accessed_at: Optional[datetime] = None


class ContinueLearningResponse(BaseModel):
    course_id: int
    course_title: str
    next_lesson_id: Optional[int] = None
    next_lesson_title: Optional[str] = None
    is_course_completed: bool
    reason: str  # "latest_progress", "first_incomplete", "course_completed_first_lesson", "no_lessons"


class StudentAssignmentOverviewItem(BaseModel):
    assignment_id: int
    assignment_title: str
    course_id: int
    course_title: str
    instructions: str
    max_marks: int
    due_date: Optional[datetime] = None
    is_closed: bool
    submission_id: Optional[int] = None
    submission_status: str  # "not_submitted", "submitted", "graded", "past_due"
    submitted_at: Optional[datetime] = None
    is_late: bool = False
    grade: Optional[float] = None
    feedback: Optional[str] = None
    allow_resubmission: bool = True


class StudentQuizHistoryItem(BaseModel):
    attempt_id: int
    quiz_id: int
    quiz_title: str
    course_id: int
    course_title: str
    attempt_number: int
    score: float
    total_points: int
    passing_score: int
    passed: bool
    started_at: datetime
    submitted_at: Optional[datetime] = None
    max_attempts: int
    remaining_attempts: Optional[int] = None


class EnhancedStudentDashboardStats(BaseModel):
    enrolled_courses_count: int
    in_progress_courses_count: int
    completed_courses_count: int
    overall_progress_percentage: float
    total_quizzes_taken: int
    quizzes_passed: int
    average_quiz_score: float
    total_assignments_count: int = 0
    submitted_assignments_count: int = 0
    pending_assignments_count: int = 0


class EnhancedStudentDashboardResponse(BaseModel):
    stats: EnhancedStudentDashboardStats
    recently_accessed_lessons: List[StudentRecentLessonActivity] = []
    upcoming_deadlines: List[StudentUpcomingDeadline] = []
    recent_grades: List[StudentRecentGrade] = []
    recommended_courses: List[CourseResponse] = []
    enrolled_courses: List[EnrolledCourseDetail] = []

