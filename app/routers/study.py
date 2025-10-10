from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from app.models.focus_models import StudySessionRequest
from app.security import get_current_user
from app.services.db import cache_service

router = APIRouter(prefix="/study", tags=["study"])


@router.post("/start")
async def start_study_session(
    data: StudySessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Start a study session: mark start time in Redis and lock XP gain tracking.
    """
    guest_token = current_user["token"]
    session_id = data.session_id

    # Check if session exists
    session_key = f"session:{session_id}"
    if not cache_service.exists(session_key):
        raise HTTPException(status_code=404, detail="Session not found")

    # Store start timestamp
    cache_service.hset(session_key, mapping={"study_start": datetime.utcnow().isoformat()})
    cache_service.hset(f"user:{guest_token}:study", mapping={"active_session": session_id})

    return {"message": f"Study session {session_id} started."}


@router.post("/end")
async def end_study_session(
    data: StudySessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    End a study session: calculate XP based on duration, update user's XP & coins.
    """
    guest_token = current_user["token"]
    session_id = data.session_id

    session_key = f"session:{session_id}"
    study_key = f"user:{guest_token}:study"

    session_data = cache_service.hgetall(session_key)
    if not session_data or "study_start" not in session_data:
        raise HTTPException(status_code=400, detail="No active study session found")

    # Calculate duration
    start_time = datetime.fromisoformat(session_data["study_start"])
    duration_minutes = (datetime.utcnow() - start_time).total_seconds() / 60

    # Simple XP formula: 10 XP per 15 minutes
    gained_xp = int((duration_minutes / 15) * 10)
    if gained_xp < 1:
        gained_xp = 1  # Minimum XP gain

    # Update user stats
    user_key = f"token:{guest_token}"
    current_xp = int(cache_service.hget(user_key, "xp") or 0)
    new_xp = current_xp + gained_xp
    cache_service.hset(user_key, mapping={"xp": new_xp})

    # Cleanup study markers
    cache_service.hdel(study_key, "active_session")
    cache_service.hdel(session_key, "study_start")

    return {"new_xp": new_xp, "session_duration_min": round(duration_minutes, 2)}
