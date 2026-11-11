from datetime import datetime, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.user import User
from app.schemas.lesson import LessonProgressResponse, LessonResponse


def get_lesson_nav(db: Session, course_id: int, current_order_index: int) -> Tuple[Optional[int], Optional[int]]:
    """Find prev and next lesson IDs based on order_index."""
    prev_lesson = (
        db.query(Lesson.id)
        .filter(Lesson.course_id == course_id, Lesson.order_index < current_order_index)
        .order_by(Lesson.order_index.desc())
        .first()
    )
    next_lesson = (
        db.query(Lesson.id)
        .filter(Lesson.course_id == course_id, Lesson.order_index > current_order_index)
        .order_by(Lesson.order_index.asc())
        .first()
    )
    prev_id = prev_lesson[0] if prev_lesson else None
    next_id = next_lesson[0] if next_lesson else None
    return prev_id, next_id


def get_lesson_for_user(db: Session, lesson_id: int, user: User) -> LessonResponse:
    """Fetch lesson content and verify enrollment or authorization."""
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lesson not found.",
        )

    course = db.query(Course).filter(Course.id == lesson.course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated course not found.")

    if user.role != "admin" and course.instructor_id != user.id:
        enrollment = (
            db.query(CourseEnrollment)
            .filter(
                CourseEnrollment.student_id == user.id,
                CourseEnrollment.course_id == lesson.course_id,
                CourseEnrollment.status == "approved",
            )
            .first()
        )
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in this course to view its lessons.",
            )

    progress = (
        db.query(LessonProgress)
        .filter(
            LessonProgress.student_id == user.id,
            LessonProgress.lesson_id == lesson.id,
        )
        .first()
    )
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


def mark_lesson_complete(db: Session, lesson_id: int, user: User) -> LessonProgressResponse:
    """Mark a lesson complete and update overall course completion percentage."""
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")

    enrollment = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.student_id == user.id,
            CourseEnrollment.course_id == lesson.course_id,
        )
        .first()
    )
    if (
        user.role not in ("instructor", "admin")
        and (not enrollment or enrollment.status != "approved")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be enrolled in the course to record progress.",
        )

    now = datetime.now(timezone.utc)
    progress = (
        db.query(LessonProgress)
        .filter(
            LessonProgress.student_id == user.id,
            LessonProgress.lesson_id == lesson_id,
        )
        .first()
    )
    if not progress:
        progress = LessonProgress(
            student_id=user.id,
            lesson_id=lesson_id,
            is_completed=True,
            completed_at=now,
            updated_at=now,
        )
        db.add(progress)
    else:
        progress.is_completed = True
        progress.completed_at = now
        progress.updated_at = now

    db.commit()

    total_lessons = db.query(Lesson).filter(Lesson.course_id == lesson.course_id).count()
    completed_lessons = (
        db.query(LessonProgress)
        .join(Lesson, Lesson.id == LessonProgress.lesson_id)
        .filter(
            LessonProgress.student_id == user.id,
            Lesson.course_id == lesson.course_id,
            LessonProgress.is_completed == True,
        )
        .count()
    )

    completion_percentage = (
        round((completed_lessons / total_lessons) * 100.0, 1) if total_lessons > 0 else 100.0
    )

    if enrollment:
        enrollment.completion_percentage = completion_percentage
        db.commit()

    return LessonProgressResponse(
        student_id=user.id,
        lesson_id=lesson_id,
        is_completed=True,
        completed_at=now,
        updated_at=now,
        course_completion_percentage=completion_percentage,
    )
