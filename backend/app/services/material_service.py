from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import CourseEnrollment
from app.models.lesson import Lesson
from app.models.material import LearningMaterial
from app.models.section import CourseSection
from app.models.user import User
from app.schemas.material import MaterialResponse, MaterialUpdate
from app.services.file_validator import validate_upload_content
from app.services.storage import get_storage_provider


def check_course_ownership(course: Course, user: User):
    """Verify that current user is the course instructor or an administrator."""
    if user.role != "admin" and course.instructor_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage learning materials for this course.",
        )


def check_course_material_access(db: Session, course_id: int, user: User) -> Course:
    """
    Verify course exists and user has authorization to access materials:
    - Administrators: Allowed.
    - Course Instructor: Allowed.
    - Students: Must be actively enrolled in the course.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    if user.role != "admin" and course.instructor_id != user.id:
        enrollment = (
            db.query(CourseEnrollment)
            .filter(
                CourseEnrollment.student_id == user.id,
                CourseEnrollment.course_id == course_id,
            )
            .first()
        )
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in this course to access its learning materials.",
            )
    return course


def build_material_response(mat: LearningMaterial) -> MaterialResponse:
    """Map LearningMaterial model to MaterialResponse with relational titles."""
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
        uploader_name=mat.uploader.full_name if mat.uploader else None,
        section_title=mat.section.title if mat.section else None,
        lesson_title=mat.lesson.title if mat.lesson else None,
        created_at=mat.created_at,
        updated_at=mat.updated_at,
    )


def upload_course_material(
    db: Session,
    course_id: int,
    file_content: bytes,
    original_filename: str,
    client_mime: Optional[str],
    title: str,
    description: Optional[str],
    section_id: Optional[int],
    lesson_id: Optional[int],
    current_user: User,
) -> MaterialResponse:
    """
    Validate, securely store, and record a new course learning material.
    Handles cleanup if database insertion fails to prevent orphaned files.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    check_course_ownership(course, current_user)

    # Validate section linking if provided
    if section_id:
        sec = db.query(CourseSection).filter(
            CourseSection.id == section_id,
            CourseSection.course_id == course_id,
        ).first()
        if not sec:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected section does not belong to this course.")

    # Validate lesson linking if provided
    if lesson_id:
        les = db.query(Lesson).filter(
            Lesson.id == lesson_id,
            Lesson.course_id == course_id,
        ).first()
        if not les:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected lesson does not belong to this course.")

    # Server-side validation of content, MIME, magic bytes, and size
    clean_filename, canonical_mime, file_size, storage_key = validate_upload_content(
        filename=original_filename,
        content=file_content,
        client_content_type=client_mime,
    )

    storage = get_storage_provider()
    # Save file to storage
    storage.save_file(storage_key, file_content)

    # Persist record in database with transaction safety
    try:
        material = LearningMaterial(
            title=title.strip(),
            description=description.strip() if description else None,
            original_filename=clean_filename,
            storage_key=storage_key,
            mime_type=canonical_mime,
            file_size=file_size,
            uploader_id=current_user.id,
            course_id=course_id,
            section_id=section_id,
            lesson_id=lesson_id,
        )
        db.add(material)
        db.commit()
        db.refresh(material)
    except Exception as e:
        # If database persistence fails, clean up the written file to prevent disk leaks
        db.rollback()
        storage.delete_file(storage_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record learning material: {str(e)}",
        )

    return build_material_response(material)


def list_course_materials(
    db: Session,
    course_id: int,
    current_user: User,
    section_id: Optional[int] = None,
    lesson_id: Optional[int] = None,
) -> List[MaterialResponse]:
    """List all authorized learning materials for a course."""
    check_course_material_access(db, course_id, current_user)

    query = db.query(LearningMaterial).filter(LearningMaterial.course_id == course_id)
    if section_id:
        query = query.filter(LearningMaterial.section_id == section_id)
    if lesson_id:
        query = query.filter(LearningMaterial.lesson_id == lesson_id)

    materials = query.order_by(LearningMaterial.created_at.desc()).all()
    return [build_material_response(m) for m in materials]


def get_material_detail(db: Session, material_id: int, current_user: User) -> MaterialResponse:
    """Retrieve metadata for a specific learning material."""
    mat = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning material not found.")

    check_course_material_access(db, mat.course_id, current_user)
    return build_material_response(mat)


def update_material(
    db: Session,
    material_id: int,
    update_data: MaterialUpdate,
    current_user: User,
) -> MaterialResponse:
    """Update title, description, or module linkages for an authorized material."""
    mat = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning material not found.")

    course = db.query(Course).filter(Course.id == mat.course_id).first()
    check_course_ownership(course, current_user)

    if update_data.title is not None:
        mat.title = update_data.title.strip()
    if update_data.description is not None:
        mat.description = update_data.description.strip() if update_data.description else None
    if update_data.section_id is not None:
        if update_data.section_id != 0:
            sec = db.query(CourseSection).filter(
                CourseSection.id == update_data.section_id,
                CourseSection.course_id == mat.course_id,
            ).first()
            if not sec:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected section does not belong to this course.")
            mat.section_id = update_data.section_id
        else:
            mat.section_id = None
    if update_data.lesson_id is not None:
        if update_data.lesson_id != 0:
            les = db.query(Lesson).filter(
                Lesson.id == update_data.lesson_id,
                Lesson.course_id == mat.course_id,
            ).first()
            if not les:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected lesson does not belong to this course.")
            mat.lesson_id = update_data.lesson_id
        else:
            mat.lesson_id = None

    mat.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(mat)
    return build_material_response(mat)


def delete_material(db: Session, material_id: int, current_user: User) -> dict:
    """Delete learning material from both database and storage provider."""
    mat = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning material not found.")

    course = db.query(Course).filter(Course.id == mat.course_id).first()
    check_course_ownership(course, current_user)

    storage_key = mat.storage_key
    db.delete(mat)
    db.commit()

    # Safely delete from storage
    storage = get_storage_provider()
    storage.delete_file(storage_key)

    return {"message": "Learning material deleted successfully."}


def get_material_file_for_download(db: Session, material_id: int, current_user: User):
    """
    Authenticate and authorize download of material file.
    Returns (material, file_path_or_bytes).
    """
    mat = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning material not found.")

    check_course_material_access(db, mat.course_id, current_user)

    storage = get_storage_provider()
    if not storage.file_exists(mat.storage_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested file was not found in storage.",
        )

    local_path = storage.get_file_path(mat.storage_key)
    if local_path:
        return mat, local_path

    # If stream or bytes (e.g. cloud)
    return mat, storage.get_file_bytes(mat.storage_key)

