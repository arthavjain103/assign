/**
 * SEED DATA - Profile Content
 * Used to populate user profile and settings
 * Generated: 2026-06-10
 */

const userProfile = {
  "userId": "user_123",
  "name": "You",
  "email": "user@nishaffs.app",
  "avatar": "assets/images/girl_avatar_1.png",
  "joinDate": "2026-06-01",
  "bio": "On a journey of self-discovery and growth 🌱",
  "stats": {
    "totalAffirmations": 156,
    "streakDays": 7,
    "communityPosts": 12,
    "diaryEntries": 24,
    "favoriteMood": "Happy"
  },
  "preferences": {
    "notificationsEnabled": true,
    "dailyReminderTime": "07:00",
    "theme": "Rose Garden",
    "language": "English",
    "privacyLevel": "Private",
    "shareStats": false
  }
};

const achievements = [
  {
    "id": "ach_001",
    "title": "First Step",
    "description": "Created your first affirmation",
    "icon": "🌱",
    "unlockedDate": "2026-06-01"
  },
  {
    "id": "ach_002",
    "title": "Consistency Champion",
    "description": "Maintained a 7-day streak",
    "icon": "🔥",
    "unlockedDate": "2026-06-08"
  },
  {
    "id": "ach_003",
    "title": "Community Voice",
    "description": "Posted your first community message",
    "icon": "📢",
    "unlockedDate": "2026-06-05"
  },
  {
    "id": "ach_004",
    "title": "Journal Keeper",
    "description": "Written 10 diary entries",
    "icon": "📔",
    "unlockedDate": "2026-06-07"
  },
  {
    "id": "ach_005",
    "title": "Peaceful Mind",
    "description": "Listened to meditation music for 60 minutes",
    "icon": "🧘",
    "unlockedDate": "2026-06-09"
  }
];

const notificationHistory = [
  {
    "id": "notif_001",
    "type": "reminder",
    "title": "Daily Affirmation Time!",
    "message": "Start your day with positive affirmations",
    "timestamp": "2026-06-10T07:00:00Z"
  },
  {
    "id": "notif_002",
    "type": "achievement",
    "title": "🔥 Streak Milestone!",
    "message": "You've reached a 7-day consistency streak!",
    "timestamp": "2026-06-08T18:30:00Z"
  },
  {
    "id": "notif_003",
    "type": "community",
    "title": "Someone liked your post!",
    "message": "Your affirmation post received 45 likes",
    "timestamp": "2026-06-09T14:22:00Z"
  },
  {
    "id": "notif_004",
    "type": "reminder",
    "title": "Meditation Moment",
    "message": "Try our new 432Hz healing frequency",
    "timestamp": "2026-06-10T12:00:00Z"
  }
];

export const profileData = { userProfile, achievements, notificationHistory };
