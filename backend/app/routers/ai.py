from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, get_mongo_db
from app.repositories.user_repository import MongoUser
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    LessonSummaryResponse,
    PracticeQuestionsResponse,
    StudyRecommendationsResponse,
)
from app.schemas.common import MessageResponse
from app.services.ai_service import (
    delete_user_conversation,
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
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return handle_ai_chat(mongo_db, current_user, request, sqlite_db=db)


@router.post(
    "/lessons/{lesson_id}/summarize",
    response_model=LessonSummaryResponse,
    summary="Generate a concise extractive summary of real lesson content",
)
def summarize_lesson_endpoint(
    lesson_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return summarize_lesson_service(mongo_db, lesson_id, current_user)


@router.post(
    "/lessons/{lesson_id}/practice-questions",
    response_model=PracticeQuestionsResponse,
    summary="Generate self-assessment practice questions strictly from lesson text",
)
def generate_practice_questions_endpoint(
    lesson_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return generate_practice_questions_service(mongo_db, lesson_id, current_user)


@router.get(
    "/study-recommendations",
    response_model=StudyRecommendationsResponse,
    summary="Get personalized study suggestions based on student's actual course progress and assessment history",
)
def get_study_recommendations_endpoint(
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_student_study_recommendations(mongo_db, current_user.id)


@router.get(
    "/conversations",
    summary="List past AI conversations for current user",
)
def get_conversations(
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return list_user_conversations(mongo_db, current_user.id)


@router.get(
    "/conversations/{conversation_id}",
    summary="Get message history for a specific conversation",
)
def get_conversation(
    conversation_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    detail = get_conversation_detail(mongo_db, conversation_id, current_user.id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )
    return detail


@router.delete(
    "/conversations/{conversation_id}",
    response_model=MessageResponse,
    summary="Delete a conversation",
)
def delete_conversation(
    conversation_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    delete_user_conversation(mongo_db, conversation_id, current_user.id, sqlite_db=db)
    return MessageResponse(message="Conversation deleted.")
