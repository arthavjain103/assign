"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import {
  // Sidebar icons
  Home, MessageSquare, Phone, Video, Users, Layout,
  FileText, Film, Grid, Settings,
  // Topbar
  Search, Bell, HelpCircle, ChevronDown,
  // Actions
  VideoIcon, PlusSquare, Calendar, Monitor,
  // Meeting rows
  Clock, Link, Copy, Trash2, MoreHorizontal,
  // Others
  Shield, X, Check, AlertCircle, ExternalLink,
  RefreshCw, Star, ChevronRight, Mic
} from "lucide-react";
import "./dashboard.css";
import { TeamChatView, ContactsView, WhiteboardsView, GenericGridContent } from "./components/TabViews";

// ─── Types ──────────────────────────────────────────────────────────────
interface User {
  id: number;
  username: string;
  email: string;
  avatar_url: string;
}

interface Meeting {
  id: number;
  uuid: string;
  meeting_id: string;
  title: string;
  description: string;
  invite_link: string;
  start_time: string | null;
  duration_minutes: number | null;
  is_scheduled: boolean;
  is_active: boolean;
  created_at: string;
  host?: User;
}

const API = "http://127.0.0.1:8000";

// ─── Nav Items ────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { id: "home",        icon: Home,         label: "Home",        active: true },
  { id: "chat",        icon: MessageSquare, label: "Team Chat",   badge: 3 },
  { id: "meetings",    icon: Video,         label: "Meetings" },
  { id: "contacts",    icon: Users,         label: "Contacts" },
  { id: "whiteboards", icon: Layout,        label: "Whiteboards" },
  { id: "notes",       icon: FileText,      label: "Notes" },
  { id: "clips",       icon: Film,          label: "Clips" },
  { id: "apps",        icon: Grid,          label: "Apps" },
];

// ─── Helpers ──────────────────────────────────────────────────────────────
function fmtTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}
function fmtDuration(mins: number | null) {
  if (!mins) return "";
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}
function initials(name: string) {
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
}
function isUpcoming(iso: string | null) {
  return iso ? new Date(iso) > new Date() : false;
}

// ─── Main Dashboard Component ────────────────────────────────────────────
export default function Dashboard() {
  const router = useRouter();

  // Data state
  const [currentUser, setCurrentUser]         = useState<User | null>(null);
  const [upcomingMeetings, setUpcomingMeetings] = useState<Meeting[]>([]);
  const [recentMeetings, setRecentMeetings]   = useState<Meeting[]>([]);
  const [loading, setLoading]                 = useState(true);
  const [activeNav, setActiveNav]             = useState("home");
  const [recentTab, setRecentTab]             = useState<"all" | "upcoming" | "past">("all");

  // Modal state
  const [showJoin, setShowJoin]               = useState(false);
  const [showSchedule, setShowSchedule]       = useState(false);
  const [toast, setToast]                     = useState("");

  // Join form
  const [joinId, setJoinId]                   = useState("");
  const [joinName, setJoinName]               = useState("");
  const [joinError, setJoinError]             = useState("");
  const [joinLoading, setJoinLoading]         = useState(false);

  // Schedule form
  const [schTitle, setSchTitle]               = useState("");
  const [schDesc, setSchDesc]                 = useState("");
  const [schDate, setSchDate]                 = useState("");
  const [schTime, setSchTime]                 = useState("");
  const [schDuration, setSchDuration]         = useState(30);
  const [schError, setSchError]               = useState("");
  const [schLoading, setSchLoading]           = useState(false);

  // ─── Data fetching ─────────────────────────────────────────────────
  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [userRes, upRes, recRes] = await Promise.all([
        fetch(`${API}/api/users/me`),
        fetch(`${API}/api/meetings/upcoming`),
        fetch(`${API}/api/meetings/recent`),
      ]);
      if (userRes.ok) setCurrentUser(await userRes.json());
      if (upRes.ok)   setUpcomingMeetings(await upRes.json());
      if (recRes.ok)  setRecentMeetings(await recRes.json());
    } catch (e) {
      console.error("API error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => { if (currentUser) setJoinName(currentUser.username); }, [currentUser]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 2500);
    return () => clearTimeout(t);
  }, [toast]);

  // ─── Handlers ──────────────────────────────────────────────────────
  const handleNewMeeting = async () => {
    try {
      const res = await fetch(`${API}/api/meetings/instant`, { method: "POST" });
      if (!res.ok) throw new Error();
      const meeting: Meeting = await res.json();
      const name = encodeURIComponent(currentUser?.username || "Host");
      router.push(`/room/${meeting.meeting_id}?name=${name}`);
    } catch {
      setToast("Failed to create meeting. Is the backend running?");
    }
  };

  const handleJoinSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoinError("");
    if (!joinId.trim() || !joinName.trim()) {
      setJoinError("Please fill in all required fields.");
      return;
    }

    let cleanId = joinId.trim();
    // Extract ID from invite link
    if (cleanId.includes("?")) {
      try {
        const url = new URL(cleanId.includes("http") ? cleanId : `http://x?${cleanId.split("?")[1]}`);
        cleanId = url.searchParams.get("id") || cleanId;
      } catch { /* keep as-is */ }
    }
    // Strip non-digit/dash
    cleanId = cleanId.replace(/[^0-9-]/g, "");

    setJoinLoading(true);
    try {
      const res = await fetch(`${API}/api/meetings/${cleanId}`);
      if (res.status === 404) { setJoinError("Invalid Meeting ID. No such meeting found."); return; }
      if (!res.ok)             { setJoinError("Could not verify meeting. Try again."); return; }
      const meeting: Meeting = await res.json();
      if (!meeting.is_active) { setJoinError("This meeting has already ended."); return; }
      setShowJoin(false);
      router.push(`/room/${meeting.meeting_id}?name=${encodeURIComponent(joinName)}`);
    } catch {
      setJoinError("Cannot connect to backend. Make sure it is running on port 8000.");
    } finally {
      setJoinLoading(false);
    }
  };

  const handleScheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSchError("");
    if (!schTitle.trim() || !schDate || !schTime) {
      setSchError("Title, date, and time are required.");
      return;
    }
    const startDt = new Date(`${schDate}T${schTime}`);
    if (startDt <= new Date()) {
      setSchError("Start time must be in the future.");
      return;
    }
    setSchLoading(true);
    try {
      const res = await fetch(`${API}/api/meetings/schedule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: schTitle,
          description: schDesc,
          start_time: startDt.toISOString(),
          duration_minutes: schDuration,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        setSchError(err.detail || "Failed to schedule meeting."); return;
      }
      setShowSchedule(false);
      resetScheduleForm();
      fetchAll();
      setToast("Meeting scheduled successfully!");
    } catch {
      setSchError("Cannot connect to backend.");
    } finally {
      setSchLoading(false);
    }
  };

  const copyToClipboard = (text: string, label = "Copied!") => {
    navigator.clipboard.writeText(text).then(() => setToast(label));
  };

  const resetScheduleForm = () => {
    setSchTitle(""); setSchDesc(""); setSchDate("");
    setSchTime(""); setSchDuration(30); setSchError("");
  };

  const filteredRecent = recentMeetings.filter(m => {
    if (recentTab === "upcoming") return isUpcoming(m.start_time);
    if (recentTab === "past")     return !isUpcoming(m.start_time) || !m.is_active;
    return true;
  });

  // ─── Today's min date for scheduling ───────────────────────────────
  const todayMin = new Date().toISOString().split("T")[0];

  // ─── Render ────────────────────────────────────────────────────────
  return (
    <div className="zoom-shell">

      {/* ── SIDEBAR ── */}
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            {/* Zoom logo SVG */}
            <svg width="28" height="28" viewBox="0 0 36 36" fill="none">
              <rect width="36" height="36" rx="6" fill="#0E72ED"/>
              <path d="M6 12.6C6 11.16 7.16 10 8.6 10h11.8C21.84 10 23 11.16 23 12.6v10.8C23 24.84 21.84 26 20.4 26H8.6C7.16 26 6 24.84 6 23.4V12.6Z" fill="white"/>
              <path d="M24.5 15.1L30 12v12l-5.5-3.1V15.1Z" fill="white"/>
            </svg>
          </div>
          <span className="sidebar-logo-text">Zoom</span>
        </div>

        {/* Nav */}
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`sidebar-nav-item ${activeNav === item.id ? "active" : ""}`}
              onClick={() => setActiveNav(item.id)}
            >
              <span className="sidebar-nav-icon">
                <item.icon size={18} strokeWidth={activeNav === item.id ? 2.5 : 1.8} />
              </span>
              {item.label}
              {item.badge && <span className="sidebar-nav-badge">{item.badge}</span>}
            </button>
          ))}

          <div className="sidebar-divider" />

          <button className="sidebar-nav-item" onClick={() => setActiveNav("settings")}>
            <span className="sidebar-nav-icon">
              <Settings size={18} strokeWidth={1.8} />
            </span>
            Settings
          </button>
        </nav>

        {/* Profile */}
        <div className="sidebar-profile">
          <div className="sidebar-avatar">
            {currentUser?.avatar_url ? (
              <Image src={currentUser.avatar_url} alt="avatar" width={34} height={34} style={{ borderRadius: "50%", objectFit: "cover" }} />
            ) : (
              <span>{currentUser ? initials(currentUser.username) : "AA"}</span>
            )}
          </div>
          <div className="sidebar-profile-info">
            <div className="sidebar-profile-name">{currentUser?.username || "Aditi Arora"}</div>
            <div className="sidebar-profile-status">● Online</div>
          </div>
          <ChevronDown size={14} color="var(--text-muted)" />
        </div>
      </aside>

      {/* ── MAIN AREA ── */}
      <div className="main-area">

        {/* TOPBAR */}
        <header className="topbar">
          <div className="topbar-search">
            <span className="topbar-search-icon">
              <Search size={15} />
            </span>
            <input
              className="topbar-search-input"
              type="text"
              placeholder="Search"
              aria-label="Search"
            />
          </div>

          <div className="topbar-actions">
            <button
              className="topbar-upgrade-btn"
              title="Upgrade plan"
            >
              <Star size={13} />
              Upgrade
            </button>

            <button className="topbar-icon-btn tooltip-btn" data-tip="Help" aria-label="Help">
              <HelpCircle size={18} strokeWidth={1.8} />
            </button>
            <button className="topbar-icon-btn tooltip-btn" data-tip="Notifications" aria-label="Notifications">
              <Bell size={18} strokeWidth={1.8} />
            </button>
            <button className="topbar-icon-btn tooltip-btn" data-tip="Settings" aria-label="Settings">
              <Settings size={18} strokeWidth={1.8} />
            </button>
            <div className="topbar-avatar">
              {currentUser?.avatar_url ? (
                <Image src={currentUser.avatar_url} alt="avatar" width={32} height={32} style={{ borderRadius: "50%", objectFit: "cover" }} />
              ) : (
                initials(currentUser?.username || "AA")
              )}
            </div>
          </div>
        </header>

        {/* PAGE CONTENT */}
        <main className="page-content" style={{ padding: activeNav === "home" ? undefined : 0, overflow: activeNav === "home" ? undefined : "hidden" }}>

          {activeNav === "home" && (
            <>
              {/* ── ACTION CARDS ── */}
              <section>
                <div className="action-grid">
                  {/* New Meeting */}
                  <button className="action-card orange" onClick={handleNewMeeting} aria-label="New Meeting">
                    <div className="action-card-icon-area">
                      <div className="action-card-icon-circle white">
                        <VideoIcon size={24} />
                      </div>
                    </div>
                    <div className="action-card-info">
                      <div className="action-card-title">New Meeting</div>
                      <div className="action-card-desc">Start an instant meeting</div>
                    </div>
                  </button>

                  {/* Join */}
                  <button
                    className="action-card blue"
                    onClick={() => setShowJoin(true)}
                    aria-label="Join Meeting"
                  >
                    <div className="action-card-icon-area">
                      <div className="action-card-icon-circle white">
                        <PlusSquare size={24} />
                      </div>
                    </div>
                    <div className="action-card-info">
                      <div className="action-card-title">Join</div>
                      <div className="action-card-desc">Join a meeting via ID or link</div>
                    </div>
                  </button>

                  {/* Schedule */}
                  <button
                    className="action-card blue"
                    onClick={() => setShowSchedule(true)}
                    aria-label="Schedule Meeting"
                  >
                    <div className="action-card-icon-area">
                      <div className="action-card-icon-circle white">
                        <Calendar size={24} />
                      </div>
                    </div>
                    <div className="action-card-info">
                      <div className="action-card-title">Schedule</div>
                      <div className="action-card-desc">Plan a future meeting</div>
                    </div>
                  </button>

                  {/* Share Screen */}
                  <button
                    className="action-card blue"
                    onClick={() => setToast("Share Screen: Start a meeting then use the Share button inside.")}
                    aria-label="Share Screen"
                  >
                    <div className="action-card-icon-area">
                      <div className="action-card-icon-circle white">
                        <Monitor size={24} />
                      </div>
                    </div>
                    <div className="action-card-info">
                      <div className="action-card-title">Share Screen</div>
                      <div className="action-card-desc">Share without video call</div>
                    </div>
                  </button>
                </div>
              </section>

              {/* ── CONTENT GRID ── */}
              <div className="content-grid">

                {/* UPCOMING MEETINGS */}
                <section>
                  <div className="section-header">
                    <h2 className="section-title">Upcoming</h2>
                    <button className="section-link" onClick={() => setShowSchedule(true)}>+ Schedule</button>
                  </div>
                  <div className="meetings-card">
                    <div className="meetings-card-header">
                      <span className="meetings-card-title">Upcoming Meetings</span>
                      <button className="btn-icon-sm tooltip-btn" data-tip="Refresh" onClick={fetchAll}>
                        <RefreshCw size={14} />
                      </button>
                    </div>
                    <div className="meetings-list">
                      {loading ? (
                        <div className="loading-row">
                          <div className="spinner" />
                          Loading meetings…
                        </div>
                      ) : upcomingMeetings.length === 0 ? (
                        <div className="empty-state">
                          <Calendar size={32} strokeWidth={1} style={{ opacity: 0.25 }} />
                          <div className="empty-state-text">No upcoming meetings</div>
                          <div className="empty-state-sub">
                            <button className="section-link" onClick={() => setShowSchedule(true)}>Schedule a meeting</button>
                          </div>
                        </div>
                      ) : (
                        upcomingMeetings.map(m => (
                          <div key={m.id} className="meeting-row">
                            <div className="meeting-row-time-col">
                              <span className="meeting-row-time">
                                {m.start_time ? fmtTime(m.start_time).replace(/(AM|PM)/, "") : "–"}
                              </span>
                              <span className="meeting-row-ampm">
                                {m.start_time ? (new Date(m.start_time).getHours() >= 12 ? "PM" : "AM") : ""}
                              </span>
                            </div>
                            <div className="meeting-row-divider" />
                            <div className="meeting-row-info">
                              <div className="meeting-row-title">{m.title}</div>
                              <div className="meeting-row-meta">
                                <Clock size={11} />
                                {m.start_time ? fmtDate(m.start_time) : "—"}
                                {m.duration_minutes ? ` · ${fmtDuration(m.duration_minutes)}` : ""}
                              </div>
                              <div className="meeting-row-id">{m.meeting_id}</div>
                            </div>
                            <div className="meeting-row-actions">
                              <button
                                className="btn-icon-sm tooltip-btn"
                                data-tip="Copy invite link"
                                onClick={() => copyToClipboard(m.invite_link, "Invite link copied!")}
                              >
                                <Link size={13} />
                              </button>
                              <button
                                className="btn-start"
                                onClick={() => router.push(`/room/${m.meeting_id}?name=${encodeURIComponent(currentUser?.username || "Host")}`)}
                              >
                                Start
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </section>

                {/* RECENT MEETINGS */}
                <section>
                  <div className="section-header">
                    <h2 className="section-title">Recent</h2>
                  </div>
                  <div className="meetings-card">
                    <div className="tabs-row">
                      {(["all", "upcoming", "past"] as const).map(tab => (
                        <button
                          key={tab}
                          className={`tab-item ${recentTab === tab ? "active" : ""}`}
                          onClick={() => setRecentTab(tab)}
                        >
                          {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                      ))}
                    </div>
                    <div className="meetings-list">
                      {loading ? (
                        <div className="loading-row">
                          <div className="spinner" />
                          Loading…
                        </div>
                      ) : filteredRecent.length === 0 ? (
                        <div className="empty-state">
                          <Clock size={32} strokeWidth={1} style={{ opacity: 0.25 }} />
                          <div className="empty-state-text">No meetings here</div>
                        </div>
                      ) : (
                        filteredRecent.map(m => (
                          <div key={m.id} className="recent-row">
                            <div className="recent-icon">
                              <Video size={15} strokeWidth={1.8} />
                            </div>
                            <div className="recent-info">
                              <div className="recent-title">{m.title}</div>
                              <div className="recent-meta">
                                {m.start_time ? `${fmtDate(m.start_time)}, ${fmtTime(m.start_time)}` : `Created ${fmtDate(m.created_at)}`}
                                {m.duration_minutes ? ` · ${fmtDuration(m.duration_minutes)}` : ""}
                              </div>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <span className={`recent-badge ${m.is_active && isUpcoming(m.start_time) ? "active" : "ended"}`}>
                                {m.is_active && isUpcoming(m.start_time) ? "Scheduled" : "Past"}
                              </span>
                              <button
                                className="btn-icon-sm tooltip-btn"
                                data-tip="Copy invite"
                                onClick={() => copyToClipboard(m.invite_link, "Copied!")}
                              >
                                <Copy size={12} />
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </section>
              </div>

              {/* ── PERSONAL MEETING ID ── */}
              <section>
                <div className="pmi-banner">
                  <div>
                    <div className="pmi-label">Personal Meeting ID</div>
                    <div className="pmi-id">
                      {currentUser?.id
                        ? `${String(currentUser.id).padStart(3, "0")}-${Math.floor(Math.random() * 900 + 100)}-${Math.floor(Math.random() * 9000 + 1000)}`
                        : "839-201-9482"}
                    </div>
                  </div>
                  <div className="pmi-actions">
                    <button
                      className="btn-outline"
                      onClick={() => copyToClipboard("http://localhost:3000/join?id=839-201-9482", "Personal link copied!")}
                    >
                      <Copy size={13} />
                      Copy Invite Link
                    </button>
                    <button className="btn-primary" onClick={handleNewMeeting}>
                      <VideoIcon size={13} />
                      Start Meeting
                    </button>
                  </div>
                </div>
              </section>
            </>
          )}

          {activeNav === "chat" && <TeamChatView />}
          {activeNav === "contacts" && <ContactsView />}
          {activeNav === "whiteboards" && <WhiteboardsView />}
          {activeNav === "notes" && <GenericGridContent title="Notes" icon={FileText} desc="Document your meeting notes seamlessly." />}
          {activeNav === "clips" && <GenericGridContent title="Clips" icon={Film} desc="Short form asynchronous team video messages." />}
          {activeNav === "apps" && <GenericGridContent title="Apps" icon={Grid} desc="Integrate essential applications directly into Zoom." />}
          {activeNav === "meetings" && <GenericGridContent title="Meetings" icon={Video} desc="View and manage all your scheduled events." />}
          {activeNav === "settings" && <GenericGridContent title="Settings" icon={Settings} desc="Configure your ZoomConnect preferences." />}


        </main>
      </div>

      {/* ── JOIN MEETING MODAL ── */}
      {showJoin && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Join Meeting">
          <div className="modal-box">
            <div className="modal-header">
              <span className="modal-title">Join Meeting</span>
              <button className="modal-close" onClick={() => { setShowJoin(false); setJoinError(""); }} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleJoinSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label" htmlFor="join-id">
                    Meeting ID or Personal Link Name <span>*</span>
                  </label>
                  <input
                    id="join-id"
                    type="text"
                    className="form-input"
                    placeholder="123-456-7890 or zoom.com/j/..."
                    value={joinId}
                    onChange={e => { setJoinId(e.target.value); setJoinError(""); }}
                    autoFocus
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="join-name">
                    Your Name <span>*</span>
                  </label>
                  <input
                    id="join-name"
                    type="text"
                    className="form-input"
                    placeholder="Enter your display name"
                    value={joinName}
                    onChange={e => { setJoinName(e.target.value); setJoinError(""); }}
                    maxLength={40}
                    required
                  />
                </div>
                {joinError && (
                  <div className="form-error">
                    <AlertCircle size={13} />
                    {joinError}
                  </div>
                )}
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text-muted)" }}>
                  <Shield size={12} />
                  Zoom encrypts your meeting end-to-end.
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-outline" onClick={() => { setShowJoin(false); setJoinError(""); }}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={joinLoading}>
                  {joinLoading ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Verifying…</> : "Join"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── SCHEDULE MEETING MODAL ── */}
      {showSchedule && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Schedule Meeting">
          <div className="modal-box" style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <span className="modal-title">Schedule Meeting</span>
              <button className="modal-close" onClick={() => { setShowSchedule(false); setSchError(""); resetScheduleForm(); }} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleScheduleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label" htmlFor="sch-title">
                    Topic <span>*</span>
                  </label>
                  <input
                    id="sch-title"
                    type="text"
                    className="form-input"
                    placeholder="e.g. Weekly Team Standup"
                    value={schTitle}
                    onChange={e => setSchTitle(e.target.value)}
                    autoFocus
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="sch-desc">Description (optional)</label>
                  <textarea
                    id="sch-desc"
                    className="form-textarea"
                    placeholder="Add a meeting description or agenda…"
                    value={schDesc}
                    onChange={e => setSchDesc(e.target.value)}
                  />
                </div>

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label" htmlFor="sch-date">Date <span>*</span></label>
                    <input
                      id="sch-date"
                      type="date"
                      className="form-input"
                      min={todayMin}
                      value={schDate}
                      onChange={e => setSchDate(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label" htmlFor="sch-time">Time <span>*</span></label>
                    <input
                      id="sch-time"
                      type="time"
                      className="form-input"
                      value={schTime}
                      onChange={e => setSchTime(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="sch-duration">Duration</label>
                  <select
                    id="sch-duration"
                    className="form-select"
                    value={schDuration}
                    onChange={e => setSchDuration(Number(e.target.value))}
                  >
                    <option value={15}>15 minutes</option>
                    <option value={30}>30 minutes</option>
                    <option value={45}>45 minutes</option>
                    <option value={60}>1 hour</option>
                    <option value={90}>1.5 hours</option>
                    <option value={120}>2 hours</option>
                    <option value={180}>3 hours</option>
                  </select>
                </div>

                {schError && (
                  <div className="form-error">
                    <AlertCircle size={13} />
                    {schError}
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button type="button" className="btn-outline" onClick={() => { setShowSchedule(false); resetScheduleForm(); }}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={schLoading}>
                  {schLoading
                    ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Saving…</>
                    : <><Calendar size={13} /> Schedule</>
                  }
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── TOAST ── */}
      {toast && (
        <div className="copy-toast" role="status">
          <Check size={12} style={{ display: "inline", marginRight: 6 }} />
          {toast}
        </div>
      )}
    </div>
  );
}
