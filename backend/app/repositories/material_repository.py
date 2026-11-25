import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import DESCENDING, ReturnDocument
from pymongo.database import Database
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.material import LearningMaterial
from app.mongo_schema import next_sequence_id, sync_counter
from app.repositories.user_repository import _ensure_utc

logger = logging.getLogger(__name__)


@dataclass
class MongoLearningMaterial:
    id: int
    title: str
    description: Optional[str]
    original_filename: str
    storage_key: str
    mime_type: str
    file_size: int
    uploader_id: int
    course_id: int
    section_id: Optional[int]
    lesson_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "MongoLearningMaterial":
        now = datetime.now(timezone.utc)
        sec_id = doc.get("section_id")
        les_id = doc.get("lesson_id")
        return cls(
            id=int(doc["id"]),
            title=str(doc["title"]),
            description=doc.get("description"),
            original_filename=str(doc["original_filename"]),
            storage_key=str(doc["storage_key"]),
            mime_type=str(doc["mime_type"]),
            file_size=int(doc["file_size"]),
            uploader_id=int(doc["uploader_id"]),
            course_id=int(doc["course_id"]),
            section_id=int(sec_id) if sec_id is not None else None,
            lesson_id=int(les_id) if les_id is not None else None,
            created_at=_ensure_utc(doc.get("created_at")) or now,
            updated_at=_ensure_utc(doc.get("updated_at")) or now,
        )


def get_material_by_id(
    mongo_db: Database,
    material_id: int,
) -> Optional[MongoLearningMaterial]:
    doc = mongo_db["learning_materials"].find_one({"id": int(material_id)})
    return MongoLearningMaterial.from_doc(doc) if doc else None


def list_materials_for_course(
    mongo_db: Database,
    course_id: int,
    *,
    section_id: Optional[int] = None,
    lesson_id: Optional[int] = None,
) -> List[MongoLearningMaterial]:
    filt: Dict[str, Any] = {"course_id": int(course_id)}
    if section_id is not None:
        filt["section_id"] = int(section_id)
    if lesson_id is not None:
        filt["lesson_id"] = int(lesson_id)
    cursor = mongo_db["learning_materials"].find(filt).sort("created_at", DESCENDING)
    return [MongoLearningMaterial.from_doc(d) for d in cursor]


def count_all_materials(mongo_db: Database) -> int:
    return int(mongo_db["learning_materials"].count_documents({}))


def create_material_doc(
    mongo_db: Database,
    *,
    title: str,
    description: Optional[str],
    original_filename: str,
    storage_key: str,
    mime_type: str,
    file_size: int,
    uploader_id: int,
    course_id: int,
    section_id: Optional[int],
    lesson_id: Optional[int],
) -> MongoLearningMaterial:
    now = datetime.now(timezone.utc)
    material_id = next_sequence_id(mongo_db, "learning_materials")
    doc = {
        "id": material_id,
        "title": title.strip(),
        "description": description.strip() if description else None,
        "original_filename": original_filename,
        "storage_key": storage_key,
        "mime_type": mime_type,
        "file_size": int(file_size),
        "uploader_id": int(uploader_id),
        "course_id": int(course_id),
        "section_id": int(section_id) if section_id is not None else None,
        "lesson_id": int(lesson_id) if lesson_id is not None else None,
        "created_at": now,
        "updated_at": now,
    }
    mongo_db["learning_materials"].insert_one(doc)
    return MongoLearningMaterial.from_doc(doc)


def update_material_doc(
    mongo_db: Database,
    material_id: int,
    updates: Dict[str, Any],
) -> Optional[MongoLearningMaterial]:
    payload = dict(updates)
    payload["updated_at"] = datetime.now(timezone.utc)
    doc = mongo_db["learning_materials"].find_one_and_update(
        {"id": int(material_id)},
        {"$set": payload},
        return_document=ReturnDocument.AFTER,
    )
    return MongoLearningMaterial.from_doc(doc) if doc else None


def restore_material_snapshot(
    mongo_db: Database,
    prev: MongoLearningMaterial,
) -> None:
    mongo_db["learning_materials"].update_one(
        {"id": prev.id},
        {
            "$set": {
                "title": prev.title,
                "description": prev.description,
                "original_filename": prev.original_filename,
                "storage_key": prev.storage_key,
                "mime_type": prev.mime_type,
                "file_size": prev.file_size,
                "uploader_id": prev.uploader_id,
                "course_id": prev.course_id,
                "section_id": prev.section_id,
                "lesson_id": prev.lesson_id,
                "created_at": prev.created_at,
                "updated_at": prev.updated_at,
            }
        },
        upsert=True,
    )


def delete_material_doc(mongo_db: Database, material_id: int) -> None:
    mongo_db["learning_materials"].delete_one({"id": int(material_id)})


# ---------------------------------------------------------------------------
# Transitional SQLite Shadow Sync
# ---------------------------------------------------------------------------


def sync_material_to_sqlite_shadow(
    sqlite_db: Optional[Session],
    material: MongoLearningMaterial,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = (
            sqlite_db.query(LearningMaterial)
            .filter(LearningMaterial.id == material.id)
            .first()
        )
        if row is None:
            row = LearningMaterial(
                id=material.id,
                title=material.title,
                description=material.description,
                original_filename=material.original_filename,
                storage_key=material.storage_key,
                mime_type=material.mime_type,
                file_size=material.file_size,
                uploader_id=material.uploader_id,
                course_id=material.course_id,
                section_id=material.section_id,
                lesson_id=material.lesson_id,
                created_at=material.created_at,
                updated_at=material.updated_at,
            )
            sqlite_db.add(row)
        else:
            row.title = material.title
            row.description = material.description
            row.section_id = material.section_id
            row.lesson_id = material.lesson_id
            row.updated_at = material.updated_at
        sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow sync failed for material_id=%s: %s",
            material.id,
            type(exc).__name__,
        )
        raise


def delete_material_from_sqlite_shadow(
    sqlite_db: Optional[Session],
    material_id: int,
) -> None:
    if sqlite_db is None:
        return
    try:
        row = (
            sqlite_db.query(LearningMaterial)
            .filter(LearningMaterial.id == material_id)
            .first()
        )
        if row is not None:
            sqlite_db.delete(row)
            sqlite_db.commit()
    except SQLAlchemyError as exc:
        sqlite_db.rollback()
        logger.error(
            "SQLite shadow delete failed for material_id=%s: %s",
            material_id,
            type(exc).__name__,
        )
        raise


def sync_sqlite_materials_to_mongo(
    sqlite_db: Session,
    mongo_db: Database,
) -> Dict[str, int]:
    """Seed helper: copy SQLite learning_materials into MongoDB."""
    rows = sqlite_db.query(LearningMaterial).order_by(LearningMaterial.id.asc()).all()
    max_id = 0
    for m in rows:
        doc = {
            "id": int(m.id),
            "title": m.title,
            "description": m.description,
            "original_filename": m.original_filename,
            "storage_key": m.storage_key,
            "mime_type": m.mime_type,
            "file_size": int(m.file_size),
            "uploader_id": int(m.uploader_id),
            "course_id": int(m.course_id),
            "section_id": int(m.section_id) if m.section_id is not None else None,
            "lesson_id": int(m.lesson_id) if m.lesson_id is not None else None,
            "created_at": _ensure_utc(m.created_at) or datetime.now(timezone.utc),
            "updated_at": _ensure_utc(m.updated_at) or datetime.now(timezone.utc),
        }
        mongo_db["learning_materials"].update_one(
            {"id": doc["id"]}, {"$set": doc}, upsert=True
        )
        max_id = max(max_id, doc["id"])
    sync_counter(mongo_db, "learning_materials", max_id)
    return {"learning_materials": len(rows)}
