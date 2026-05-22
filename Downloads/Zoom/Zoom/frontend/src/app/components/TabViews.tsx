import React, { useState } from "react";
import { Search, Star, Hash, Plus, MessageSquare, Video, Phone, ChevronRight, Layout, History, FileText, Grid, Lock, Check } from "lucide-react";

// ─── TEAM CHAT VIEW ───
export function TeamChatView() {
  const [activeSection, setActiveSection] = useState("Recent");
  const [message, setMessage] = useState("");
  const [feed, setFeed] = useState([
    { id: 1, sender: "Aditi Arora", text: "Hey, is the prototype ready for the demo today?", time: "10:42 AM", isMe: false },
    { id: 2, sender: "You", text: "Yes! Just pushing the final frontend pages to the branch now.", time: "10:43 AM", isMe: true }
  ]);

  const handleSend = () => {
    if (!message.trim()) return;
    setFeed([...feed, { id: Date.now(), sender: "You", text: message, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), isMe: true }]);
    setMessage("");
  };

  return (
    <div className="tab-view-container" style={{ display: "flex", height: "100%", width: "100%", background: "#fff" }}>
      {/* Sidebar Area */}
      <div className="tab-sidebar" style={{ width: 280, borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", background: "#f8f9fa" }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600, fontSize: 16 }}>Team Chat</span>
          <button className="btn-icon-sm" style={{ background: "#e2e8f0" }}><Plus size={14}/></button>
        </div>
        <div style={{ padding: "12px 16px" }}>
          <div className="topbar-search" style={{ width: "100%", marginTop: 0, background: "#e2e8f0" }}>
            <span className="topbar-search-icon"><Search size={14}/></span>
            <input className="topbar-search-input" placeholder="Jump to..." />
          </div>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
          {["Starred", "Recent", "Channels"].map(section => (
            <div key={section} style={{ padding: "0 12px" }}>
              <div 
                onClick={() => setActiveSection(section)}
                style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-muted)", fontSize: 11, fontWeight: 600, textTransform: "uppercase", padding: "12px 8px 6px", cursor: "pointer", transition: "color 0.2s" }}
              >
                <ChevronRight size={12} style={{ transform: activeSection === section ? "rotate(90deg)" : "none", transition: "transform 0.2s" }}/> {section}
              </div>
              
              {activeSection === section && section === "Recent" && (
                <>
                  <div className="chat-item active" style={{ padding: "8px", borderRadius: 6, display: "flex", alignItems: "center", gap: 10, background: "#e8effc", cursor: "pointer", margin: "2px 0" }}>
                    <div className="avatar" style={{ background: "var(--zoom-blue)", color: "#fff", width: 28, height: 28, fontSize: 12 }}>A</div> 
                    <span style={{ fontWeight: 500, fontSize: 13, color: "var(--zoom-blue)" }}>Aditi Arora</span>
                  </div>
                  <div className="chat-item" style={{ padding: "8px", borderRadius: 6, display: "flex", alignItems: "center", gap: 10, cursor: "pointer", margin: "2px 0" }}>
                    <div className="avatar" style={{ background: "#F26D21", color: "#fff", width: 28, height: 28, fontSize: 12 }}>RS</div> 
                    <span style={{ fontWeight: 500, fontSize: 13 }}>Rahul Singh</span>
                  </div>
                </>
              )}
              {activeSection === section && section === "Channels" && (
                <>
                  <div className="chat-item" style={{ padding: "8px", borderRadius: 6, display: "flex", alignItems: "center", gap: 10, cursor: "pointer", margin: "2px 0" }}>
                    <Hash size={16} color="var(--text-muted)"/> <span style={{ fontWeight: 500, fontSize: 13 }}>Engineering</span>
                  </div>
                  <div className="chat-item" style={{ padding: "8px", borderRadius: 6, display: "flex", alignItems: "center", gap: 10, cursor: "pointer", margin: "2px 0" }}>
                    <Lock size={14} color="var(--text-muted)"/> <span style={{ fontWeight: 500, fontSize: 13 }}>Private Sync</span>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="tab-main" style={{ flex: 1, display: "flex", flexDirection: "column", background: "#fff" }}>
        <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#fff" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <div className="avatar" style={{ background: "var(--zoom-blue)", color: "#fff", width: 40, height: 40, fontSize: 16 }}>A</div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 16 }}>Aditi Arora</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 8, background: "#059669", borderRadius: "50%" }}></span> Available
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <button className="btn-outline" style={{ padding: "6px 12px", border: "1px solid var(--zoom-blue)", color: "var(--zoom-blue)" }}><Video size={16} style={{marginRight: 6}}/> Meet</button>
            <button className="btn-icon-sm" style={{ background: "#f1f5f9" }}><Phone size={16}/></button>
          </div>
        </div>
        
        <div style={{ flex: 1, padding: "24px", overflowY: "auto", display: "flex", flexDirection: "column", background: "#fafafa" }}>
          <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 12, margin: "16px 0" }}>Today</div>
          
          {feed.map((msg, i) => (
            <div key={msg.id} style={{ display: "flex", gap: 12, marginBottom: 20, flexDirection: msg.isMe ? "row-reverse" : "row" }}>
              {!msg.isMe && <div className="avatar" style={{ background: "var(--zoom-blue)", color: "#fff" }}>A</div>}
              <div style={{ display: "flex", flexDirection: "column", alignItems: msg.isMe ? "flex-end" : "flex-start", maxWidth: "70%" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                  {!msg.isMe && <span style={{ fontWeight: 600, fontSize: 14 }}>{msg.sender}</span>}
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{msg.time}</span>
                </div>
                <div style={{ 
                  background: msg.isMe ? "var(--zoom-blue)" : "#fff", 
                  color: msg.isMe ? "#fff" : "var(--text)", 
                  padding: "10px 14px", 
                  borderRadius: msg.isMe ? "12px 12px 0 12px" : "0 12px 12px 12px", 
                  border: msg.isMe ? "none" : "1px solid var(--border)",
                  fontSize: 14, 
                  marginTop: 4, 
                  boxShadow: "0 1px 2px rgba(0,0,0,0.02)"
                }}>
                  {msg.text}
                </div>
              </div>
            </div>
          ))}
        </div>
        
        <div style={{ padding: 24, background: "#fff", borderTop: "1px solid var(--border)" }}>
          <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 8, background: "#fff", display: "flex", flexDirection: "column", gap: 8 }}>
            <input 
              type="text" 
              placeholder="Message Aditi Arora..." 
              value={message}
              onChange={e => setMessage(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSend()}
              style={{ border: "none", outline: "none", padding: "8px", fontSize: 14, width: "100%" }} 
            />
            <div style={{ display: "flex", justifyContent: "space-between", padding: "0 8px", alignItems: "center" }}>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn-icon-sm tooltip-btn" data-tip="Format" style={{ background: "transparent" }}><Layout size={16}/></button>
              </div>
              <button onClick={handleSend} className="btn-primary" style={{ padding: "6px 14px", borderRadius: 6, fontSize: 13, opacity: message ? 1 : 0.5 }}>Send</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── CONTACTS VIEW ───
export function ContactsView() {
  const [activeTab, setActiveTab] = useState("External");
  return (
    <div className="tab-view-container" style={{ display: "flex", height: "100%", width: "100%", background: "#fff" }}>
      <div className="tab-sidebar" style={{ width: 280, borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", background: "#f8f9fa" }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontWeight: 600, fontSize: 16 }}>Contacts</span>
        </div>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
          <div className="topbar-search" style={{ width: "100%", marginTop: 0, background: "#e2e8f0" }}>
            <span className="topbar-search-icon"><Search size={14}/></span>
            <input className="topbar-search-input" placeholder="Search contacts" />
          </div>
        </div>
        <div style={{ flex: 1, padding: "16px" }}>
          {["Starred", "External", "Cloud Contacts", "Company Directory"].map(item => (
            <div 
              key={item} 
              onClick={() => setActiveTab(item)}
              style={{ padding: "10px 12px", fontSize: 14, fontWeight: 500, cursor: "pointer", color: activeTab === item ? "var(--zoom-blue)" : "var(--text)", background: activeTab === item ? "#e8effc" : "transparent", borderRadius: 6, display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}
            >
              {item === "Starred" && <Star size={16} color="var(--zoom-blue)"/>}
              {item}
            </div>
          ))}
        </div>
      </div>
      <div className="tab-main" style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#fafafa" }}>
        <div className="avatar" style={{ background: "#7C3AED", color: "#fff", width: 80, height: 80, fontSize: 32, marginBottom: 16 }}>D</div>
        <h2 style={{ fontSize: 24, fontWeight: 600, color: "var(--text)" }}>Directory</h2>
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Select a contact from {activeTab} to view their profile and start chatting.</p>
      </div>
    </div>
  );
}

// ─── WHITEBOARDS VIEW ───
export function WhiteboardsView() {
  const [tab, setTab] = useState("Recent");
  
  return (
    <div className="tab-view-container" style={{ padding: 40, width: "100%", height: "100%", background: "#fff", overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 32 }}>
        <h2 style={{ fontSize: 28, fontWeight: 600 }}>Whiteboards</h2>
        <button className="btn-primary" style={{ padding: "8px 16px", borderRadius: 8 }}><Plus size={16} style={{ marginRight: 6 }}/> New Whiteboard</button>
      </div>
      
      <div style={{ display: "flex", gap: 32, borderBottom: "1px solid var(--border)", marginBottom: 32 }}>
        {["Recent", "My Whiteboards", "Shared with Me", "Trash"].map(t => (
          <div 
            key={t} 
            onClick={() => setTab(t)}
            style={{ padding: "0 0 12px", fontWeight: tab === t ? 600 : 400, color: tab === t ? "var(--zoom-blue)" : "var(--text)", borderBottom: tab === t ? "2px solid var(--zoom-blue)" : "2px solid transparent", cursor: "pointer", fontSize: 15, transition: "color 0.2s" }}
          >
            {t}
          </div>
        ))}
      </div>
      
      {tab === "Recent" ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 24 }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{ border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden", cursor: "pointer", transition: "box-shadow 0.2s" }} className="hover-shadow">
              <div style={{ height: 150, background: "#f8f9fa", display: "flex", alignItems: "center", justifyContent: "center", borderBottom: "1px solid var(--border)" }}>
                <Layout size={40} color="#cbd5e1" strokeWidth={1} />
              </div>
              <div style={{ padding: 16, background: "#fff" }}>
                <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>Design Sprint Q{i}</div>
                <div style={{ fontSize: 13, color: "var(--text-muted)" }}>Edited 2 days ago</div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginTop: 80 }}>
          <Layout size={48} color="#cbd5e1" strokeWidth={1} style={{ marginBottom: 16 }} />
          <h3 style={{ fontSize: 18, fontWeight: 600 }}>No active files in {tab}</h3>
        </div>
      )}
    </div>
  );
}

// ─── APPS / CLIPS / NOTES VIEW ───
export function GenericGridContent({ title, icon: Icon, desc }: { title: string, icon: any, desc: string }) {
  const [installed, setInstalled] = useState<number[]>([]);
  return (
    <div className="tab-view-container" style={{ padding: 40, width: "100%", height: "100%", background: "#fff", overflowY: "auto" }}>
      <h2 style={{ fontSize: 28, fontWeight: 600, marginBottom: 8 }}>{title}</h2>
      <p style={{ fontSize: 15, color: "var(--text-muted)", marginBottom: 32 }}>{desc}</p>
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 24 }}>
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} style={{ padding: 24, border: "1px solid var(--border)", borderRadius: 12, display: "flex", flexDirection: "column", gap: 16, background: "#fff" }} className="hover-shadow">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div style={{ width: 48, height: 48, background: "#f1f5f9", borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center" }}>
                 <Icon size={24} color="var(--zoom-blue)"/>
              </div>
              <button onClick={() => setInstalled(installed.includes(i) ? installed.filter(x => x !== i) : [...installed, i])} className={installed.includes(i) ? "btn-outline" : "btn-primary"} style={{ padding: "6px 12px", borderRadius: 6, fontSize: 13 }}>
                {installed.includes(i) ? "Open" : "Add"}
              </button>
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>{title} Add-on {i}</div>
              <div style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.4 }}>Synchronize your workspace directly through the central interface.</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

