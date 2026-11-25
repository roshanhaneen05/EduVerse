from typing import Dict, List, Optional
from fastapi import HTTPException, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.repositories.course_repository import (
    MongoCourse,
    get_course_by_id,
    get_enrollment_by_student_and_course,
    get_lesson_by_id,
    get_section_by_id,
    list_lessons_for_course,
    list_sections_for_course,
)
from app.repositories.material_repository import (
    MongoLearningMaterial,
    create_material_doc,
    delete_material_doc,
    delete_material_from_sqlite_shadow,
    get_material_by_id,
    list_materials_for_course,
    restore_material_snapshot,
    sync_material_to_sqlite_shadow,
    update_material_doc,
)
from app.repositories.user_repository import MongoUser, get_user_by_id, get_users_by_ids
from app.schemas.material import MaterialResponse, MaterialUpdate
from app.services.file_validator import validate_upload_content
from app.services.storage import get_storage_provider


def check_course_ownership(course: MongoCourse, user: MongoUser) -> None:
    """Verify that current user is the course instructor or an administrator."""
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage learning materials for this course.",
        )


def check_course_material_access(
    mongo_db: Database,
    course_id: int,
    user: MongoUser,
) -> MongoCourse:
    """
    Verify course exists and user has authorization to access materials:
    - Administrators: Allowed.
    - Course Instructor: Allowed.
    - Students: Must be actively enrolled in the course.
    """
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    if user.role != "admin" and course.instructor_id != user.id:
        enrollment = get_enrollment_by_student_and_course(mongo_db, user.id, course_id)
        if not enrollment or enrollment.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in this course to access its learning materials.",
            )
    return course


def build_material_response(
    mongo_db: Database,
    mat: MongoLearningMaterial,
    *,
    user_cache: Optional[Dict[int, MongoUser]] = None,
    section_titles: Optional[Dict[int, str]] = None,
    lesson_titles: Optional[Dict[int, str]] = None,
) -> MaterialResponse:
    """Map MongoLearningMaterial to MaterialResponse with relational titles."""
    uploader = (
        user_cache.get(mat.uploader_id)
        if user_cache is not None
        else get_user_by_id(mongo_db, mat.uploader_id)
    )
    section_title = None
    if mat.section_id is not None:
        if section_titles is not None:
            section_title = section_titles.get(mat.section_id)
        else:
            sec = get_section_by_id(mongo_db, mat.section_id)
            section_title = sec.title if sec else None

    lesson_title = None
    if mat.lesson_id is not None:
        if lesson_titles is not None:
            lesson_title = lesson_titles.get(mat.lesson_id)
        else:
            les = get_lesson_by_id(mongo_db, mat.lesson_id)
            lesson_title = les.title if les else None

    return MaterialResponse(
        id=mat.id,
        course_id=mat.course_id,
        section_id=mat.section_id,
        lesson_id=mat.lesson_id,
        title=mat.title,
        description=mat.description,
        original_filename=mat.original_filename,
        mime_type=mat.mime_type,
        file_size=mat.file_size,
        uploader_id=mat.uploader_id,
        uploader_name=uploader.full_name if uploader else None,
        section_title=section_title,
        lesson_title=lesson_title,
        created_at=mat.created_at,
        updated_at=mat.updated_at,
    )


def upload_course_material(
    mongo_db: Database,
    course_id: int,
    file_content: bytes,
    original_filename: str,
    client_mime: Optional[str],
    title: str,
    description: Optional[str],
    section_id: Optional[int],
    lesson_id: Optional[int],
    current_user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> MaterialResponse:
    """
    Validate, securely store, and record a new course learning material in MongoDB.
    Handles cleanup if persistence fails to prevent orphaned files.
    """
    course = get_course_by_id(mongo_db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    if section_id:
        sec = get_section_by_id(mongo_db, section_id)
        if not sec or sec.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected section does not belong to this course.",
            )

    if lesson_id:
        les = get_lesson_by_id(mongo_db, lesson_id)
        if not les or les.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected lesson does not belong to this course.",
            )

    clean_filename, canonical_mime, file_size, storage_key = validate_upload_content(
        filename=original_filename,
        content=file_content,
        client_content_type=client_mime,
    )

    storage = get_storage_provider()
    storage.save_file(storage_key, file_content)

    material: Optional[MongoLearningMaterial] = None
    try:
        material = create_material_doc(
            mongo_db,
            title=title,
            description=description,
            original_filename=clean_filename,
            storage_key=storage_key,
            mime_type=canonical_mime,
            file_size=file_size,
            uploader_id=current_user.id,
            course_id=course_id,
            section_id=section_id,
            lesson_id=lesson_id,
        )
        sync_material_to_sqlite_shadow(sqlite_db, material)
    except Exception as exc:
        if material is not None:
            delete_material_doc(mongo_db, material.id)
        storage.delete_file(storage_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record learning material: {str(exc)}",
        ) from exc

    return build_material_response(mongo_db, material)


def list_course_materials(
    mongo_db: Database,
    course_id: int,
    current_user: MongoUser,
    section_id: Optional[int] = None,
    lesson_id: Optional[int] = None,
) -> List[MaterialResponse]:
    """List all authorized learning materials for a course."""
    check_course_material_access(mongo_db, course_id, current_user)
    materials = list_materials_for_course(
        mongo_db,
        course_id,
        section_id=section_id,
        lesson_id=lesson_id,
    )
    if not materials:
        return []

    user_cache = get_users_by_ids(mongo_db, [m.uploader_id for m in materials])
    section_titles = {s.id: s.title for s in list_sections_for_course(mongo_db, course_id)}
    lesson_titles = {l.id: l.title for l in list_lessons_for_course(mongo_db, course_id)}

    return [
        build_material_response(
            mongo_db,
            m,
            user_cache=user_cache,
            section_titles=section_titles,
            lesson_titles=lesson_titles,
        )
        for m in materials
    ]


def get_material_detail(
    mongo_db: Database,
    material_id: int,
    current_user: MongoUser,
) -> MaterialResponse:
    """Retrieve metadata for a specific learning material."""
    mat = get_material_by_id(mongo_db, material_id)
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning material not found.")

    check_course_material_access(mongo_db, mat.course_id, current_user)
    return build_material_response(mongo_db, mat)


def update_material(
    mongo_db: Database,
    material_id: int,
    update_data: MaterialUpdate,
    current_user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> MaterialResponse:
    """Update title, description, or module linkages for an authorized material."""
    mat = get_material_by_id(mongo_db, material_id)
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning material not found.")

    course = get_course_by_id(mongo_db, mat.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    updates: dict = {}
    if update_data.title is not None:
        updates["title"] = update_data.title.strip()
    if update_data.description is not None:
        updates["description"] = update_data.description.strip() if update_data.description else None
    if update_data.section_id is not None:
        if update_data.section_id != 0:
            sec = get_section_by_id(mongo_db, update_data.section_id)
            if not sec or sec.course_id != mat.course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected section does not belong to this course.",
                )
            updates["section_id"] = update_data.section_id
        else:
            updates["section_id"] = None
    if update_data.lesson_id is not None:
        if update_data.lesson_id != 0:
            les = get_lesson_by_id(mongo_db, update_data.lesson_id)
            if not les or les.course_id != mat.course_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected lesson does not belong to this course.",
                )
            updates["lesson_id"] = update_data.lesson_id
        else:
            updates["lesson_id"] = None

    updated = update_material_doc(mongo_db, mat.id, updates) if updates else mat
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning material not found.")
    try:
        sync_material_to_sqlite_shadow(sqlite_db, updated)
    except Exception:
        restore_material_snapshot(mongo_db, mat)
        raise

    return build_material_response(mongo_db, updated)


def delete_material(
    mongo_db: Database,
    material_id: int,
    current_user: MongoUser,
    sqlite_db: Optional[Session] = None,
) -> dict:
    """Delete learning material from MongoDB, SQLite shadow, and storage provider."""
    mat = get_material_by_id(mongo_db, material_id)
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning material not found.")

    course = get_course_by_id(mongo_db, mat.course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    storage_key = mat.storage_key
    delete_material_doc(mongo_db, material_id)
    delete_material_from_sqlite_shadow(sqlite_db, material_id)

    storage = get_storage_provider()
    storage.delete_file(storage_key)

    return {"message": "Learning material deleted successfully."}


def get_material_file_for_download(
    mongo_db: Database,
    material_id: int,
    current_user: MongoUser,
):
    """
    Authenticate and authorize download of material file.
    Returns (material, file_path_or_bytes).
    """
    mat = get_material_by_id(mongo_db, material_id)
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning material not found.")

    check_course_material_access(mongo_db, mat.course_id, current_user)

    storage = get_storage_provider()
    if not storage.file_exists(mat.storage_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested file was not found in storage.",
        )

    local_path = storage.get_file_path(mat.storage_key)
    if local_path:
        return mat, local_path

    return mat, storage.get_file_bytes(mat.storage_key)
