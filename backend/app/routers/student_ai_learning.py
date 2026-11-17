from typing import List

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_student
from app.models.ai_learning import AIQuiz, AIQuizAttempt
from app.models.user import User
from app.schemas.ai_learning import (
    AICourseOutline,
    AIQuizAttemptResponse,
    AIQuizGenerationRequest,
    AIQuizGeneratedResponse,
    AIQuizHistoryItem,
    AIQuizReviewRequestResponse,
    AIQuizStartResponse,
    AIQuizSubmitRequest,
    StudyPlanDashboardResponse,
    StudyPlanGenerationRequest,
    StudyPlanGenerationResponse,
    StudyPreferenceResponse,
    StudyReminderResponse,
    StudyTaskRescheduleRequest,
    StudyTaskResponse,
    StudyTaskStatusUpdate,
)
from app.services.ai_quiz_service import (
    generate_quiz,
    get_quiz_attempt_review,
    get_quiz_history,
    get_student_course_outline,
    request_instructor_review,
    start_quiz_attempt,
    submit_quiz_attempt,
)
from app.services.study_planner_service import (
    delete_study_task,
    generate_study_plan,
    get_planner_dashboard,
    mark_study_reminder_read,
    reschedule_study_task,
    save_study_preferences,
    serialize_study_task,
    update_study_task_status,
)


router = APIRouter(prefix="/student/ai-learning", tags=["Student AI Learning Tools"])


def _quiz_response(quiz: AIQuiz) -> dict:
    return {
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "course_id": quiz.course_id,
            "course_title": quiz.course.title,
            "section_id": quiz.section_id,
            "lesson_id": quiz.lesson_id,
            "difficulty": quiz.difficulty,
            "question_type": quiz.question_type,
            "question_count": quiz.question_count,
            "created_at": quiz.created_at,
        },
        "questions": [
            {
                "id": question.id,
                "question": question.question_text,
                "question_type": question.question_type,
                "options": [
                    {"id": option.id, "text": option.option_text}
                    for option in question.options
                ],
                "difficulty": question.difficulty,
                "order_index": question.order_index,
            }
            for question in quiz.questions
        ],
    }


def _attempt_response(attempt: AIQuizAttempt) -> dict:
    return {
        "id": attempt.id,
        "quiz_id": attempt.quiz_id,
        "quiz_title": attempt.quiz.title,
        "course_title": attempt.quiz.course.title,
        "started_at": attempt.started_at,
        "submitted_at": attempt.submitted_at,
        "awarded_points": attempt.awarded_points,
        "total_points": attempt.total_points,
        "percentage": attempt.percentage,
        "duration_seconds": attempt.duration_seconds,
        "performance_level": attempt.performance_level,
        "review_requested_at": attempt.review_requested_at,
        "answers": [
            {
                "question_id": answer.question_id,
                "question": answer.question.question_text,
                "question_type": answer.question.question_type,
                "submitted_answer": (
                    answer.answer_text
                    if answer.question.question_type == "short_answer"
                    else answer.selected_option.option_text if answer.selected_option else None
                ),
                "correct_answer": answer.question.correct_answer,
                "is_correct": answer.is_correct,
                "awarded_points": answer.awarded_points,
                "total_points": answer.question.points,
                "explanation": answer.question.explanation,
                "automated_evaluation": answer.question.question_type == "short_answer",
                "automated_feedback": answer.automated_feedback,
            }
            for answer in attempt.answers
        ],
    }


@router.get("/courses", response_model=List[AICourseOutline])
def list_ai_learning_courses(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return get_student_course_outline(db, current_user.id)


@router.post("/quizzes", response_model=AIQuizGeneratedResponse, status_code=status.HTTP_201_CREATED)
def create_ai_quiz(
    request: AIQuizGenerationRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return _quiz_response(generate_quiz(db, current_user.id, request))


@router.post("/quizzes/{quiz_id}/attempts", response_model=AIQuizStartResponse, status_code=status.HTTP_201_CREATED)
def begin_ai_quiz_attempt(
    quiz_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    attempt = start_quiz_attempt(db, current_user.id, quiz_id)
    return {"attempt_id": attempt.id, "started_at": attempt.started_at}


@router.post("/attempts/{attempt_id}/submit", response_model=AIQuizAttemptResponse)
def submit_ai_quiz_attempt(
    attempt_id: int,
    request: AIQuizSubmitRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    attempt = submit_quiz_attempt(db, current_user.id, attempt_id, request)
    return _attempt_response(attempt)


@router.get("/attempts/{attempt_id}", response_model=AIQuizAttemptResponse)
def review_ai_quiz_attempt(
    attempt_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    attempt = get_quiz_attempt_review(db, current_user.id, attempt_id)
    return _attempt_response(attempt)


@router.get("/quizzes/history", response_model=List[AIQuizHistoryItem])
def list_ai_quiz_history(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return get_quiz_history(db, current_user.id)


@router.post("/attempts/{attempt_id}/request-review", response_model=AIQuizReviewRequestResponse)
def ask_for_instructor_review(
    attempt_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    requested_at = request_instructor_review(db, current_user.id, attempt_id)
    return {
        "message": "Your instructor has been notified and can review the automated short-answer grading.",
        "review_requested_at": requested_at,
    }


@router.get("/planner", response_model=StudyPlanDashboardResponse)
def get_study_planner_dashboard(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return get_planner_dashboard(db, current_user.id)


@router.put("/planner/preferences", response_model=StudyPreferenceResponse)
def update_study_preferences(
    request: StudyPlanGenerationRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    return save_study_preferences(db, current_user.id, request)


@router.post("/planner/generate", response_model=StudyPlanGenerationResponse, status_code=status.HTTP_201_CREATED)
def create_study_plan(
    request: StudyPlanGenerationRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    generate_study_plan(db, current_user.id, request)
    return get_planner_dashboard(db, current_user.id)


@router.patch("/planner/tasks/{task_id}", response_model=StudyTaskResponse)
def complete_study_task(
    task_id: int,
    request: StudyTaskStatusUpdate,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    task = update_study_task_status(db, current_user.id, task_id)
    return serialize_study_task(task)


@router.put("/planner/tasks/{task_id}/schedule", response_model=StudyTaskResponse)
def move_study_task(
    task_id: int,
    request: StudyTaskRescheduleRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    task = reschedule_study_task(db, current_user.id, task_id, request.scheduled_at)
    return serialize_study_task(task)


@router.delete("/planner/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_study_task(
    task_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    delete_study_task(db, current_user.id, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/planner/reminders/{reminder_id}/read", response_model=StudyReminderResponse)
def read_study_reminder(
    reminder_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    reminder = mark_study_reminder_read(db, current_user.id, reminder_id)
    return {
        "id": reminder.id,
        "notification_type": reminder.notification_type,
        "message": reminder.message,
        "remind_at": reminder.remind_at,
        "is_read": reminder.is_read,
        "task_id": reminder.task_id,
        "deadline_id": reminder.deadline_id,
    }
