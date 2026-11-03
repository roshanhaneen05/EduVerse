from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.ai import AIConversation
from app.models.user import User
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    AIConversationDetail,
    AIConversationSummary,
    LessonSummaryResponse,
    PracticeQuestionsResponse,
    StudyRecommendationsResponse,
)
from app.schemas.common import MessageResponse
from app.services.ai_service import (
    generate_practice_questions_service,
    get_conversation_detail,
    get_student_study_recommendations,
    handle_ai_chat,
    list_user_conversations,
    summarize_lesson_service,
)

router = APIRouter(prefix="/ai", tags=["AI Learning Assistant"])


@router.post(
    "/chat",
    response_model=AIChatResponse,
    summary="Ask a question or request explanations from the AI Learning Assistant",
)
def chat_with_assistant(
    request: AIChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return handle_ai_chat(db, current_user, request)


@router.post(
    "/lessons/{lesson_id}/summarize",
    response_model=LessonSummaryResponse,
    summary="Generate a concise extractive summary of real lesson content",
)
def summarize_lesson_endpoint(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return summarize_lesson_service(db, lesson_id, current_user)


@router.post(
    "/lessons/{lesson_id}/practice-questions",
    response_model=PracticeQuestionsResponse,
    summary="Generate self-assessment practice questions strictly from lesson text",
)
def generate_practice_questions_endpoint(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return generate_practice_questions_service(db, lesson_id, current_user)


@router.get(
    "/study-recommendations",
    response_model=StudyRecommendationsResponse,
    summary="Get personalized study suggestions based on student's actual course progress and assessment history",
)
def get_study_recommendations_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_student_study_recommendations(db, current_user.id)


@router.get(
    "/conversations",
    summary="List past AI conversations for current user",
)
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_user_conversations(db, current_user.id)


@router.get(
    "/conversations/{conversation_id}",
    summary="Get message history for a specific conversation",
)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    detail = get_conversation_detail(db, conversation_id, current_user.id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return detail


@router.delete(
    "/conversations/{conversation_id}",
    response_model=MessageResponse,
    summary="Delete a conversation",
)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = db.query(AIConversation).filter(AIConversation.id == conversation_id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    if c.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this conversation.")
    db.delete(c)
    db.commit()
    return MessageResponse(message="Conversation deleted.")
