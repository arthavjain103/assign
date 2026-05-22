from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

# --- USER SCHEMAS ---
class UserBase(BaseModel):
    username: str
    email: str
    avatar_url: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- PARTICIPANT SCHEMAS ---
class ParticipantBase(BaseModel):
    display_name: str
    is_host: bool = False
    is_muted: bool = False
    is_video_off: bool = False

class ParticipantJoin(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=30)

class ParticipantUpdate(BaseModel):
    is_muted: Optional[bool] = None
    is_video_off: Optional[bool] = None

class ParticipantResponse(ParticipantBase):
    id: int
    meeting_id: int
    user_id: Optional[int] = None
    joined_at: datetime
    left_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- MEETING SCHEMAS ---
class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None

class MeetingCreate(MeetingBase):
    # Instant meeting creation needs nothing or just standard fields
    pass

class MeetingSchedule(MeetingBase):
    start_time: datetime
    duration_minutes: int = Field(..., gt=0)

class MeetingResponse(MeetingBase):
    id: int
    uuid: str
    meeting_id: str
    host_id: int
    invite_link: str
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    is_scheduled: bool
    is_active: bool
    created_at: datetime
    host: UserResponse
    participants: List[ParticipantResponse] = []
    participants_count: int

    class Config:
        from_attributes = True
