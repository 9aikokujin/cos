from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.utils.scheduler import release_instagram_batch, get_instagram_batch_state


class BatchReleaseRequest(BaseModel):
    batch_id: str
    token: str


router = APIRouter(prefix="/instagram-batch", tags=["InstagramBatch"])


@router.post("/release")
async def release_batch(payload: BatchReleaseRequest):
    expected_token = getattr(settings, "INSTAGRAM_BATCH_CONTROL_TOKEN", None)
    if expected_token and payload.token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid token")

    released = release_instagram_batch(payload.batch_id)
    if not released:
        active, current_id, _ = get_instagram_batch_state()
        detail = "Batch not active"
        if active and current_id:
            detail = f"Another batch ({current_id}) is active"
        raise HTTPException(status_code=404, detail=detail)
    return {"status": "released"}
