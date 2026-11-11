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
]
