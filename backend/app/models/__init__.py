from app.models.user import User, UserRole
from app.models.course import Course
from app.models.section import CourseSection
from app.models.lesson import Lesson, LessonProgress
from app.models.enrollment import CourseEnrollment
from app.models.quiz import (
    Quiz,
    Question,
    AnswerOption,
    QuizAttempt,
    QuizAttemptAnswer,
)
from app.models.ai import AIConversation, AIMessage
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.material import LearningMaterial
from app.models.announcement import CourseAnnouncement
from app.models.discussion import CourseDiscussion, DiscussionReply
from app.models.notification import Notification
from app.models.email_delivery import EmailDelivery
from app.models.instructor import InstructorPasswordToken, InstructorProfile
from app.models.ai_learning import (
    AIQuiz,
    AIQuizAnswer,
    AIQuizAttempt,
    AIQuizOption,
    AIQuizQuestion,
    StudyDeadline,
    StudyNotification,
    StudyPlan,
    StudyPreference,
    StudyTask,
)
from app.models.instructor_ai import (
    AssignmentEvaluation,
    AssignmentEvaluationCriterion,
    AssignmentRubric,
    EvaluationCriterionRubric,
    GeneratedQuestion,
    QuestionPaper,
)

__all__ = [
    "User",
    "UserRole",
    "Course",
    "CourseSection",
    "Lesson",
    "LessonProgress",
    "CourseEnrollment",
    "Quiz",
    "Question",
    "AnswerOption",
    "QuizAttempt",
    "QuizAttemptAnswer",
    "AIConversation",
    "AIMessage",
    "Assignment",
    "AssignmentSubmission",
    "LearningMaterial",
    "CourseAnnouncement",
    "CourseDiscussion",
    "DiscussionReply",
    "Notification",
    "EmailDelivery",
    "InstructorProfile",
    "InstructorPasswordToken",
    "AIQuiz",
    "AIQuizQuestion",
    "AIQuizOption",
    "AIQuizAttempt",
    "AIQuizAnswer",
    "StudyPreference",
    "StudyPlan",
    "StudyDeadline",
    "StudyTask",
    "StudyNotification",
    "AssignmentRubric",
    "EvaluationCriterionRubric",
    "AssignmentEvaluation",
    "AssignmentEvaluationCriterion",
    "QuestionPaper",
    "GeneratedQuestion",
]
