"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from datetime import date

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _serialize(ann: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    ann["id"] = str(ann.pop("_id"))
    return ann


def _get_today() -> str:
    return date.today().isoformat()


def _require_auth(teacher_username: Optional[str]) -> None:
    """Raise 401 if teacher_username is missing or invalid."""
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """
    Get currently active announcements (public).

    Returns announcements where today is within [start_date, expiry_date].
    start_date is optional; when absent the announcement is always active until expiry.
    """
    today = _get_today()
    query = {
        "expiry_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": {"$exists": False}},
            {"start_date": {"$lte": today}},
        ],
    }
    return [_serialize(ann) for ann in announcements_collection.find(query).sort("created_at", -1)]


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(
    teacher_username: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """
    Get all announcements regardless of status — requires authentication.
    """
    _require_auth(teacher_username)
    return [_serialize(ann) for ann in announcements_collection.find().sort("expiry_date", -1)]


@router.post("", response_model=Dict[str, Any], status_code=201)
def create_announcement(
    message: str,
    expiry_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Create a new announcement — requires authentication.

    - **message**: Announcement text (required)
    - **expiry_date**: YYYY-MM-DD (required)
    - **start_date**: YYYY-MM-DD (optional)
    """
    _require_auth(teacher_username)

    try:
        date.fromisoformat(expiry_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="expiry_date inválido. Use YYYY-MM-DD")

    if start_date:
        try:
            start = date.fromisoformat(start_date)
            expiry = date.fromisoformat(expiry_date)
            if start > expiry:
                raise HTTPException(
                    status_code=400, detail="start_date não pode ser posterior a expiry_date"
                )
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date inválido. Use YYYY-MM-DD")

    from datetime import datetime

    doc = {
        "message": message.strip(),
        "start_date": start_date or None,
        "expiry_date": expiry_date,
        "created_by": teacher_username,
        "created_at": datetime.utcnow().isoformat(),
    }
    result = announcements_collection.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiry_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Update an existing announcement — requires authentication.
    """
    _require_auth(teacher_username)

    try:
        date.fromisoformat(expiry_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="expiry_date inválido. Use YYYY-MM-DD")

    if start_date:
        try:
            start = date.fromisoformat(start_date)
            expiry = date.fromisoformat(expiry_date)
            if start > expiry:
                raise HTTPException(
                    status_code=400, detail="start_date não pode ser posterior a expiry_date"
                )
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date inválido. Use YYYY-MM-DD")

    from bson import ObjectId

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de anúncio inválido")

    result = announcements_collection.update_one(
        {"_id": oid},
        {"$set": {
            "message": message.strip(),
            "start_date": start_date or None,
            "expiry_date": expiry_date,
        }},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado")

    updated = announcements_collection.find_one({"_id": oid})
    return _serialize(updated)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Delete an announcement — requires authentication.
    """
    _require_auth(teacher_username)

    from bson import ObjectId

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de anúncio inválido")

    result = announcements_collection.delete_one({"_id": oid})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado")

    return {"message": "Anúncio excluído com sucesso"}
