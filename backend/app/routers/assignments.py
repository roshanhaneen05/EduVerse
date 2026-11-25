from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pymongo.database import Database
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, get_mongo_db
from app.repositories.assignment_repository import get_assignment_by_id
from app.repositories.user_repository import MongoUser
from app.schemas.assignment import (
    AssignmentDetailResponse,
    AssignmentResponse,
    SubmissionCreate,
    SubmissionResponse,
)
from app.services.assignment_service import (
    check_student_course_access,
    get_assignment_detail_for_student,
    get_student_submission,
    list_course_assignments_for_student,
    submit_student_assignment,
)
from app.services.file_validator import validate_upload_content
from app.services.storage import get_storage_provider

router = APIRouter(prefix="/assignments", tags=["Assignments & Student Submissions"])


@router.post("/{assignment_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_assignment_attachment(
    assignment_id: int,
    file: UploadFile = File(...),
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    assignment = get_assignment_by_id(mongo_db, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only enrolled students can upload assignment files.")
    check_student_course_access(mongo_db, assignment.course_id, current_user)
    if not assignment.is_published or assignment.is_archived or assignment.is_closed:
        raise HTTPException(status_code=400, detail="This assignment is not accepting submissions.")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Assignment attachments must be 10 MB or smaller.")
    filename, mime_type, file_size, storage_key = validate_upload_content(
        file.filename or "",
        content,
        file.content_type,
    )
    if filename.rsplit(".", 1)[-1].lower() not in {"pdf", "docx", "txt"}:
        raise HTTPException(status_code=400, detail="Assignment attachments must be PDF, DOCX, or TXT files.")
    try:
        get_storage_provider().save_file(storage_key, content)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail="Assignment file storage is not configured.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the assignment attachment.") from exc
    return {
        "name": filename,
        "storage_key": storage_key,
        "mime_type": mime_type,
        "file_size": file_size,
    }


@router.get(
    "/course/{course_id}",
    response_model=List[AssignmentResponse],
    summary="List published assignments for a course (student/enrolled view)",
)
def get_course_assignments(
    course_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return list_course_assignments_for_student(mongo_db, course_id, current_user)


@router.get(
    "/{assignment_id}",
    response_model=AssignmentDetailResponse,
    summary="Get assignment details and personal submission status",
)
def get_assignment(
    assignment_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_assignment_detail_for_student(mongo_db, assignment_id, current_user)


@router.post(
    "/{assignment_id}/submit",
    response_model=SubmissionResponse,
    summary="Submit or resubmit written work for an assignment",
)
def submit_assignment(
    assignment_id: int,
    submission_in: SubmissionCreate,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
    db: Session = Depends(get_db),
):
    return submit_student_assignment(
        mongo_db,
        assignment_id,
        submission_in,
        current_user,
        sqlite_db=db,
    )


@router.get(
    "/{assignment_id}/my-submission",
    response_model=Optional[SubmissionResponse],
    summary="Get current user's submission and grading feedback for an assignment",
)
def get_my_submission(
    assignment_id: int,
    current_user: MongoUser = Depends(get_current_user),
    mongo_db: Database = Depends(get_mongo_db),
):
    return get_student_submission(mongo_db, assignment_id, current_user)
