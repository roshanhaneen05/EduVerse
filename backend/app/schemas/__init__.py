from app.schemas.common import HealthResponse, MessageResponse
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdateProfile,
    PasswordChange,
    UserAdminUpdate,
)
from app.schemas.auth import TokenResponse, TokenData
from app.schemas.course import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CourseDetailResponse,
)
from app.schemas.lesson import (
    LessonCreate,
    LessonUpdate,
    LessonResponse,
    LessonProgressResponse,
)
from app.schemas.enrollment import EnrollmentResponse
from app.schemas.quiz import (
    QuizCreate,
    QuizResponse,
    QuestionCreate,
    QuestionResponse,
    AnswerOptionCreate,
    AnswerOptionResponse,
    QuizSubmission,
    QuizAttemptResult,
    QuizAttemptSummary,
)
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    AIConversationSummary,
    AIConversationDetail,
)
from app.schemas.admin import (
    PlatformStats,
    InstructorDashboardStats,
    StudentDashboardStats,
)

__all__ = [
    "HealthResponse",
    "MessageResponse",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "UserUpdateProfile",
    "PasswordChange",
    "UserAdminUpdate",
    "TokenResponse",
    "TokenData",
    "CourseCreate",
    "CourseUpdate",
    "CourseResponse",
    "CourseDetailResponse",
    "LessonCreate",
    "LessonUpdate",
    "LessonResponse",
    "LessonProgressResponse",
    "EnrollmentResponse",
    "QuizCreate",
    "QuizResponse",
    "QuestionCreate",
    "QuestionResponse",
    "AnswerOptionCreate",
    "AnswerOptionResponse",
    "QuizSubmission",
    "QuizAttemptResult",
    "QuizAttemptSummary",
    "AIChatRequest",
    "AIChatResponse",
    "AIConversationSummary",
    "AIConversationDetail",
    "PlatformStats",
    "InstructorDashboardStats",
    "StudentDashboardStats",
]
