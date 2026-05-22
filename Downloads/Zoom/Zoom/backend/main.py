import random
import re
from datetime import datetime
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import get_db, engine
import models
import schemas

# Ensure database tables exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Zoom Replica API Backend",
    description="FastAPI server with SQLite backend for Zoom Clone",
    version="1.0.0"
)

# CORS Middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with exact frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Helper Functions ---
def generate_meeting_id() -> str:
    """Generates a unique 10-digit meeting ID: xxx-xxx-xxxx"""
    digits = [str(random.randint(0, 9)) for _ in range(10)]
    return f"{''.join(digits[:3])}-{''.join(digits[3:6])}-{''.join(digits[6:])}"

def get_default_user(db: Session = Depends(get_db)) -> models.User:
    """Get or create the default user (as login is not required)"""
    user = db.query(models.User).filter(models.User.email == "aditi.arora@zoom.us").first()
    if not user:
        user = models.User(
            username="Aditi Arora",
            email="aditi.arora@zoom.us",
            avatar_url="https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&q=80&w=120"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

# --- API Endpoints ---

@app.get("/api/users/me", response_model=schemas.UserResponse)
def get_current_user(current_user: models.User = Depends(get_default_user)):
    """Return current logged-in user placeholder"""
    return current_user

@app.post("/api/meetings/instant", response_model=schemas.MeetingResponse)
def create_instant_meeting(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_default_user)
):
    """Instantly create and active a Zoom meeting"""
    meeting_id = generate_meeting_id()
    invite_link = f"http://localhost:3000/join?id={meeting_id}"

    meeting = models.Meeting(
        meeting_id=meeting_id,
        title=f"Instant Meeting by {current_user.username}",
        description="No description provided",
        host_id=current_user.id,
        invite_link=invite_link,
        is_scheduled=False,
        is_active=True
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    
    # Auto-join host as participant
    host_participant = models.Participant(
        meeting_id=meeting.id,
        user_id=current_user.id,
        display_name=current_user.username,
        is_host=True,
        is_muted=False,
        is_video_off=False
    )
    db.add(host_participant)
    db.commit()
    
    # Refresh meeting to load host and participants relations
    db.refresh(meeting)
    return meeting

@app.post("/api/meetings/schedule", response_model=schemas.MeetingResponse)
def schedule_meeting(
    meeting_in: schemas.MeetingSchedule,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_default_user)
):
    """Schedule a future Zoom meeting"""
    if meeting_in.start_time < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be in the future"
        )

    meeting_id = generate_meeting_id()
    invite_link = f"http://localhost:3000/join?id={meeting_id}"

    meeting = models.Meeting(
        meeting_id=meeting_id,
        title=meeting_in.title,
        description=meeting_in.description,
        host_id=current_user.id,
        invite_link=invite_link,
        start_time=meeting_in.start_time,
        duration_minutes=meeting_in.duration_minutes,
        is_scheduled=True,
        is_active=True
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting

@app.get("/api/meetings/upcoming", response_model=List[schemas.MeetingResponse])
def get_upcoming_meetings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_default_user)
):
    """Retrieve active upcoming scheduled meetings"""
    now = datetime.utcnow()
    meetings = db.query(models.Meeting).filter(
        models.Meeting.is_scheduled == True,
        models.Meeting.is_active == True,
        models.Meeting.host_id == current_user.id,
        # Allow meeting to stay in upcoming list up to 2 hours past its start
        models.Meeting.start_time >= (now - timedelta_custom(minutes=120))
    ).order_by(models.Meeting.start_time.asc()).all()
    return meetings

# Custom timedelta helper to avoid imports issues in scope
def timedelta_custom(minutes: int):
    from datetime import timedelta
    return timedelta(minutes=minutes)

@app.get("/api/meetings/recent", response_model=List[schemas.MeetingResponse])
def get_recent_meetings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_default_user)
):
    """Retrieve completed or inactive meetings for history dashboard"""
    meetings = db.query(models.Meeting).filter(
        models.Meeting.host_id == current_user.id
    ).order_by(models.Meeting.created_at.desc()).limit(10).all()
    return meetings

@app.get("/api/meetings/{meeting_id}", response_model=schemas.MeetingResponse)
def get_meeting(meeting_id: str, db: Session = Depends(get_db)):
    """Get meeting details and validate meeting existence"""
    # Clean meeting id of potential dash spaces
    clean_id = re.sub(r"\s|-", "", meeting_id)
    
    # Check direct clean ID format xxx-xxx-xxxx in DB
    formatted_id = f"{clean_id[:3]}-{clean_id[3:6]}-{clean_id[6:]}" if len(clean_id) == 10 else meeting_id
    
    meeting = db.query(models.Meeting).filter(
        (models.Meeting.meeting_id == formatted_id) | 
        (models.Meeting.meeting_id == meeting_id) |
        (models.Meeting.uuid == meeting_id)
    ).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting does not exist or has expired."
        )
    return meeting

@app.post("/api/meetings/{meeting_id}/join", response_model=schemas.ParticipantResponse)
def join_meeting(
    meeting_id: str,
    payload: schemas.ParticipantJoin,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_default_user)
):
    """Enter a participant into an active meeting"""
    meeting = get_meeting(meeting_id, db)
    
    if not meeting.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This meeting session has already ended."
        )

    # Check if participant with user_id is already active
    existing = db.query(models.Participant).filter(
        models.Participant.meeting_id == meeting.id,
        models.Participant.display_name == payload.display_name,
        models.Participant.left_at == None
    ).first()
    
    if existing:
        return existing

    # Determine if participant is host (display name matches host name)
    is_host = (meeting.host_id == current_user.id and payload.display_name == current_user.username)

    participant = models.Participant(
        meeting_id=meeting.id,
        user_id=current_user.id if payload.display_name == current_user.username else None,
        display_name=payload.display_name,
        is_host=is_host,
        is_muted=False,
        is_video_off=False
    )
    
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant

@app.post("/api/meetings/{meeting_id}/leave")
def leave_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_default_user)
):
    """Record participant exit from a meeting using validated caller"""
    meeting = get_meeting(meeting_id, db)
    
    participant = db.query(models.Participant).filter(
        models.Participant.meeting_id == meeting.id,
        models.Participant.user_id == current_user.id,
        models.Participant.left_at == None
    ).first()
    
    if participant:
        participant.left_at = datetime.utcnow()
        db.commit()
        return {"status": "left"}
    
    return {"status": "not_found"}

@app.post("/api/meetings/{meeting_id}/participants/{participant_name}/mute", response_model=schemas.ParticipantResponse)
def host_mute_participant(
    meeting_id: str,
    participant_name: str,
    payload: schemas.ParticipantUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_default_user)
):
    """Host control: Mute/Unmute participant. Validates host access."""
    meeting = get_meeting(meeting_id, db)
    
    if meeting.host_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized: Only the host can manage participant audio/video.")
    
    participant = db.query(models.Participant).filter(
        models.Participant.meeting_id == meeting.id,
        models.Participant.display_name == participant_name,
        models.Participant.left_at == None
    ).first()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found in active meeting"
        )
        
    if payload.is_muted is not None:
        participant.is_muted = payload.is_muted
    if payload.is_video_off is not None:
        participant.is_video_off = payload.is_video_off
        
    db.commit()
    db.refresh(participant)
    return participant

@app.post("/api/meetings/{meeting_id}/participants/{participant_name}/remove")
def host_remove_participant(
    meeting_id: str,
    participant_name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_default_user)
):
    """Host control: Remove a participant from the meeting. Validates host access."""
    meeting = get_meeting(meeting_id, db)
    
    if meeting.host_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized: Only the host can remove participants.")
    
    participant = db.query(models.Participant).filter(
        models.Participant.meeting_id == meeting.id,
        models.Participant.display_name == participant_name,
        models.Participant.left_at == None
    ).first()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found in active meeting"
        )
        
    participant.left_at = datetime.utcnow()
    db.commit()
    return {"status": "removed"}

@app.post("/api/meetings/{meeting_id}/end")
def end_meeting(
    meeting_id: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_default_user)
):
    """End meeting entirely. Validates host access to prevent hijack closures."""
    meeting = get_meeting(meeting_id, db)
    
    if meeting.host_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized: Only the host can arbitrarily end the meeting.")
    
    meeting.is_active = False
    
    # Set left_at for all active participants
    active_participants = db.query(models.Participant).filter(
        models.Participant.meeting_id == meeting.id,
        models.Participant.left_at == None
    ).all()
    
    for p in active_participants:
        p.left_at = datetime.utcnow()
        
    db.commit()
    return {"status": "meeting_ended"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
