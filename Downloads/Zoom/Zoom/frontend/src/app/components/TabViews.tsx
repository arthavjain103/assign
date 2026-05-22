import React from "react";
import { Search, Star, Hash, Plus, MessageSquare, Video, Phone, ChevronRight, Layout, PhoneCall, History, FileText, Grid } from "lucide-react";
import Image from "next/image";

// ─── TEAM CHAT VIEW ───
export function TeamChatView() {
  return (
    <div className="tab-view-container" style={{ display: "flex", height: "100%", width: "100%" }}>
      {/* Sidebar Area */}
      <div className="tab-sidebar" style={{ width: 260, borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", background: "#f8f9fa" }}>
        <div style={{ padding: "16px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600, fontSize: 16 }}>Team Chat</span>
          <button className="btn-icon-sm"><Plus size={16}/></button>
        </div>
        <div style={{ padding: "12px", borderBottom: "1px solid var(--border)" }}>
          <div className="topbar-search" style={{ width: "100%", marginTop: 0 }}>
            <span className="topbar-search-icon"><Search size={14}/></span>
            <input className="topbar-search-input" placeholder="Jump to..." />
          </div>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
          {["Starred", "Recent", "Channels"].map(section => (
            <div key={section} style={{ padding: "0 12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-muted)", fontSize: 11, fontWeight: 600, textTransform: "uppercase", padding: "12px 4px 4px", cursor: "pointer" }}>
                <ChevronRight size={12}/> {section}
              </div>
              {section === "Recent" && (
                <>
                  <div className="chat-item active"><div className="avatar">A</div> <span className="chat-name">Aditi Arora</span></div>
                  <div className="chat-item"><div className="avatar">RS</div> <span className="chat-name">Rahul Singh</span></div>
                </>
              )}
              {section === "Channels" && (
                <>
                  <div className="chat-item"><Hash size={14} color="var(--text-muted)"/> <span className="chat-name">Engineering Team</span></div>
                  <div className="chat-item"><Hash size={14} color="var(--text-muted)"/> <span className="chat-name">Design Sync</span></div>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="tab-main" style={{ flex: 1, display: "flex", flexDirection: "column", background: "#fff" }}>
        <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <div className="avatar" style={{ width: 40, height: 40, fontSize: 16 }}>A</div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 16 }}>Aditi Arora</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Available</div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <button className="btn-icon-sm"><Video size={16}/></button>
            <button className="btn-icon-sm"><Phone size={16}/></button>
          </div>
        </div>
        <div style={{ flex: 1, padding: 24, overflowY: "auto", display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
          {/* Mock messages */}
          <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 12, margin: "24px 0" }}>Today</div>
          <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
            <div className="avatar">A</div>
            <div>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <span style={{ fontWeight: 600, fontSize: 14 }}>Aditi Arora</span> <span style={{ fontSize: 11, color: "var(--text-muted)" }}>10:42 AM</span>
              </div>
              <div style={{ background: "#f1f5f9", padding: "8px 12px", borderRadius: "0 8px 8px 8px", fontSize: 13, marginTop: 4, display: "inline-block" }}>
                Hey, is the prototype ready for the demo today?
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 12, marginBottom: 16, flexDirection: "row-reverse" }}>
            <div>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline", justifyContent: "flex-end" }}>
                <span style={{ fontSize: 11, color: "var(--text-muted)" }}>10:43 AM</span> <span style={{ fontWeight: 600, fontSize: 14 }}>You</span>
              </div>
              <div style={{ background: "var(--zoom-blue)", color: "#fff", padding: "8px 12px", borderRadius: "8px 0 8px 8px", fontSize: 13, marginTop: 4, display: "inline-block" }}>
                Yes! Just pushing the final frontend pages to the branch now.
              </div>
            </div>
          </div>
        </div>
        <div style={{ padding: 16, borderTop: "1px solid var(--border)" }}>
          <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 8, background: "#f8f9fa", display: "flex", flexDirection: "column", gap: 8 }}>
            <input type="text" placeholder="Message Aditi Arora..." style={{ border: "none", background: "transparent", outline: "none", padding: "8px", fontSize: 14 }} />
            <div style={{ display: "flex", justifyContent: "space-between", padding: "0 8px" }}>
              <div style={{ display: "flex", gap: 8 }}>
                <div style={{ width: 24, height: 24, borderRadius: 4, background: "#e2e8f0" }}></div>
                <div style={{ width: 24, height: 24, borderRadius: 4, background: "#e2e8f0" }}></div>
              </div>
              <button className="btn-primary" style={{ padding: "4px 12px", borderRadius: 4, fontSize: 12 }}>Send</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── CONTACTS VIEW ───
export function ContactsView() {
  return (
    <div className="tab-view-container" style={{ display: "flex", height: "100%", width: "100%" }}>
      <div className="tab-sidebar" style={{ width: 260, borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", background: "#f8f9fa" }}>
        <div style={{ padding: "16px", borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontWeight: 600, fontSize: 16 }}>Contacts</span>
        </div>
        <div style={{ padding: "12px", borderBottom: "1px solid var(--border)" }}>
          <div className="topbar-search" style={{ width: "100%", marginTop: 0 }}>
            <span className="topbar-search-icon"><Search size={14}/></span>
            <input className="topbar-search-input" placeholder="Search contacts" />
          </div>
        </div>
        <div style={{ flex: 1, padding: "16px" }}>
          {["Starred", "External", "Cloud Contacts", "Company Directory"].map(item => (
            <div key={item} style={{ padding: "10px 0", fontSize: 14, fontWeight: 500, cursor: "pointer", color: "var(--text)", display: "flex", alignItems: "center", gap: 8 }}>
              {item === "Starred" && <Star size={16} color="var(--zoom-blue)"/>}
              {item}
            </div>
          ))}
        </div>
      </div>
      <div className="tab-main" style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#fff" }}>
        <div className="avatar" style={{ width: 80, height: 80, fontSize: 32, marginBottom: 16 }}>D</div>
        <h2 style={{ fontSize: 24, fontWeight: 600 }}>Directory</h2>
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Select a contact to view their profile</p>
      </div>
    </div>
  );
}

// ─── WHITEBOARDS VIEW ───
export function WhiteboardsView() {
  return (
    <div className="tab-view-container" style={{ padding: 32, width: "100%", height: "100%", background: "#fff", overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <h2 style={{ fontSize: 24, fontWeight: 600 }}>Whiteboards</h2>
        <button className="btn-primary" style={{ padding: "8px 16px" }}><Plus size={14} style={{ marginRight: 6 }}/> New</button>
      </div>
      <div style={{ display: "flex", gap: 24, borderBottom: "1px solid var(--border)", marginBottom: 24 }}>
        {["Recent", "My Whiteboards", "Shared with Me", "Template"].map((tab, i) => (
          <div key={tab} style={{ padding: "0 0 12px", fontWeight: i === 0 ? 600 : 400, color: i === 0 ? "var(--zoom-blue)" : "var(--text)", borderBottom: i === 0 ? "2px solid var(--zoom-blue)" : "2px solid transparent", cursor: "pointer", fontSize: 14 }}>
            {tab}
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 24 }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden", cursor: "pointer" }}>
            <div style={{ height: 140, background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Layout size={40} color="#cbd5e1" strokeWidth={1} />
            </div>
            <div style={{ padding: 12 }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>Sprint Planning Q{i}</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Edited 2 days ago</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── APPS / CLIPS / NOTES VIEW ───
export function GenericGridContent({ title, icon: Icon, desc }: { title: string, icon: any, desc: string }) {
  return (
    <div className="tab-view-container" style={{ padding: 32, width: "100%", height: "100%", background: "#fff" }}>
      <h2 style={{ fontSize: 24, fontWeight: 600, marginBottom: 24 }}>{title}</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24, maxWidth: 800 }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ padding: 24, border: "1px solid var(--border)", borderRadius: 12, display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ width: 40, height: 40, background: "#e2e8f0", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center" }}>
               <Icon size={20} color="var(--zoom-blue)"/>
            </div>
            <div style={{ fontWeight: 600 }}>{title} Template {i}</div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
