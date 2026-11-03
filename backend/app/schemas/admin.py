from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.course import CourseResponse
from app.schemas.user import UserResponse


class AdminRecentActivity(BaseModel):
    activity_type: str  # user_registered, course_enrolled, course_created, quiz_attempt, assignment_submission
    title: str
    description: str
    timestamp: datetime
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    reference_id: Optional[int] = None


class PlatformStats(BaseModel):
    total_users: int
    total_students: int
    total_instructors: int
    total_admins: int
    total_courses: int
    published_courses: int
    total_enrollments: int
    total_quiz_attempts: int
    average_quiz_pass_rate: float
    total_assignments: int = 0
    total_submissions: int = 0
    total_learning_materials: int = 0
    recent_activities: List[AdminRecentActivity] = []


class PaginatedUserResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[UserResponse]


class AdminCourseItem(BaseModel):
    id: int
    title: str
    description: str
    category: str
    difficulty: str
    is_published: bool
    instructor_id: int
    instructor_name: str
    instructor_email: str
    enrolled_students_count: int = 0
    lesson_count: int = 0
    quiz_count: int = 0
    assignment_count: int = 0
    created_at: datetime
    updated_at: datetime


class PaginatedAdminCourseResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[AdminCourseItem]


class InstructorDashboardStats(BaseModel):
    total_courses: int
    published_courses: int
    total_students_enrolled: int
    total_quizzes: int
    average_student_progress: float
    recent_enrollments: List[dict] = []


class StudentDashboardStats(BaseModel):
    enrolled_courses_count: int
    completed_courses_count: int
    in_progress_courses_count: int
    total_quizzes_taken: int
    quizzes_passed: int
    average_quiz_score: float
    recent_quiz_results: List[dict] = []
