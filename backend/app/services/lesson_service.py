from datetime import datetime, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.repositories.course_repository import (
    count_lessons_for_course,
    get_adjacent_lesson_ids,
    get_completed_lesson_ids,
    get_course_by_id,
    get_enrollment_by_student_and_course,
    get_lesson_by_id,
    get_lesson_progress,
    list_lessons_for_course,
    restore_enrollment_snapshot,
    sync_enrollment_to_sqlite_shadow,
    sync_lesson_progress_to_sqlite_shadow,
    update_enrollment_completion,
    upsert_lesson_progress,
)
from app.repositories.user_repository import MongoUser
from app.schemas.lesson import LessonProgressResponse, LessonResponse


def get_lesson_nav(
    mongo_db: Database,
    course_id: int,
    current_order_index: int,
) -> Tuple[Optional[int], Optional[int]]:
    """Find prev and next lesson IDs based on order_index."""
    return get_adjacent_lesson_ids(mongo_db, course_id, current_order_index)


def get_lesson_for_user(
    mongo_db: Database,
    lesson_id: int,
    user: MongoUser,
) -> LessonResponse:
    """Fetch lesson content from MongoDB and verify enrollment or authorization."""
    lesson = get_lesson_by_id(mongo_db, lesson_id)
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found.",
        )

    course = get_course_by_id(mongo_db, lesson.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated course not found.")

    if user.role != "admin" and course.instructor_id != user.id:
        enrollment = get_enrollment_by_student_and_course(mongo_db, user.id, lesson.course_id)
        if not enrollment or enrollment.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in this course to view its lessons.",
            )

    progress = get_lesson_progress(mongo_db, user.id, lesson.id)
    is_completed = progress.is_completed if progress else False

    return LessonResponse(
        id=lesson.id,
        course_id=lesson.course_id,
        section_id=lesson.section_id,
        title=lesson.title,
        content=lesson.content,
        video_url=lesson.video_url,
        order_index=lesson.order_index,
        is_completed=is_completed,
        created_at=lesson.created_at,
        updated_at=lesson.updated_at,
    )


def mark_lesson_complete(
    mongo_db: Database,
    lesson_id: int,
    user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> LessonProgressResponse:
    """Mark a lesson complete in MongoDB and update overall course completion percentage."""
    lesson = get_lesson_by_id(mongo_db, lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")

    enrollment = get_enrollment_by_student_and_course(mongo_db, user.id, lesson.course_id)
    if (
        user.role not in ("instructor", "admin")
        and (not enrollment or enrollment.status != "approved")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be enrolled in the course to record progress.",
        )

    now = datetime.now(timezone.utc)
    progress = upsert_lesson_progress(
        mongo_db,
        student_id=user.id,
        lesson_id=lesson_id,
        is_completed=True,
        now=now,
    )
    sync_lesson_progress_to_sqlite_shadow(sqlite_db, progress)

    course_lessons = list_lessons_for_course(mongo_db, lesson.course_id)
    total_lessons = len(course_lessons) if course_lessons else count_lessons_for_course(mongo_db, lesson.course_id)
    completed_ids = get_completed_lesson_ids(
        mongo_db,
        user.id,
        [l.id for l in course_lessons],
    )
    completed_lessons = len(completed_ids)

    completion_percentage = (
        round((completed_lessons / total_lessons) * 100.0, 1) if total_lessons > 0 else 100.0
    )

    if enrollment:
        updated_enr = update_enrollment_completion(mongo_db, enrollment.id, completion_percentage)
        if updated_enr:
            try:
                sync_enrollment_to_sqlite_shadow(sqlite_db, updated_enr)
            except Exception:
                restore_enrollment_snapshot(mongo_db, enrollment)
                raise

    return LessonProgressResponse(
        student_id=user.id,
        lesson_id=lesson_id,
        is_completed=True,
        completed_at=progress.completed_at or now,
        updated_at=progress.updated_at or now,
        course_completion_percentage=completion_percentage,
    )
