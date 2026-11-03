import io
from pathlib import Path
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_instructor
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.material import MaterialResponse, MaterialUpdate
from app.security.jwt import decode_access_token
from app.services.material_service import (
    delete_material as service_delete_material,
    get_material_detail as service_get_material_detail,
    get_material_file_for_download as service_get_material_file,
    list_course_materials as service_list_course_materials,
    update_material as service_update_material,
    upload_course_material as service_upload_course_material,
)

router = APIRouter(tags=["Course Learning Materials"])
http_bearer = HTTPBearer(auto_error=False)


def get_current_user_flexible(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> User:
    """Authorize user via either Authorization Bearer header or ?token query param."""
    raw_token = None
    if auth and auth.credentials:
        raw_token = auth.credentials
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to download course materials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact an administrator.",
        )
    return user


@router.post(
    "/instructor/courses/{course_id}/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new course learning material (Instructor / Admin only)",
)
async def upload_material(
    course_id: int,
    title: str = Form(..., min_length=2, max_length=255),
    description: Optional[str] = Form(None),
    section_id: Optional[int] = Form(None),
    lesson_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    """
    Securely upload and validate a course document or image.
    Validates extension, MIME type, file signature, and size limit.
    """
    content = await file.read()
    return service_upload_course_material(
        db=db,
        course_id=course_id,
        file_content=content,
        original_filename=file.filename or "material",
        client_mime=file.content_type,
        title=title,
        description=description,
        section_id=section_id if section_id and section_id > 0 else None,
        lesson_id=lesson_id if lesson_id and lesson_id > 0 else None,
        current_user=current_user,
    )


@router.get(
    "/materials/course/{course_id}",
    response_model=List[MaterialResponse],
    summary="List available learning materials for a course (Enrolled students, instructors, admins)",
)
def list_course_materials(
    course_id: int,
    section_id: Optional[int] = Query(None),
    lesson_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all materials for an enrolled or owned course."""
    return service_list_course_materials(
        db=db,
        course_id=course_id,
        current_user=current_user,
        section_id=section_id,
        lesson_id=lesson_id,
    )


@router.get(
    "/materials/{material_id}",
    response_model=MaterialResponse,
    summary="Get learning material metadata",
)
def get_material_detail(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve metadata for a specific material."""
    return service_get_material_detail(db, material_id, current_user)


@router.put(
    "/instructor/materials/{material_id}",
    response_model=MaterialResponse,
    summary="Update learning material title or description (Instructor / Admin only)",
)
def update_material(
    material_id: int,
    update_data: MaterialUpdate,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    """Update title, description, or module linkages for an authorized material."""
    return service_update_material(db, material_id, update_data, current_user)


@router.delete(
    "/instructor/materials/{material_id}",
    response_model=MessageResponse,
    summary="Delete a learning material and remove file from storage (Instructor / Admin only)",
)
def delete_material(
    material_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    """Safely delete material record and clean up associated storage file."""
    res = service_delete_material(db, material_id, current_user)
    return MessageResponse(message=res["message"])


@router.get(
    "/materials/{material_id}/download",
    summary="Download an authorized learning material file",
)
def download_material(
    material_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Securely stream the authorized file.
    Does NOT expose internal filesystem paths or identifiers.
    Enforces student course enrollment or instructor ownership.
    Accepts Authorization Bearer header OR ?token= query parameter for direct browser downloads.
    """
    mat, file_source = service_get_material_file(db, material_id, current_user)

    # Encode filename safely for Content-Disposition
    ascii_filename = mat.original_filename.encode("ascii", "ignore").decode("ascii") or "material"

    if isinstance(file_source, Path):
        return FileResponse(
            path=file_source,
            filename=ascii_filename,
            media_type=mat.mime_type,
            content_disposition_type="attachment",
        )
    elif isinstance(file_source, bytes):
        return Response(
            content=file_source,
            media_type=mat.mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{ascii_filename}"',
                "Content-Length": str(len(file_source)),
            },
        )
    else:
        return StreamingResponse(
            io.BytesIO(file_source),
            media_type=mat.mime_type,
            headers={"Content-Disposition": f'attachment; filename="{ascii_filename}"'},
        )
