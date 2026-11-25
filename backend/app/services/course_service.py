from typing import Dict, List, Optional
from fastapi import HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.repositories.assignment_repository import (
    list_assignments_for_course,
    list_submissions_for_student_assignments,
)
from app.repositories.course_repository import (
    MongoCourse,
    create_course_doc,
    delete_course_cascade_mongo,
    get_completed_lesson_ids,
    get_course_by_id,
    get_enrollment_by_student_and_course,
    list_courses_filtered,
    list_lessons_for_course,
    list_sections_for_course,
    restore_course_snapshot,
    sync_course_to_sqlite_shadow,
    update_course_doc,
)
from app.repositories.material_repository import list_materials_for_course
from app.repositories.quiz_repository import (
    count_questions_by_quiz_ids,
    list_quizzes_for_course,
)
from app.repositories.user_repository import MongoUser, get_user_by_id, get_users_by_ids
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


def enrich_course_response(
    mongo_db: Database | Session,
    course: MongoCourse,
    instructor_cache: Optional[Dict[int, MongoUser]] = None,
) -> CourseResponse:
    """Convert Course model (MongoDB or transitional SQLAlchemy ORM) to CourseResponse."""
    if instructor_cache is not None:
        instructor_doc = instructor_cache.get(course.instructor_id)
    elif isinstance(mongo_db, Session):
        instructor_doc = getattr(course, "instructor", None)
        if instructor_doc is None:
            from app.models.user import User

            instructor_doc = mongo_db.query(User).filter(User.id == course.instructor_id).first()
    else:
        instructor_doc = get_user_by_id(mongo_db, course.instructor_id)

    instructor = None
    if instructor_doc:
        instructor = InstructorSummary(
            id=instructor_doc.id,
            full_name=instructor_doc.full_name,
            email=instructor_doc.email,
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
    mongo_db: Database,
    search: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    is_published: Optional[bool] = None,
    instructor_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[CourseResponse]:
    """Retrieve filtered courses from MongoDB with pagination."""
    courses = list_courses_filtered(
        mongo_db,
        search=search,
        category=category,
        difficulty=difficulty,
        is_published=is_published,
        instructor_id=instructor_id,
        skip=skip,
        limit=limit,
    )
    instructor_map = get_users_by_ids(mongo_db, [c.instructor_id for c in courses])
    return [enrich_course_response(mongo_db, c, instructor_cache=instructor_map) for c in courses]


def get_course_detail(
    mongo_db: Database,
    course_id: int,
    current_user: Optional[MongoUser] = None,
) -> CourseDetailResponse:
    """Get full course detail from MongoDB across courses, sections, lessons, quizzes, assignments, materials."""
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )

    base_response = enrich_course_response(mongo_db, course)

    is_enrolled = False
    completion_percentage = 0.0
    enrollment_status = None
    completed_lesson_ids = set()

    if current_user:
        enrollment = get_enrollment_by_student_and_course(mongo_db, current_user.id, course_id)
        if enrollment:
            enrollment_status = enrollment.status
            is_enrolled = enrollment.status == "approved"
            if is_enrolled:
                completion_percentage = enrollment.completion_percentage

    restrict_course_content = bool(
        current_user
        and current_user.role == "student"
        and enrollment_status != "approved"
    )
    lessons = list_lessons_for_course(mongo_db, course_id) if not restrict_course_content else []
    if current_user and is_enrolled and lessons:
        completed_lesson_ids = get_completed_lesson_ids(
            mongo_db,
            current_user.id,
            [l.id for l in lessons],
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

    sections = list_sections_for_course(mongo_db, course_id) if not restrict_course_content else []
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

    is_manager = bool(current_user and current_user.role in ("instructor", "admin"))
    quizzes = (
        []
        if restrict_course_content
        else list_quizzes_for_course(mongo_db, course_id, published_only=not is_manager)
    )
    question_counts = count_questions_by_quiz_ids(mongo_db, [q.id for q in quizzes])

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
            question_count=question_counts.get(q.id, 0),
        )
        for q in quizzes
    ]

    is_course_owner_or_admin = bool(
        current_user and (current_user.role == "admin" or course.instructor_id == current_user.id)
    )
    assignments = (
        []
        if restrict_course_content
        else list_assignments_for_course(
            mongo_db,
            course_id,
            published_only=not is_course_owner_or_admin,
            exclude_archived=True,
            sort_asc=True,
        )
    )

    user_submissions = {}
    if current_user and assignments:
        user_submissions = list_submissions_for_student_assignments(
            mongo_db,
            current_user.id,
            [a.id for a in assignments],
        )

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

    material_items = []
    if current_user and (is_enrolled or is_course_owner_or_admin):
        raw_materials = list_materials_for_course(mongo_db, course_id)
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
        enrollment_status=enrollment_status,
        completion_percentage=completion_percentage,
    )


def create_course(
    mongo_db: Database,
    course_in: CourseCreate,
    instructor_id: int,
    sqlite_db: Optional[Session] = None,
) -> MongoCourse:
    course = create_course_doc(
        mongo_db,
        title=course_in.title.strip(),
        description=course_in.description.strip(),
        category=course_in.category.strip(),
        difficulty=course_in.difficulty,
        is_published=course_in.is_published,
        instructor_id=instructor_id,
    )
    try:
        sync_course_to_sqlite_shadow(sqlite_db, course)
    except Exception:
        delete_course_cascade_mongo(mongo_db, course.id)
        raise
    return course


def update_course(
    mongo_db: Database,
    course: MongoCourse,
    course_in: CourseUpdate,
    sqlite_db: Optional[Session] = None,
) -> MongoCourse:
    updates: dict = {}
    if course_in.title is not None:
        updates["title"] = course_in.title.strip()
    if course_in.description is not None:
        updates["description"] = course_in.description.strip()
    if course_in.category is not None:
        updates["category"] = course_in.category.strip()
    if course_in.difficulty is not None:
        updates["difficulty"] = course_in.difficulty
    if course_in.is_published is not None:
        updates["is_published"] = course_in.is_published

    updated = update_course_doc(mongo_db, course.id, updates) if updates else course
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    try:
        sync_course_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_course_snapshot(mongo_db, course)
        raise
    return updated
