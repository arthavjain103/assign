"use client";

import { useState, useEffect, useRef, use } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Mic, MicOff, Video, VideoOff,
  Users, MessageSquare, MoreHorizontal,
  PhoneOff, Shield, ChevronUp,
  Send, X, Copy, Link, LayoutGrid,
  UserPlus, SmilePlus, Circle, Star, Headphones
} from "lucide-react";

// Icon aliases for Zoom-like naming clarity
const ScreenShare = Video;        // share-screen visual substitute
const CircleDot   = Circle;       // recording indicator
const Crown       = Star;         // host crown indicator
import "../../room.css";
import "../../room_extras.css";

// ─── Types ──────────────────────────────────────────────────────────────
interface Participant {
  id?: number;
  display_name: string;
  is_host: boolean;
  is_muted: boolean;
  is_video_off: boolean;
}

interface ChatMessage {
  id: number;
  sender: string;
  text: string;
  time: string;
  isMe: boolean;
  isSystem: boolean;
}

interface FloatingEmoji {
  id: number;
  emoji: string;
  x: number;
}

type PanelType = "participants" | "chat" | "apps" | null;

const API = "http://127.0.0.1:8000";

// ─── Helpers ──────────────────────────────────────────────────────────
function initials(name: string) {
  return name.split(" ").slice(0, 2).map(n => n[0]).join("").toUpperCase() || "??";
}

function formatTimer(sec: number) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

// Avatar color palette per participant
const COLORS = [
  "#0E72ED", "#F26D21", "#7C3AED", "#059669",
  "#DC2626", "#0891B2", "#D97706", "#BE185D",
];
function avatarColor(name: string) {
  let hash = 0;
  for (const c of name) hash = (hash * 31 + c.charCodeAt(0)) % COLORS.length;
  return COLORS[Math.abs(hash)];
}

// Simulated participants entering
const SIM_PARTICIPANTS: Participant[] = [
  { display_name: "Priya Sharma",    is_host: false, is_muted: true,  is_video_off: false },
  { display_name: "Rohan Mehta",     is_host: false, is_muted: false, is_video_off: true  },
  { display_name: "Anika Verma",     is_host: false, is_muted: false, is_video_off: false },
];

// ─── Component ───────────────────────────────────────────────────────────
export default function MeetingRoom({ params }: { params: Promise<{ id: string }> }) {
  const { id: meetingId } = use(params);
  const router            = useRouter();
  const searchParams      = useSearchParams();
  const displayName       = searchParams.get("name") || "Participant";

  // Meeting state
  const [meetingTitle, setMeetingTitle] = useState("Zoom Meeting");
  const [elapsed,      setElapsed]      = useState(0);
  const [isHost,       setIsHost]       = useState(false);

  // AV state
  const [isMuted,    setIsMuted]    = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [isSharing,  setIsSharing]  = useState(false);
  const [isRecording,setIsRecording]= useState(false);
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Participants & chat
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput,    setChatInput]    = useState("");
  const [unread,       setUnread]       = useState(0);

  // Panel view
  const [activePanel, setActivePanel] = useState<PanelType>(null);

  // Reactions
  const [showReactions,    setShowReactions]    = useState(false);
  const [floatingEmojis,   setFloatingEmojis]   = useState<FloatingEmoji[]>([]);

  // Modals & Popups
  const [showEndModal,   setShowEndModal]   = useState(false);
  const [showAudioModal, setShowAudioModal] = useState(true);
  const [audioJoined,    setAudioJoined]    = useState(false);
  const [copied,         setCopied]         = useState(false);

  // Chat auto-scroll
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ─── Init & cleanup ──────────────────────────────────────────────
  useEffect(() => {
    initMeeting();
    return () => stopMedia();
    // eslint-disable-next-line
  }, []);

  async function initMeeting() {
    try {
      const res = await fetch(`${API}/api/meetings/${meetingId}`);
      if (!res.ok) { router.push("/"); return; }
      const meeting = await res.json();
      setMeetingTitle(meeting.title || "Zoom Meeting");

      const joinRes = await fetch(`${API}/api/meetings/${meetingId}/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName }),
      });
      if (joinRes.ok) {
        const part = await joinRes.json();
        setIsHost(part.is_host);
        setParticipants([{
          display_name: displayName,
          is_host: part.is_host,
          is_muted: false,
          is_video_off: false,
        }]);
      }

      // Start camera
      await startCamera();

      // Simulate participants joining
      SIM_PARTICIPANTS.forEach((p, i) => {
        setTimeout(() => {
          setParticipants(prev => [...prev, p]);
          addSystemMsg(`${p.display_name} joined the meeting.`);
        }, (i + 1) * 4000);
      });

    } catch (e) {
      console.error("Init meeting error:", e);
      // Even without API, show the room
      setParticipants([{ display_name: displayName, is_host: true, is_muted: false, is_video_off: false }]);
      setIsHost(true);
      startCamera();
    }
  }

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      setLocalStream(stream);
      if (videoRef.current) videoRef.current.srcObject = stream;
    } catch {
      setIsVideoOff(true);
    }
  }

  function stopMedia() {
    localStream?.getTracks().forEach(t => t.stop());
  }

  // ─── Timer ────────────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(id);
  }, []);

  // ─── Chat auto-scroll ─────────────────────────────────────────────
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // ─── Unread counter ──────────────────────────────────────────────
  useEffect(() => {
    if (activePanel === "chat") setUnread(0);
  }, [activePanel]);

  // ─── Helpers ─────────────────────────────────────────────────────
  function addSystemMsg(text: string) {
    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    setChatMessages(prev => [...prev, { id: Date.now() + Math.random(), sender: "System", text, time: now, isMe: false, isSystem: true }]);
    if (activePanel !== "chat") setUnread(u => u + 1);
  }

  function addChatMsg(sender: string, text: string, isMe: boolean) {
    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    setChatMessages(prev => [...prev, { id: Date.now() + Math.random(), sender, text, time: now, isMe, isSystem: false }]);
    if (!isMe && activePanel !== "chat") setUnread(u => u + 1);
  }

  // ─── AV Controls ─────────────────────────────────────────────────
  function toggleMic() {
    if (localStream) {
      const track = localStream.getAudioTracks()[0];
      if (track) { track.enabled = !track.enabled; setIsMuted(!track.enabled); return; }
    }
    setIsMuted(m => !m);
  }

  function toggleVideo() {
    if (localStream) {
      const track = localStream.getVideoTracks()[0];
      if (track) {
        track.enabled = !track.enabled;
        setIsVideoOff(!track.enabled);
        return;
      }
    }
    setIsVideoOff(v => !v);
  }

  function toggleScreenShare() {
    setIsSharing(s => !s);
    if (!isSharing) addSystemMsg("You started sharing your screen.");
    else addSystemMsg("You stopped sharing your screen.");
  }

  function toggleRecording() {
    setIsRecording(r => {
      if (!r) addSystemMsg("Recording started by the host.");
      else   addSystemMsg("Recording stopped.");
      return !r;
    });
  }

  // ─── Panel toggle ─────────────────────────────────────────────────
  function togglePanel(panel: PanelType) {
    setActivePanel(prev => prev === panel ? null : panel);
    if (panel === "chat") setUnread(0);
  }

  // ─── Reactions ────────────────────────────────────────────────────
  function sendReaction(emoji: string) {
    const id = Date.now();
    const x  = 20 + Math.random() * 60;
    setFloatingEmojis(prev => [...prev, { id, emoji, x }]);
    setTimeout(() => setFloatingEmojis(prev => prev.filter(e => e.id !== id)), 2800);
    setShowReactions(false);
  }

  // ─── Chat message ──────────────────────────────────────────────────
  function handleSendChat(e: React.FormEvent) {
    e.preventDefault();
    if (!chatInput.trim()) return;
    addChatMsg(displayName, chatInput.trim(), true);
    setChatInput("");

    // Simulate a reply
    const others = participants.filter(p => p.display_name !== displayName);
    if (others.length > 0) {
      const REPLIES = ["Got it, thanks!", "Sounds good!", "Can you elaborate?", "Great point!", "Let's discuss offline."];
      setTimeout(() => {
        const r = others[Math.floor(Math.random() * others.length)];
        addChatMsg(r.display_name, REPLIES[Math.floor(Math.random() * REPLIES.length)], false);
      }, 2500 + Math.random() * 1500);
    }
  }

  // ─── Host controls ─────────────────────────────────────────────────
  async function muteParticipant(pName: string, currentMuted: boolean) {
    try {
      await fetch(`${API}/api/meetings/${meetingId}/participants/${encodeURIComponent(pName)}/mute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_muted: !currentMuted }),
      });
    } catch { /* offline mode */ }
    setParticipants(prev => prev.map(p => p.display_name === pName ? { ...p, is_muted: !currentMuted } : p));
    addSystemMsg(`${pName} was ${!currentMuted ? "muted" : "unmuted"} by the host.`);
  }

  async function removeParticipant(pName: string) {
    try {
      await fetch(`${API}/api/meetings/${meetingId}/participants/${encodeURIComponent(pName)}/remove`, { method: "POST" });
    } catch { /* offline */ }
    setParticipants(prev => prev.filter(p => p.display_name !== pName));
    addSystemMsg(`${pName} was removed from the meeting.`);
  }

  function muteAll() {
    setParticipants(prev => prev.map(p => p.display_name === displayName ? p : { ...p, is_muted: true }));
    addSystemMsg("All participants were muted by the host.");
  }

  // ─── Leave / End ────────────────────────────────────────────────────
  async function handleExit(action: "leave" | "end") {
    stopMedia();
    try {
      if (action === "end") {
        await fetch(`${API}/api/meetings/${meetingId}/end`, { method: "POST" });
      } else {
        await fetch(`${API}/api/meetings/${meetingId}/leave?display_name=${encodeURIComponent(displayName)}`, { method: "POST" });
      }
    } catch { /* offline */ }
    router.push("/");
  }

  // ─── Copy invite ─────────────────────────────────────────────────
  function copyInviteLink() {
    const link = `http://localhost:3000/room/${meetingId}?name=Guest`;
    navigator.clipboard.writeText(link).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  // ─── Grid class ─────────────────────────────────────────────────
  function gridClass(count: number) {
    if (count === 1) return "count-1";
    if (count === 2) return "count-2";
    if (count === 3) return "count-3";
    if (count === 4) return "count-4";
    return "count-many";
  }

  // ─── Render ──────────────────────────────────────────────────────
  return (
    <div className="room-shell">

      {/* Floating Emojis */}
      <div className="floating-reactions-container">
        {floatingEmojis.map(e => (
          <span
            key={e.id}
            className="floating-emoji"
            style={{ left: `${e.x}%` }}
          >
            {e.emoji}
          </span>
        ))}
      </div>

      {/* ── MAIN STAGE ── */}
      <div className="room-stage">

        {/* Header */}
        <header className="room-header">
          <div className="room-header-left">
            <button className="room-header-security">
              <Shield size={13} />
              Encrypted
            </button>
            <span className="room-header-title">{meetingTitle}</span>
          </div>

          <div className="room-header-center">
            {isRecording && (
              <div className="recording-indicator">
                <div className="record-dot" />
                Recording
              </div>
            )}
            <span className="room-header-time">{formatTimer(elapsed)}</span>
          </div>

          <div className="room-header-right">
            <button className="room-header-btn" onClick={copyInviteLink}>
              {copied ? <><Copy size={13} /> Copied!</> : <><Link size={13} /> Copy Invite</>}
            </button>
            <button className="room-header-btn" onClick={() => togglePanel("participants")}>
              <Users size={13} />
              {participants.length}
            </button>
          </div>
        </header>

        {/* Screen share overlay */}
        {isSharing && (
          <div className="screenshare-overlay">
            <div className="screenshare-inner">
              <ScreenShare size={48} strokeWidth={1.2} color="#60A5FA" />
              <h2>Sharing your screen</h2>
              <p>Other participants can see your screen content.</p>
              <button
                style={{
                  marginTop: 8, padding: "8px 20px", borderRadius: 8,
                  background: "var(--zoom-red)", color: "#fff",
                  fontWeight: 600, fontSize: 13, cursor: "pointer", border: "none"
                }}
                onClick={toggleScreenShare}
              >
                Stop Sharing
              </button>
            </div>
          </div>
        )}

        {/* Video Grid */}
        <div className="room-video-area">
          <div className={`video-grid ${gridClass(participants.length)}`}>

            {/* Local (self) tile */}
            <div className="video-card">
              {!isVideoOff && localStream ? (
                <video ref={videoRef} autoPlay playsInline muted className="video-feed" />
              ) : (
                <div className="video-avatar">
                  <div className="avatar-circle" style={{ background: avatarColor(displayName) }}>
                    {initials(displayName)}
                  </div>
                  <span className="avatar-label">Camera off</span>
                </div>
              )}
              <div className="video-card-name">
                {isHost && <Crown size={11} color="#FBBF24" />}
                <span className="video-card-name-text">{displayName} (You)</span>
              </div>
              {isMuted && (
                <div className="video-card-indicators">
                  <div className="indicator-pill"><MicOff size={11} /></div>
                </div>
              )}
            </div>

            {/* Remote participants */}
            {participants.filter(p => p.display_name !== displayName).map((p, idx) => (
              <div key={idx} className="video-card">
                <div className="video-avatar">
                  <div
                    className="avatar-circle"
                    style={{
                      background: avatarColor(p.display_name),
                      animation: !p.is_muted ? "pulse 3s 1s ease-in-out infinite" : "none",
                    }}
                  >
                    {initials(p.display_name)}
                  </div>
                  {p.is_video_off && <span className="avatar-label">Camera off</span>}
                </div>
                <div className="video-card-name">
                  {p.is_host && <Crown size={11} color="#FBBF24" />}
                  <span className="video-card-name-text">{p.display_name}</span>
                </div>
                {p.is_muted && (
                  <div className="video-card-indicators">
                    <div className="indicator-pill"><MicOff size={11} /></div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* ── CONTROL BAR ── */}
        <footer className="control-bar">
          {/* Group 1: AV */}
          <div className="control-group">
            {/* Mic / Join Audio split button */}
            <div className="ctrl-split">
              {!audioJoined ? (
                <button
                  className="ctrl-btn"
                  onClick={() => setShowAudioModal(true)}
                  aria-label="Join Audio"
                >
                  <div className="ctrl-btn-icon">
                    <Headphones size={20} color="#22C55E" />
                  </div>
                  <span className="ctrl-btn-label">Join Audio</span>
                </button>
              ) : (
                <button
                  className={`ctrl-btn ${isMuted ? "muted" : ""}`}
                  onClick={toggleMic}
                  aria-label={isMuted ? "Unmute" : "Mute"}
                >
                  <div className="ctrl-btn-icon">
                    {isMuted ? <MicOff size={20} /> : <Mic size={20} />}
                  </div>
                  <span className="ctrl-btn-label">{isMuted ? "Unmute" : "Mute"}</span>
                </button>
              )}
              <button className="ctrl-caret" aria-label="Audio options">
                <ChevronUp size={12} />
              </button>
            </div>

            {/* Video split button */}
            <div className="ctrl-split">
              <button
                className={`ctrl-btn ${isVideoOff ? "muted" : ""}`}
                onClick={toggleVideo}
                aria-label={isVideoOff ? "Start Video" : "Stop Video"}
              >
                <div className="ctrl-btn-icon">
                  {isVideoOff ? <VideoOff size={20} /> : <Video size={20} />}
                </div>
                <span className="ctrl-btn-label">{isVideoOff ? "Start Video" : "Stop Video"}</span>
              </button>
              <button className="ctrl-caret" aria-label="Video options">
                <ChevronUp size={12} />
              </button>
            </div>
          </div>

          {/* Group 2: Features */}
          <div className="control-group">
            {/* Security -> Host Tools (If Host) */}
            {isHost && (
              <button className="ctrl-btn" aria-label="Host tools">
                <div className="ctrl-btn-icon"><Shield size={20} /></div>
                <span className="ctrl-btn-label">Host tools</span>
              </button>
            )}

            {/* Participants */}
            <button
              className={`ctrl-btn ${activePanel === "participants" ? "active" : ""}`}
              onClick={() => togglePanel("participants")}
              aria-label="Participants"
            >
              <div className="ctrl-btn-icon">
                <Users size={20} />
                <span className="ctrl-badge">{participants.length}</span>
              </div>
              <span className="ctrl-btn-label">Participants</span>
            </button>

            {/* Chat */}
            <button
              className={`ctrl-btn ${activePanel === "chat" ? "active" : ""}`}
              onClick={() => togglePanel("chat")}
              aria-label="Chat"
            >
              <div className="ctrl-btn-icon">
                <MessageSquare size={20} />
                {unread > 0 && <span className="ctrl-badge" style={{ background: "#22C55E" }}>{unread}</span>}
              </div>
              <span className="ctrl-btn-label">Chat</span>
            </button>

            {/* Reactions -> React */}
            <div style={{ position: "relative" }}>
              <button
                className={`ctrl-btn ${showReactions ? "active" : ""}`}
                onClick={() => setShowReactions(s => !s)}
                aria-label="React"
              >
                <div className="ctrl-btn-icon"><SmilePlus size={20} /></div>
                <span className="ctrl-btn-label">React</span>
              </button>
              {showReactions && (
                <div className="reactions-picker">
                  {["👍", "👏", "❤️", "😂", "😮", "🎉", "🙌", "🔥"].map(emoji => (
                    <button
                      key={emoji}
                      className="reaction-emoji-btn"
                      onClick={() => sendReaction(emoji)}
                      aria-label={emoji}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Share Screen -> Share */}
            <div className="ctrl-split">
              <button
                className={`ctrl-btn ${isSharing ? "active" : ""}`}
                onClick={toggleScreenShare}
                aria-label={isSharing ? "Stop Share" : "Share"}
              >
                <div className="ctrl-btn-icon">
                  <ScreenShare size={20} color="#22C55E" />
                </div>
                <span className="ctrl-btn-label">{isSharing ? "Stop Share" : "Share"}</span>
              </button>
              <button className="ctrl-caret" aria-label="Share options">
                <ChevronUp size={12} />
              </button>
            </div>

            {/* Apps */}
            <button
              className={`ctrl-btn ${activePanel === "apps" ? "active" : ""}`}
              onClick={() => togglePanel("apps")}
              aria-label="Apps"
            >
              <div className="ctrl-btn-icon"><LayoutGrid size={20} /></div>
              <span className="ctrl-btn-label">Apps</span>
            </button>

            {/* More */}
            <button className="ctrl-btn" aria-label="More">
              <div className="ctrl-btn-icon"><MoreHorizontal size={20} /></div>
              <span className="ctrl-btn-label">More</span>
            </button>
          </div>

          {/* Group 3: End */}
          <div className="control-group">
            <button className="ctrl-end-btn" onClick={() => setShowEndModal(true)}>
              <PhoneOff size={16} />
              {isHost ? "End" : "Leave"}
            </button>
          </div>
        </footer>
      </div>

      {/* ── SIDE PANEL ── */}
      {activePanel && (
        <aside className="room-panel">
          <div className="panel-header">
            <span className="panel-title">
              {activePanel === "participants" ? `Participants (${participants.length})` 
                : activePanel === "chat" ? "Meeting Chat" 
                : "Apps"}
            </span>
            <button className="panel-close" onClick={() => setActivePanel(null)} aria-label="Close panel">
              <X size={16} />
            </button>
          </div>

          {/* PARTICIPANTS */}
          {activePanel === "participants" && (
            <>
              <div className="participants-panel">
                {participants.map((p, i) => (
                  <div key={i} className="participant-item">
                    <div className="p-avt" style={{ background: avatarColor(p.display_name) }}>
                      {initials(p.display_name)}
                    </div>
                    <div className="p-info">
                      <div className="p-name">
                        {p.display_name}
                        {p.display_name === displayName && " (You)"}
                      </div>
                      <div className="p-tag">{p.is_host ? "Host" : "Participant"}</div>
                    </div>
                    <div className="p-controls">
                      {p.is_muted
                        ? <MicOff size={14} color="#FC6262" />
                        : <Mic size={14} color="#9CA3AF" />
                      }
                      {isHost && p.display_name !== displayName && (
                        <>
                          <button
                            className="p-ctrl-btn"
                            onClick={() => muteParticipant(p.display_name, p.is_muted)}
                            title={p.is_muted ? "Unmute" : "Mute"}
                          >
                            {p.is_muted ? "Unmute" : "Mute"}
                          </button>
                          <button
                            className="p-ctrl-btn danger"
                            onClick={() => removeParticipant(p.display_name)}
                            title="Remove from meeting"
                          >
                            Remove
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {isHost && (
                <div className="panel-footer">
                  <button className="panel-footer-btn outline" onClick={muteAll}>
                    <MicOff size={13} />
                    Mute All
                  </button>
                  <button className="panel-footer-btn primary">
                    <UserPlus size={13} />
                    Invite
                  </button>
                </div>
              )}
            </>
          )}

          {/* CHAT */}
          {activePanel === "chat" && (
            <>
              <div className="chat-messages">
                {chatMessages.length === 0 && (
                  <div style={{ textAlign: "center", padding: "32px 16px", color: "var(--room-text-secondary)", fontSize: 13 }}>
                    <MessageSquare size={28} strokeWidth={1} style={{ opacity: 0.4, marginBottom: 8, display: "block", margin: "0 auto 10px" }} />
                    Chat is end-to-end encrypted.
                    <br />Messages are visible to all participants.
                  </div>
                )}
                {chatMessages.map(msg => (
                  <div key={msg.id} className={`chat-msg ${msg.isSystem ? "system" : msg.isMe ? "me" : ""}`}>
                    {msg.isSystem ? (
                      <div className="chat-msg-system-text">{msg.text}</div>
                    ) : (
                      <>
                        <div className="chat-msg-header">
                          <span className="chat-msg-sender">{msg.sender}</span>
                          <span className="chat-msg-time">{msg.time}</span>
                        </div>
                        <div className={`chat-msg-bubble ${msg.isMe ? "me" : ""}`}>
                          {msg.text}
                        </div>
                      </>
                    )}
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
              <form className="chat-input-bar" onSubmit={handleSendChat}>
                <input
                  className="chat-input"
                  type="text"
                  placeholder="Send a message to everyone…"
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  maxLength={500}
                />
                <button
                  type="submit"
                  className="chat-send-btn"
                  disabled={!chatInput.trim()}
                  aria-label="Send"
                >
                  <Send size={14} />
                </button>
              </form>
            </>
          )}

          {/* APPS PANEL */}
          {activePanel === "apps" && (
            <div className="apps-panel">
              <div className="apps-tabs">
                <div className="apps-tab active">My apps</div>
                <div className="apps-tab">Discover</div>
              </div>
              <div className="apps-content">
                <div className="apps-hero">
                  <div className="apps-grid-icon"><LayoutGrid size={32} color="#0E72ED" /></div>
                  <p><a href="#" className="zoom-link">Add Apps</a> to enhance your Zoom experience</p>
                </div>
                <div className="apps-list">
                  <h3>Built by Zoom</h3>
                  <div className="app-item">
                    <div className="app-icon" style={{ background: "#0E72ED" }}>⏱️</div>
                    <div>
                      <h4>Timer</h4>
                      <p>Keep control of your workday...</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </aside>
      )}

      {/* ── JOIN AUDIO MODAL ── */}
      {showAudioModal && (
        <div className="room-modal-overlay audio-overlay">
          <div className="audio-modal-box">
            <div className="audio-modal-header">
              <div className="audio-icon-badge"><Headphones size={14} color="#fff" /></div>
              <span>Join audio</span>
              <button className="audio-close-btn" onClick={() => setShowAudioModal(false)}><X size={16} /></button>
            </div>
            <div className="audio-modal-content">
              <button 
                className="join-audio-big-btn"
                onClick={() => {
                  setAudioJoined(true);
                  setShowAudioModal(false);
                }}
              >
                Join with computer audio
              </button>
              <a href="#" className="test-audio-link">Test speaker and microphone</a>
            </div>
            <div className="audio-modal-footer">
              <label className="zoom-checkbox">
                <input type="checkbox" />
                <span>Automatically join audio by computer when joining</span>
              </label>
            </div>
          </div>
        </div>
      )}

      {/* ── END MEETING MODAL ── */}
      {showEndModal && (
        <div className="room-modal-overlay" role="dialog" aria-modal="true">
          <div className="room-modal-box">
            <div className="room-modal-title">
              {isHost ? "End Meeting" : "Leave Meeting"}
            </div>
            <div className="room-modal-desc">
              {isHost
                ? "Do you want to end this meeting for everyone, or just leave?"
                : "Are you sure you want to leave this meeting?"}
            </div>
            <div className="room-modal-actions">
              {isHost && (
                <button className="room-modal-btn danger" onClick={() => handleExit("end")}>
                  <PhoneOff size={15} />
                  End Meeting for All
                </button>
              )}
              <button
                className="room-modal-btn danger"
                style={{ background: isHost ? "transparent" : "var(--zoom-red)", border: isHost ? "1px solid var(--room-border)" : "none", color: isHost ? "var(--room-text-secondary)" : "#fff" }}
                onClick={() => handleExit("leave")}
              >
                {isHost ? "Leave Meeting" : "Leave"}
              </button>
              <button className="room-modal-btn secondary" onClick={() => setShowEndModal(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
