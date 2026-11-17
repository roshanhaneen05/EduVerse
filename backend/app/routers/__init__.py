from app.routers.admin import router as admin_router
from app.routers.ai import router as ai_router
from app.routers.assignments import router as assignments_router
from app.routers.auth import router as auth_router
from app.routers.courses import router as courses_router
from app.routers.enrollments import router as enrollments_router
from app.routers.health import router as health_router
from app.routers.instructor import router as instructor_router
from app.routers.instructor_admin import router as instructor_admin_router
from app.routers.instructor_teaching import router as instructor_teaching_router
from app.routers.lessons import router as lessons_router
from app.routers.materials import router as materials_router
from app.routers.announcements import router as announcements_router
from app.routers.discussions import router as discussions_router
from app.routers.notifications import router as notifications_router
from app.routers.quizzes import router as quizzes_router
from app.routers.student import router as student_router
from app.routers.student_ai_learning import router as student_ai_learning_router

__all__ = [
    "admin_router",
    "ai_router",
    "announcements_router",
    "assignments_router",
    "auth_router",
    "courses_router",
    "discussions_router",
    "enrollments_router",
    "health_router",
    "instructor_router",
    "instructor_admin_router",
    "instructor_teaching_router",
    "lessons_router",
    "materials_router",
    "notifications_router",
    "quizzes_router",
    "student_router",
    "student_ai_learning_router",
]
