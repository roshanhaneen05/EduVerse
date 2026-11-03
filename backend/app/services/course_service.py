from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.assignment import Assignment, AssignmentSubmission
from app.models.course import Course
from app.models.material import LearningMaterial
from app.models.section import CourseSection
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson, LessonProgress
from app.models.quiz import Quiz
from app.models.user import User
from app.schemas.course import (
    AssignmentOutlineItem,
    CourseCreate,
    CourseDetailResponse,
    CourseResponse,
    CourseUpdate,
    InstructorSummary,
    LessonOutlineItem,
    MaterialOutlineItem,
    QuizOutlineItem,
)


def enrich_course_response(db: Session, course: Course) -> CourseResponse:
    """Convert Course ORM model to CourseResponse."""
    instructor = None
    if course.instructor:
        instructor = InstructorSummary(
            id=course.instructor.id,
            full_name=course.instructor.full_name,
            email=course.instructor.email,
        )

    return CourseResponse(
        id=course.id,
        title=course.title,
        description=course.description,
        category=course.category,
        difficulty=course.difficulty,
        is_published=course.is_published,
        instructor_id=course.instructor_id,
        instructor=instructor,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


def list_courses(
    db: Session,
    search: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    is_published: Optional[bool] = None,
    instructor_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[CourseResponse]:
    """Retrieve filtered courses with pagination."""
    query = db.query(Course).options(joinedload(Course.instructor))

    if is_published is not None:
        query = query.filter(Course.is_published == is_published)
    if instructor_id is not None:
        query = query.filter(Course.instructor_id == instructor_id)
    if category:
        query = query.filter(Course.category.ilike(f"%{category}%"))
    if difficulty:
        query = query.filter(Course.difficulty.ilike(difficulty))
    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            (Course.title.ilike(search_filter))
            | (Course.description.ilike(search_filter))
            | (Course.category.ilike(search_filter))
        )

    courses = query.order_by(Course.created_at.desc()).offset(skip).limit(limit).all()
    return [enrich_course_response(db, c) for c in courses]


def get_course_detail(
    db: Session,
    course_id: int,
    current_user: Optional[User] = None,
) -> CourseDetailResponse:
    """Get full course detail including outline and user-specific progress."""
    course = (
        db.query(Course)
        .options(joinedload(Course.instructor))
        .filter(Course.id == course_id)
        .first()
    )
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    base_response = enrich_course_response(db, course)

    is_enrolled = False
    completion_percentage = 0.0
    completed_lesson_ids = set()

    if current_user:
        enrollment = (
            db.query(CourseEnrollment)
            .filter(
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.course_id == course_id,
            )
            .first()
        )
        if enrollment:
            is_enrolled = True
            completion_percentage = enrollment.completion_percentage

            progress_records = (
                db.query(LessonProgress.lesson_id)
                .filter(
                    LessonProgress.student_id == current_user.id,
                    LessonProgress.is_completed == True,
                )
                .all()
            )
            completed_lesson_ids = {r[0] for r in progress_records}

    lessons = (
        db.query(Lesson)
        .filter(Lesson.course_id == course_id)
        .order_by(Lesson.order_index.asc())
        .all()
    )
    lesson_items = [
        LessonOutlineItem(
            id=l.id,
            course_id=l.course_id,
            section_id=l.section_id,
            title=l.title,
            video_url=l.video_url,
            order_index=l.order_index,
            is_completed=(l.id in completed_lesson_ids),
        )
        for l in lessons
    ]

    sections = (
        db.query(CourseSection)
        .filter(CourseSection.course_id == course_id)
        .order_by(CourseSection.order_index.asc())
        .all()
    )
    section_items = []
    for s in sections:
        sec_lessons = [item for item in lesson_items if item.section_id == s.id]
        section_items.append({
            "id": s.id,
            "course_id": s.course_id,
            "title": s.title,
            "description": s.description,
            "order_index": s.order_index,
            "lesson_count": len(sec_lessons),
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "lessons": sec_lessons,
        })

    is_manager = current_user and current_user.role in ("instructor", "admin")
    quiz_query = db.query(Quiz).filter(Quiz.course_id == course_id)
    if not is_manager:
        quiz_query = quiz_query.filter(Quiz.is_published == True)
    quizzes = quiz_query.order_by(Quiz.id.asc()).all()

    quiz_items = [
        QuizOutlineItem(
            id=q.id,
            course_id=q.course_id,
            title=q.title,
            description=q.description,
            passing_score=q.passing_score,
            is_published=q.is_published,
            time_limit_minutes=q.time_limit_minutes,
            max_attempts=q.max_attempts,
            section_id=q.section_id,
            lesson_id=q.lesson_id,
            question_count=len(q.questions) if q.questions else 0,
        )
        for q in quizzes
    ]

    # Assignments
    assignment_query = db.query(Assignment).filter(
        Assignment.course_id == course_id,
        Assignment.is_archived == False,
    )
    if not current_user or (current_user.role != "admin" and course.instructor_id != current_user.id):
        assignment_query = assignment_query.filter(Assignment.is_published == True)

    assignments = assignment_query.order_by(Assignment.created_at.asc()).all()

    user_submissions = {}
    if current_user and assignments:
        assignment_ids = [a.id for a in assignments]
        subs = (
            db.query(AssignmentSubmission)
            .filter(
                AssignmentSubmission.student_id == current_user.id,
                AssignmentSubmission.assignment_id.in_(assignment_ids),
            )
            .all()
        )
        user_submissions = {s.assignment_id: s for s in subs}

    assignment_items = [
        AssignmentOutlineItem(
            id=a.id,
            course_id=a.course_id,
            section_id=a.section_id,
            title=a.title,
            description=a.description,
            max_marks=a.max_marks,
            due_date=a.due_date,
            is_closed=a.is_closed,
            my_status=user_submissions[a.id].status if a.id in user_submissions else None,
            my_grade=user_submissions[a.id].grade if a.id in user_submissions else None,
        )
        for a in assignments
    ]

    # Learning Materials (accessible by enrolled students, course instructor, or admin)
    material_items = []
    if current_user and (is_enrolled or current_user.role == "admin" or course.instructor_id == current_user.id):
        raw_materials = (
            db.query(LearningMaterial)
            .filter(LearningMaterial.course_id == course_id)
            .order_by(LearningMaterial.created_at.desc())
            .all()
        )
        for m in raw_materials:
            ext = m.original_filename.rsplit(".", 1)[1].upper() if "." in m.original_filename else "FILE"
            bytes_val = m.file_size
            if bytes_val < 1024:
                fmt_size = f"{bytes_val} B"
            elif bytes_val < 1024 * 1024:
                fmt_size = f"{bytes_val / 1024:.1f} KB"
            else:
                fmt_size = f"{bytes_val / (1024 * 1024):.1f} MB"
            material_items.append(
                MaterialOutlineItem(
                    id=m.id,
                    course_id=m.course_id,
                    section_id=m.section_id,
                    lesson_id=m.lesson_id,
                    title=m.title,
                    description=m.description,
                    original_filename=m.original_filename,
                    mime_type=m.mime_type,
                    file_size=m.file_size,
                    file_size_formatted=fmt_size,
                    file_extension=ext,
                    created_at=m.created_at,
                )
            )

    return CourseDetailResponse(
        **base_response.model_dump(),
        lessons=lesson_items,
        sections=section_items,
        quizzes=quiz_items,
        assignments=assignment_items,
        materials=material_items,
        is_enrolled=is_enrolled,
        completion_percentage=completion_percentage,
    )


def create_course(db: Session, course_in: CourseCreate, instructor_id: int) -> Course:
    course = Course(
        title=course_in.title.strip(),
        description=course_in.description.strip(),
        category=course_in.category.strip(),
        difficulty=course_in.difficulty,
        is_published=course_in.is_published,
        instructor_id=instructor_id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def update_course(db: Session, course: Course, course_in: CourseUpdate) -> Course:
    if course_in.title is not None:
        course.title = course_in.title.strip()
    if course_in.description is not None:
        course.description = course_in.description.strip()
    if course_in.category is not None:
        course.category = course_in.category.strip()
    if course_in.difficulty is not None:
        course.difficulty = course_in.difficulty
    if course_in.is_published is not None:
        course.is_published = course_in.is_published

    db.commit()
    db.refresh(course)
    return course
