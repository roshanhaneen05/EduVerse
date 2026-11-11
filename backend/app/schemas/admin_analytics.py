from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AdminAnalyticsOverview(BaseModel):
    total_registered_students: int
    total_registered_instructors: int
    total_published_courses: int
    total_enrollments: int
    total_completed_courses: int
    total_active_users: int


class StudentMetric(BaseModel):
    name: str
    enrollment_count: int
    average_completion_rate: float


class AdminStudentAnalytics(BaseModel):
    total_students: int
    new_student_registrations: int
    active_students: int
    inactive_students: int
    total_enrollments: int
    average_enrollments_per_student: float
    top_students: List[StudentMetric] = Field(default_factory=list)
    highest_completion_students: List[StudentMetric] = Field(default_factory=list)


class CourseMetric(BaseModel):
    course_id: int
    course_name: str
    instructor_name: Optional[str] = None
    category: str
    is_published: bool
    enrollment_count: int
    completed_enrollments: int
    completion_rate: float


class CourseCategoryMetric(BaseModel):
    category: str
    course_count: int


class AdminCourseAnalytics(BaseModel):
    total_courses: int
    published_courses: int
    unpublished_courses: int
    categories: List[CourseCategoryMetric] = Field(default_factory=list)
    courses: List[CourseMetric] = Field(default_factory=list)
    most_popular_courses: List[CourseMetric] = Field(default_factory=list)
    least_enrolled_courses: List[CourseMetric] = Field(default_factory=list)
    highest_completion_courses: List[CourseMetric] = Field(default_factory=list)


class InstructorMetric(BaseModel):
    name: str
    course_count: int
    student_enrollments: int
    period_course_creations: int
    period_enrollments: int


class AdminInstructorAnalytics(BaseModel):
    total_instructors: int
    instructors: List[InstructorMetric] = Field(default_factory=list)
    popular_courses: List[CourseMetric] = Field(default_factory=list)


class MonthlyAnalyticsPoint(BaseModel):
    month: str
    student_registrations: int
    enrollments: int
    active_students: int


class AdminAnalyticsTrends(BaseModel):
    monthly: List[MonthlyAnalyticsPoint] = Field(default_factory=list)


class AdminAnalyticsActivity(BaseModel):
    activity_type: str
    activity_name: str
    user_name: str
    date: datetime


class AdminAnalyticsDashboard(BaseModel):
    overview: AdminAnalyticsOverview
    students: AdminStudentAnalytics
    courses: AdminCourseAnalytics
    instructors: AdminInstructorAnalytics
    trends: AdminAnalyticsTrends
    recent_activities: List[AdminAnalyticsActivity] = Field(default_factory=list)
