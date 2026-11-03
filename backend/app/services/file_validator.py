import io
import re
import uuid
import zipfile
from pathlib import Path
from typing import Optional, Set, Tuple
from fastapi import HTTPException, status
from app.config import get_settings

settings = get_settings()

# Allowed file extensions and canonical MIME types
ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
}

# Explicitly forbidden dangerous extensions
DANGEROUS_EXTENSIONS: Set[str] = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".dll", ".so", ".bin", ".scr",
    ".sh", ".bash", ".zsh", ".ps1", ".psm1", ".vbs", ".vbe", ".wsf", ".wsh",
    ".html", ".htm", ".xhtml", ".shtml", ".js", ".mjs", ".ts",
    ".php", ".phtml", ".php3", ".php4", ".php5", ".asp", ".aspx", ".jsp", ".jspx",
    ".cgi", ".pl", ".py", ".pyc", ".rb", ".jar", ".war", ".ear",
    ".svg", ".xml", ".swf", ".htaccess", ".htpasswd"
}

# Dangerous executable magic signatures to block regardless of extension
DANGEROUS_MAGIC_SIGNATURES = [
    (b"MZ", "DOS/Windows Executable"),  # Windows PE / EXE / DLL
    (b"\x7fELF", "Linux ELF Executable"),  # Linux binary
    (b"\xca\xfe\xba\xbe", "Java Class / Mach-O Binary"),  # Java / macOS binary
    (b"#!", "Shell Script"),  # Script hash-bang
    (b"<?php", "PHP Script"),  # Embedded PHP
    (b"<script", "JavaScript Script"),  # Embedded JavaScript
]


def sanitize_filename(filename: str) -> str:
    """
    Sanitize original filename to strip directory traversal patterns,
    control characters, and unsafe sequences while preserving a human-readable name.
    """
    # Strip any directory path components
    name = Path(filename).name.strip()
    # Remove null bytes and control chars
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    # Remove path traversal characters
    name = name.replace("..", "").replace("/", "").replace("\\", "")
    # Fallback if empty or purely invalid
    if not name or name == ".":
        name = "learning_material"
    return name


def validate_upload_content(filename: str, content: bytes, client_content_type: Optional[str] = None) -> Tuple[str, str, int, str]:
    """
    Rigorously validate uploaded file:
    1. Size check against configured maximum (and non-empty > 0).
    2. Extension validation against allowed list and dangerous blocklist.
    3. Content signature (magic bytes) validation matching true file format.
    4. Malicious script and executable header detection.
    5. Storage key generation.

    Returns:
        (sanitized_filename, validated_mime_type, file_size_bytes, storage_key)
    """
    file_size = len(content)

    # 1. Non-empty check
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    # 2. Maximum file size check
    max_bytes = settings.max_upload_size_bytes
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum permitted size of {settings.MAX_UPLOAD_SIZE_MB} MB ({file_size} bytes).",
        )

    # 3. Extension inspection
    clean_name = sanitize_filename(filename)
    ext = Path(clean_name).suffix.lower()

    if ext in DANGEROUS_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' is forbidden for security reasons.",
        )

    if ext not in ALLOWED_EXTENSIONS:
        allowed_list_str = ", ".join(ALLOWED_EXTENSIONS.keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {allowed_list_str}.",
        )

    canonical_mime = ALLOWED_EXTENSIONS[ext]

    # 4. Check for known dangerous magic signatures regardless of extension
    for sig, desc in DANGEROUS_MAGIC_SIGNATURES:
        if content.startswith(sig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Security violation: file content matches prohibited format ({desc}).",
            )

    # 5. Format-specific structural & magic bytes validation
    if ext == ".pdf":
        # PDF files must start with %PDF-
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed file: header does not match a valid PDF document.",
            )

    elif ext == ".png":
        # PNG signature: 89 50 4E 47 0D 0A 1A 0A
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed file: header does not match a valid PNG image.",
            )

    elif ext in (".jpg", ".jpeg"):
        # JPEG signature: FF D8 FF
        if not content.startswith(b"\xff\xd8\xff"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed file: header does not match a valid JPEG image.",
            )

    elif ext in (".docx", ".pptx"):
        # Office Open XML files are ZIP archives starting with PK\x03\x04
        if not content.startswith(b"PK\x03\x04"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malformed file: header does not match a valid {ext.upper()} archive.",
            )
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                # Check for zip bomb / excessive ratio
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > max_bytes * 5:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Archive compression ratio exceeds safe limits.",
                    )
                # Verify OpenXML content types
                namelist = zf.namelist()
                if "[Content_Types].xml" not in namelist:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid {ext.upper()} document: missing OpenXML metadata.",
                    )
                if ext == ".docx" and not any(n.startswith("word/") for n in namelist):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid DOCX document: missing Word document structure.",
                    )
                if ext == ".pptx" and not any(n.startswith("ppt/") for n in namelist):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid PPTX presentation: missing PowerPoint structure.",
                    )
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupt or invalid {ext.upper()} archive.",
            )

    elif ext == ".txt":
        # Text file: ensure valid UTF-8/ASCII without null bytes
        if b"\x00" in content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Binary content detected in text file.",
            )
        try:
            decoded_text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                decoded_text = content.decode("latin-1")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Text file encoding is not supported.",
                )
        # Prevent HTML/JavaScript smuggled as TXT
        stripped = decoded_text.strip().lower()
        if stripped.startswith("<!doctype html") or stripped.startswith("<html") or "<script" in stripped:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: HTML or script tags detected in plain text upload.",
            )

    elif ext in (".mp4", ".mov"):
        # ISO base media file format check: usually offset 4 contains 'ftyp' or starts with box length
        is_mp4_box = (
            (len(content) >= 8 and content[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"skip", b"free"))
            or content.startswith(b"\x00\x00\x00")
        )
        if not is_mp4_box:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed video: file does not match a valid MP4/MOV container structure.",
            )

    elif ext in (".webm", ".mkv"):
        # Matroska / WebM EBML header magic: 1A 45 DF A3
        if not content.startswith(b"\x1a\x45\xdf\xa3"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed video: file does not match a valid WebM/MKV container structure.",
            )

    # 6. Generate unguessable internal storage key
    storage_key = f"{uuid.uuid4().hex}{ext}"

    return clean_name, canonical_mime, file_size, storage_key

