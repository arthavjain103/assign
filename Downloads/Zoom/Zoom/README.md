# ZoomConnect — Zoom Clone Web Application

A pixel-perfect, full-stack replica of **Zoom's web platform** built for the SDE Internship Fullstack Assignment.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 (App Router), TypeScript, lucide-react, CSS Variables |
| Backend | Python 3.10+, FastAPI, SQLAlchemy ORM |
| Database | SQLite (relational schema — `zoom.db`) |
| Icons | lucide-react |
| Font | Inter (Google Fonts) |

---

## Database Schema

```
users            meetings            participants
─────────        ─────────────────   ─────────────────────
id (PK)          id (PK)             id (PK)
username         uuid (unique)       meeting_id (FK→meetings)
email            meeting_id (str)    user_id (FK→users, nullable)
avatar_url        title              display_name
created_at       description         is_host (bool)
                 host_id (FK→users)  is_muted (bool)
                 invite_link         is_video_off (bool)
                 start_time          joined_at
                 duration_minutes    left_at (nullable)
                 is_scheduled
                 is_active
                 created_at
```

**Relationships:**
- `User` → `Meeting` (1-to-many via `host_id`)
- `Meeting` → `Participant` (1-to-many, cascade delete)
- `User` → `Participant` (optional, nullable for guest participants)

---

## Features

### Core (Must Have)
| Feature | Status |
|---------|--------|
| Landing Dashboard (Zoom UI clone) | ✅ |
| New Meeting (instant, UUID ID) | ✅ |
| Join Meeting (via ID or link) | ✅ |
| Schedule Meeting (date/time/duration) | ✅ |
| Upcoming Meetings section | ✅ |
| Recent Meetings section | ✅ |
| Meeting room with video grid | ✅ |

### Bonus
| Feature | Status |
|---------|--------|
| Responsive design | ✅ |
| Host controls (Mute/Remove participants) | ✅ |
| Mute All participants | ✅ |
| Chat panel with simulated replies | ✅ |
| Floating emoji reactions | ✅ |
| Recording indicator | ✅ |
| Screen share simulation | ✅ |
| Leave/End meeting modal | ✅ |
| Participant count badge | ✅ |
| Copy invite link | ✅ |

---

## Setup Instructions

### Prerequisites
- Node.js 18+
- Python 3.10+
- pip

### 1. Backend Setup

```bash
cd Zoom/backend

# Create & activate virtual environment
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install fastapi uvicorn sqlalchemy pydantic

# Seed the database (creates zoom.db with sample data)
python seed.py

# Start the backend server
uvicorn main:app --reload --port 8000
```

**Backend will be live at:** `http://localhost:8000`  
**API Docs (Swagger):** `http://localhost:8000/docs`

### 2. Frontend Setup

```bash
cd Zoom/frontend

# Install dependencies (node_modules already present)
npm install

# Start dev server
npm run dev
```

**Frontend will be live at:** `http://localhost:3000`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me` | Get current default user |
| POST | `/api/meetings/instant` | Create instant meeting |
| POST | `/api/meetings/schedule` | Schedule a meeting |
| GET | `/api/meetings/upcoming` | List upcoming meetings |
| GET | `/api/meetings/recent` | List recent/past meetings |
| GET | `/api/meetings/{id}` | Get & validate a meeting |
| POST | `/api/meetings/{id}/join` | Join a meeting (add participant) |
| POST | `/api/meetings/{id}/leave` | Leave a meeting |
| POST | `/api/meetings/{id}/end` | End meeting for all |
| POST | `/api/meetings/{id}/participants/{name}/mute` | Host: mute/unmute participant |
| POST | `/api/meetings/{id}/participants/{name}/remove` | Host: remove participant |

---

## Sample Data (Seeded)

After running `python seed.py`:
- **Default user:** Aditi Arora (`aditi.arora@zoom.us`)
- **5 upcoming meetings** (1h, 6h, 26h, 48h, 72h from now)
- **5 past meetings** (24h, 48h, 72h, 120h, 168h ago)
- **6 users** with participant records

The default user is **automatically logged in** — no authentication required.

---

## Assumptions

1. **No authentication**: A default user (Aditi Arora) is assumed always logged in. The backend creates/fetches her on each request via `get_default_user`.
2. **WebRTC**: Real P2P video is simulated — actual webcam is captured locally via `getUserMedia`. Peer connections would require a TURN/STUN server in production.
3. **Real-time**: Chat and participant updates in the meeting room use a simulated model (setTimeout-based joins + auto-replies). Production would use WebSockets.
4. **Meeting IDs**: Generated in `xxx-xxx-xxxx` format (10 digits) similar to Zoom.
5. **Screen share**: Simulated UI overlay — no actual `getDisplayMedia` implementation.

---

## Folder Structure

```
Zoom/
├── backend/
│   ├── main.py          # FastAPI app + all API routes
│   ├── models.py        # SQLAlchemy ORM models
│   ├── schemas.py       # Pydantic schemas (request/response)
│   ├── database.py      # DB engine + session setup
│   ├── seed.py          # Database seeder
│   └── zoom.db          # SQLite database (auto-created)
│
└── frontend/
    ├── src/app/
    │   ├── page.tsx         # Dashboard (Zoom home UI)
    │   ├── dashboard.css    # Dashboard styles
    │   ├── globals.css      # Design tokens (colors, fonts, animations)
    │   ├── layout.tsx       # Root layout
    │   ├── room.css         # Meeting room styles
    │   └── room/[id]/
    │       └── page.tsx     # Meeting room page
    └── package.json
```
