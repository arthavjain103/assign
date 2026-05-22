"""
seed.py — Zoom Clone Database Seeder
Run: python seed.py
Drops all tables, recreates them, and inserts rich sample data.
"""
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base
import models


def generate_meeting_id() -> str:
    """Returns a Zoom-style meeting ID: xxx-xxx-xxxx"""
    d = [str(random.randint(0, 9)) for _ in range(10)]
    return f"{''.join(d[:3])}-{''.join(d[3:6])}-{''.join(d[6:])}"


def seed_database():
    print("=" * 50)
    print("ZoomConnect — Database Seeder")
    print("=" * 50)

    # Reset schema
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created")

    db: Session = SessionLocal()
    try:
        # ── 1. Default user (always logged in) ──────────────────
        default_user = models.User(
            username="Aditi Arora",
            email="aditi.arora@zoom.us",
            avatar_url=(
                "https://images.unsplash.com/photo-1494790108377-be9c29b29330"
                "?auto=format&fit=crop&q=80&w=120"
            ),
        )
        db.add(default_user)
        db.commit()
        db.refresh(default_user)
        print(f"✓ Default user seeded: {default_user.username} (id={default_user.id})")

        # ── 2. Additional users (for participant records) ────────
        extra_users_data = [
            {"username": "Rahul Singh",   "email": "rahul.singh@corp.in"},
            {"username": "Priya Sharma",  "email": "priya.sharma@corp.in"},
            {"username": "Arjun Kapoor",  "email": "arjun.kapoor@corp.in"},
            {"username": "Sneha Joshi",   "email": "sneha.joshi@corp.in"},
            {"username": "Karan Malhotra","email": "karan.malhotra@corp.in"},
        ]
        extra_users = []
        for u in extra_users_data:
            user = models.User(username=u["username"], email=u["email"])
            db.add(user)
            extra_users.append(user)
        db.commit()
        for u in extra_users:
            db.refresh(u)
        print(f"✓ {len(extra_users)} extra users seeded")

        # ── 3. Upcoming scheduled meetings ───────────────────────
        now = datetime.utcnow()
        upcoming_data = [
            {
                "title":       "Weekly Sync & Project Review",
                "description": "Sprint progress review and upcoming milestone planning.",
                "offset_h":    1,
                "duration":    45,
                "attendees":   ["Rahul Singh", "Priya Sharma"],
            },
            {
                "title":       "Product Brainstorming — Q2 Features",
                "description": "Ideating new features for the Zoom Clone assignment.",
                "offset_h":    6,
                "duration":    60,
                "attendees":   ["Arjun Kapoor", "Sneha Joshi", "Karan Malhotra"],
            },
            {
                "title":       "1-on-1 Sync with Tech Lead",
                "description": "Career growth, code reviews, and architecture feedback.",
                "offset_h":    26,
                "duration":    30,
                "attendees":   ["Rahul Singh"],
            },
            {
                "title":       "Design System Workshop",
                "description": "Establishing Zoom-exact design tokens and component library.",
                "offset_h":    48,
                "duration":    90,
                "attendees":   ["Priya Sharma", "Arjun Kapoor"],
            },
            {
                "title":       "All Hands — Engineering Update",
                "description": "Company-wide engineering update and Q2 roadmap.",
                "offset_h":    72,
                "duration":    60,
                "attendees":   ["Rahul Singh", "Priya Sharma", "Arjun Kapoor", "Sneha Joshi", "Karan Malhotra"],
            },
        ]

        for m in upcoming_data:
            mid = generate_meeting_id()
            start = now + timedelta(hours=m["offset_h"])
            meeting = models.Meeting(
                meeting_id=mid,
                title=m["title"],
                description=m["description"],
                host_id=default_user.id,
                invite_link=f"http://localhost:3000/join?id={mid}",
                start_time=start,
                duration_minutes=m["duration"],
                is_scheduled=True,
                is_active=True,
            )
            db.add(meeting)
            db.commit()
            db.refresh(meeting)

            # Seed host as participant
            db.add(models.Participant(
                meeting_id=meeting.id,
                user_id=default_user.id,
                display_name=default_user.username,
                is_host=True,
                is_muted=False,
                is_video_off=False,
            ))

            # Seed attendees
            for name in m["attendees"]:
                u = next((x for x in extra_users if x.username == name), None)
                db.add(models.Participant(
                    meeting_id=meeting.id,
                    user_id=u.id if u else None,
                    display_name=name,
                    is_host=False,
                    is_muted=False,
                    is_video_off=False,
                ))

            print(f"  ↑ Upcoming: {m['title']} at +{m['offset_h']}h  ID: {mid}")

        db.commit()

        # ── 4. Recent / past meetings ─────────────────────────────
        past_data = [
            {
                "title":       "Yesterday's Daily Standup",
                "description": "Daily status updates on API endpoints.",
                "offset_h":    -24,
                "duration":    15,
                "attendees":   ["Rahul Singh", "Priya Sharma", "Arjun Kapoor"],
            },
            {
                "title":       "Sprint Planning — Q2 Kickoff",
                "description": "Defined user stories, acceptance criteria, and sprint goals.",
                "offset_h":    -48,
                "duration":    90,
                "attendees":   ["Rahul Singh", "Priya Sharma", "Arjun Kapoor", "Sneha Joshi"],
            },
            {
                "title":       "Backend Architecture Review",
                "description": "SQLAlchemy schema review and FastAPI router design.",
                "offset_h":    -72,
                "duration":    60,
                "attendees":   ["Arjun Kapoor", "Karan Malhotra"],
            },
            {
                "title":       "UI/UX Walkthrough — Dashboard",
                "description": "Pixel-perfect review of Zoom dashboard replication.",
                "offset_h":    -120,
                "duration":    45,
                "attendees":   ["Priya Sharma", "Sneha Joshi"],
            },
            {
                "title":       "Project Kick-off Meeting",
                "description": "Discussed project requirements and tech stack selection.",
                "offset_h":    -168,
                "duration":    30,
                "attendees":   ["Rahul Singh", "Priya Sharma", "Arjun Kapoor", "Sneha Joshi", "Karan Malhotra"],
            },
        ]

        for m in past_data:
            mid = generate_meeting_id()
            start = now + timedelta(hours=m["offset_h"])
            meeting = models.Meeting(
                meeting_id=mid,
                title=m["title"],
                description=m["description"],
                host_id=default_user.id,
                invite_link=f"http://localhost:3000/join?id={mid}",
                start_time=start,
                duration_minutes=m["duration"],
                is_scheduled=True,
                is_active=False,
                created_at=start,
            )
            db.add(meeting)
            db.commit()
            db.refresh(meeting)

            end_time = start + timedelta(minutes=m["duration"])

            # Host participant
            db.add(models.Participant(
                meeting_id=meeting.id,
                user_id=default_user.id,
                display_name=default_user.username,
                is_host=True,
                is_muted=False,
                is_video_off=False,
                joined_at=start,
                left_at=end_time,
            ))

            # Attendee participants
            for name in m["attendees"]:
                u = next((x for x in extra_users if x.username == name), None)
                db.add(models.Participant(
                    meeting_id=meeting.id,
                    user_id=u.id if u else None,
                    display_name=name,
                    is_host=False,
                    is_muted=True,
                    is_video_off=random.choice([True, False]),
                    joined_at=start + timedelta(minutes=random.randint(0, 3)),
                    left_at=end_time,
                ))

            print(f"  ↓ Past:     {m['title']} ({m['offset_h']}h ago) ID: {mid}")

        db.commit()
        print("\n✓ Database seeding completed successfully!")
        print(f"  • 1 default user: {default_user.username}")
        print(f"  • 5 extra users")
        print(f"  • 5 upcoming meetings")
        print(f"  • 5 past meetings")
        print("\nRun: uvicorn main:app --reload --port 8000")

    except Exception as e:
        db.rollback()
        print(f"\n✗ Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
