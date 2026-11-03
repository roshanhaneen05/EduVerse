from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class MaterialUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    section_id: Optional[int] = None
    lesson_id: Optional[int] = None


class MaterialResponse(BaseModel):
    id: int
    course_id: int
    section_id: Optional[int] = None
    lesson_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    original_filename: str
    mime_type: str
    file_size: int
    uploader_id: int
    uploader_name: Optional[str] = None
    section_title: Optional[str] = None
    lesson_title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    def file_size_formatted(self) -> str:
        """Format file size in human-readable units (Bytes, KB, MB)."""
        bytes_val = self.file_size
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        else:
            return f"{bytes_val / (1024 * 1024):.1f} MB"

    @computed_field
    def file_extension(self) -> str:
        """Extract clean file extension without dot."""
        if "." in self.original_filename:
            return self.original_filename.rsplit(".", 1)[1].upper()
        return "FILE"

