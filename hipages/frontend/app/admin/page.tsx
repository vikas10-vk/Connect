"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard, Users, ShieldCheck, Briefcase, AlertTriangle,
  Star, LogOut, Loader2, CheckCircle2, XCircle, ChevronDown,
  Search, X, FileText, Shield, User, Home,
  Menu, ChevronRight, Building2, Clock, Mail, Zap, HelpCircle,
} from "lucide-react";
import { useAuth } from "@/src/contexts/AuthContext";
import api from "@/src/lib/api";

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg: "#FFF8E7", card: "#FFFFFF", panel: "#071D36",
  line: "#E8D9B0", ink: "#071D36", ink2: "#173452", ink3: "#56677A", ink4: "#8A9BB0",
  primary: "#071D36", primaryL: "rgba(212,170,58,0.12)",
  green: "#10B981", greenL: "#ECFDF5",
  amber: "#F59E0B", amberL: "#FFFBEB",
  red: "#EF4444", redL: "#FEF2F2",
  blue: "#5BB3FF", blueL: "rgba(91,179,255,0.10)",
  gold: "#D4AA3A", navText: "rgba(255,255,255,0.80)",
};
const UI = "'Inter','DM Sans',-apple-system,system-ui,sans-serif";
const SHADOW = "0 1px 3px rgba(15,25,35,0.07),0 1px 2px rgba(15,25,35,0.04)";
const SHADOW_MD = "0 4px 16px rgba(15,25,35,0.10),0 1px 4px rgba(15,25,35,0.05)";

// ─── Types ────────────────────────────────────────────────────────────────────
type Tab = "overview" | "tradies" | "homeowners" | "verification" | "jobs" | "completed" | "disputes" | "reviews" | "uncategorised";

interface Stats {
  total_tradies: number; total_homeowners: number; total_jobs: number;
  completed_jobs: number; open_disputes: number; pending_verifications: number;
}
interface VerificationItem {
  id: string; type: "licence" | "insurance" | "profile" | "change_request";
  tradie_id?: string; business_name?: string; tradie_email?: string; full_name?: string;
  phone?: string;
  category_name?: string; licence_number?: string; issuing_state?: string;
  issuing_body?: string; holder_name?: string; photo_url?: string; document_url?: string;
  insurance_type?: string; insurer_name?: string; policy_number?: string;
  coverage_amount_cents?: number; expires_at?: string;
  status: string; rejection_reason?: string; rejection_note?: string;
  edit_request_note?: string; created_at: string;
  suburb?: string; state?: string; abn?: string; verification_status?: string;
  request_type?: string; payload?: any; note?: string; admin_note?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const timeAgo = (d: string) => {
  const s = Math.floor((Date.now() - new Date(d).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};
const fmtCoverage = (cents: number) =>
  `$${(cents / 100).toLocaleString("en-AU", { maximumFractionDigits: 0 })}`;

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    pending:    { bg: C.amberL, color: C.amber, label: "Pending" },
    in_review:  { bg: C.blueL,  color: C.blue,  label: "In Review" },
    verified:   { bg: C.greenL, color: C.green,  label: "Verified" },
    rejected:   { bg: C.redL,   color: C.red,    label: "Rejected" },
    expired:    { bg: C.panel,  color: C.ink4,   label: "Expired" },
    active:     { bg: C.greenL, color: C.green,  label: "Active" },
    disputed:   { bg: C.redL,   color: C.red,    label: "Disputed" },
    completed:  { bg: C.greenL, color: C.green,  label: "Completed" },
    confirmed:  { bg: C.greenL, color: C.green,  label: "Completed" },
    in_progress:{ bg: C.blueL,  color: C.blue,   label: "In Progress" },
    hired:      { bg: C.blueL,  color: C.blue,   label: "Hired" },
    open:       { bg: C.amberL, color: C.amber,  label: "Open" },
    closed:     { bg: C.greenL, color: C.green,  label: "Completed" },
    cancelled:  { bg: C.panel,  color: C.ink4,   label: "Cancelled" },
    suspended:  { bg: C.redL,   color: C.red,    label: "Suspended" },
  };
  const s = map[status] || { bg: C.panel, color: C.ink4, label: status };
  return (
    <span style={{ fontSize: 10.5, fontWeight: 700, padding: "3px 9px", borderRadius: 20,
      background: s.bg, color: s.color, whiteSpace: "nowrap", fontFamily: UI,
      textTransform: "uppercase", letterSpacing: "0.06em" }}>
      {s.label}
    </span>
  );
}

function RejectModal({ onReject, onClose }: { onReject: (reason: string, note: string) => void; onClose: () => void }) {
  const [reason, setReason] = useState("other");
  const [note, setNote] = useState("");
  const reasons = ["invalid_number", "expired", "name_mismatch", "wrong_category", "insufficient_cover", "cannot_verify", "other"];
  return (
    <div onClick={e => e.target === e.currentTarget && onClose()}
      style={{ position: "fixed", inset: 0, zIndex: 9999, background: "rgba(10,15,25,0.55)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ background: C.card, borderRadius: 16, padding: 24, width: "100%", maxWidth: 400, boxShadow: SHADOW_MD }}>
        <p style={{ fontSize: 15, fontWeight: 700, color: C.ink, margin: "0 0 16px" }}>Reject — reason</p>
        <select value={reason} onChange={e => setReason(e.target.value)}
          style={{ width: "100%", padding: "10px 12px", borderRadius: 9, border: `1px solid ${C.line}`,
            fontSize: 13, color: C.ink, background: C.bg, marginBottom: 12, fontFamily: UI }}>
          {reasons.map(r => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
        </select>
        <textarea value={note} onChange={e => setNote(e.target.value)} rows={3} placeholder="Optional note to tradie…"
          style={{ width: "100%", padding: "10px 12px", borderRadius: 9, border: `1px solid ${C.line}`,
            fontSize: 13, color: C.ink, background: C.bg, resize: "vertical", fontFamily: UI, boxSizing: "border-box" }} />
        <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
          <button onClick={onClose}
            style={{ flex: 1, padding: "11px", borderRadius: 9, border: `1px solid ${C.line}`, background: C.bg,
              color: C.ink3, fontWeight: 600, fontSize: 13, cursor: "pointer", fontFamily: UI }}>Cancel</button>
          <button onClick={() => onReject(reason, note)}
            style={{ flex: 2, padding: "11px", borderRadius: 9, border: "none", background: C.red,
              color: "#fff", fontWeight: 700, fontSize: 13, cursor: "pointer", fontFamily: UI }}>Confirm reject</button>
        </div>
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function AdminPanel() {
  const { user } = useAuth();
  const router   = useRouter();
  const [tab, setTab]           = useState<Tab>("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget]   = useState<{ id: string; docType: "cert" | "insurance" } | null>(null);
  const [resolveTarget, setResolveTarget] = useState<{ id: string; resolution: string; title: string } | null>(null);
  const [resolveNote, setResolveNote] = useState<string>("");
  const [resolveRefund, setResolveRefund] = useState<string>("");
  const [resolveBusy, setResolveBusy] = useState(false);


  // Data
  const [overview, setOverview]       = useState<any>(null);
  const [tradies, setTradies]         = useState<any[]>([]);
  const [tradiesTotal, setTradiesTotal] = useState(0);
  const [tradieSearch, setTradieSearch] = useState("");
  const [tradieFilter, setTradieFilter] = useState("");
  const [homeowners, setHomeowners]   = useState<any[]>([]);
  const [hwTotal, setHwTotal]         = useState(0);
  const [hwSearch, setHwSearch]       = useState("");
  const [verification, setVerification] = useState<{ certifications: VerificationItem[]; insurance: VerificationItem[]; profiles: VerificationItem[]; change_requests?: VerificationItem[] } | null>(null);
  const [jobs, setJobs]               = useState<any[]>([]);
  const [jobsTotal, setJobsTotal]     = useState(0);
  const [jobSearch, setJobSearch]     = useState("");
  const [jobStatusFilter, setJobStatusFilter] = useState("");
  const [disputes, setDisputes]       = useState<any[]>([]);
  const [reviews, setReviews]         = useState<any[]>([]);
  const [reviewsTotal, setReviewsTotal] = useState(0);
  const [completedJobs, setCompletedJobs]   = useState<any[]>([]);
  const [completedTotal, setCompletedTotal] = useState(0);
  const [completedSearch, setCompletedSearch] = useState("");
  const [completedStatusFilter, setCompletedStatusFilter] = useState("");
  const [expandedCompletedId, setExpandedCompletedId] = React.useState<string | null>(null);
  // Uncategorised triage state -- requests homeowners posted via "Service not
  // listed?" that need an admin to classify into a real trade or close out.
  const [uncatItems, setUncatItems] = useState<any[]>([]);
  const [uncatTotal, setUncatTotal] = useState(0);
  const [uncatClassifyId, setUncatClassifyId] = useState<string | null>(null);
  const [uncatClassifySlug, setUncatClassifySlug] = useState<string>("");
  const [uncatCloseId, setUncatCloseId] = useState<string | null>(null);
  const [uncatCloseNote, setUncatCloseNote] = useState<string>("");

  // Auth guard
  useEffect(() => {
    if (user && user.role !== "admin") router.replace("/");
  }, [user, router]);

  const load = useCallback(async (t: Tab) => {
    setLoading(true); setError("");
    try {
      if (t === "overview") {
        const { data } = await api.get("/admin/overview");
        setOverview(data);
      } else if (t === "tradies") {
        const params = new URLSearchParams({ page: "1", limit: "50" });
        if (tradieSearch) params.set("search", tradieSearch);
        if (tradieFilter) params.set("verification_status", tradieFilter);
        const { data } = await api.get(`/admin/tradies?${params}`);
        setTradies(data.items); setTradiesTotal(data.total);
      } else if (t === "homeowners") {
        const params = new URLSearchParams({ page: "1", limit: "50" });
        if (hwSearch) params.set("search", hwSearch);
        const { data } = await api.get(`/admin/homeowners?${params}`);
        setHomeowners(data.items); setHwTotal(data.total);
      } else if (t === "verification") {
        const { data } = await api.get("/admin/verification/pending");
        setVerification(data);
      } else if (t === "jobs") {
        const params = new URLSearchParams({ page: "1", limit: "50" });
        if (jobSearch) params.set("search", jobSearch);
        if (jobStatusFilter) params.set("status", jobStatusFilter);
        const { data } = await api.get(`/admin/jobs?${params}`);
        setJobs(data.items); setJobsTotal(data.total);
      } else if (t === "disputes") {
        const { data } = await api.get("/admin/disputes");
        setDisputes(data.items);
      } else if (t === "reviews") {
        const { data } = await api.get("/admin/reviews?page=1&limit=50");
        setReviews(data.items); setReviewsTotal(data.total);
      } else if (t === "uncategorised") {
        const { data } = await api.get('/admin/uncategorised?page=1&limit=50');
        setUncatItems(data.items); setUncatTotal(data.total);
      } else if (t === "completed") {
        const params = new URLSearchParams({ page: "1", limit: "50" });
        if (completedSearch) params.set("search", completedSearch);
        if (completedStatusFilter) params.set("status", completedStatusFilter);
        const { data } = await api.get(`/admin/completed-jobs?${params}`);
        setCompletedJobs(data.items); setCompletedTotal(data.total);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to load data.");
    } finally { setLoading(false); }
  }, [tradieSearch, tradieFilter, hwSearch, jobSearch, jobStatusFilter, completedSearch, completedStatusFilter]);

  useEffect(() => { load(tab); }, [tab]);

  // Real-time refresh: when the backend broadcasts a job:status_changed
  // event (e.g. a homeowner raises a dispute, a tradie marks complete),
  // re-pull the current tab so the admin view never goes stale. Without
  // this, an admin who opened the Completed tab before the dispute would
  // continue to see the disputed job listed as completed until they
  // manually reloaded the page.
  useEffect(() => {
    if (!user) return;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;
    const connect = async () => {
      try {
        const { default: apiClient } = await import("@/src/lib/api");
        let ticket: string | undefined;
        try {
          ticket = (await apiClient.post("/auth/ws-ticket")).data?.ticket;
        } catch { return; }
        if (!ticket) return;
        const apiBase = process.env.NEXT_PUBLIC_API_URL || window.location.origin;
        const wsBase = apiBase.replace(/^http/, "ws");
        ws = new WebSocket(`${wsBase}/ws?ticket=${encodeURIComponent(ticket)}`);
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg?.type === "job:status_changed") {
              load(tab).catch(() => {});
            }
          } catch { /* ignore heartbeats */ }
        };
        ws.onclose = () => {
          if (closed) return;
          reconnectTimer = setTimeout(connect, 5000);
        };
        ws.onerror = () => { try { ws?.close(); } catch { /* noop */ } };
      } catch { /* dashboard still works without real-time */ }
    };
    connect();
    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      try { ws?.close(); } catch { /* noop */ }
    };
  }, [user, tab, load]);

  const switchTab = (t: Tab) => { setTab(t); setSidebarOpen(false); };

  // Actions
  const approveCert = async (id: string) => {
    setActionLoading(id);
    try { await api.post(`/admin/verification/certifications/${id}/approve`); await load("verification"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const rejectCert = async (id: string, reason: string, note: string) => {
    setActionLoading(id);
    try { await api.post(`/admin/verification/certifications/${id}/reject`, { reason, note }); setRejectTarget(null); await load("verification"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const approveInsurance = async (id: string) => {
    setActionLoading(id);
    try { await api.post(`/admin/verification/insurance/${id}/approve`); await load("verification"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const rejectInsurance = async (id: string, reason: string, note: string) => {
    setActionLoading(id);
    try { await api.post(`/admin/verification/insurance/${id}/reject`, { reason, note }); setRejectTarget(null); await load("verification"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const approveProfile = async (id: string) => {
    setActionLoading(id);
    try { await api.patch(`/admin/tradies/${id}/verification`, { verification_status: "verified" }); await load("verification"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const setTradieVerification = async (id: string, status: string) => {
    setActionLoading(id);
    try { await api.patch(`/admin/tradies/${id}/verification`, { verification_status: status }); await load("tradies"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const approveChangeRequest = async (id: string) => {
    setActionLoading(id);
    try { await api.post(`/admin/change-requests/${id}/approve`, { admin_note: "Approved by admin." }); await load("verification"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const rejectChangeRequest = async (id: string) => {
    const admin_note = prompt("Reason shown in admin records / optional message to tradie:") || "";
    setActionLoading(id);
    try { await api.post(`/admin/change-requests/${id}/reject`, { admin_note }); await load("verification"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const suspendTradie = async (id: string) => {
    const reason = prompt("Suspension reason. Be specific; this is emailed to the tradie and disables access:");
    if (!reason) return;
    const confirmation = prompt("Type SUSPEND TRADIE to confirm:");
    if (confirmation !== "SUSPEND TRADIE") return;
    setActionLoading(id);
    try { await api.post(`/admin/tradies/${id}/suspend`, { reason, confirmation }); await load("tradies"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const redistributeLeads = async (tradieId: string, businessName: string) => {
    setActionLoading(`redist-${tradieId}`);
    try {
      await api.post(`/admin/tradies/${tradieId}/redistribute-leads`);
      alert(`Lead redistribution triggered for ${businessName}. Matching open jobs will be distributed shortly.`);
    }
    catch (e: any) { alert(e?.response?.data?.detail || "Redistribution failed."); }
    finally { setActionLoading(null); }
  };

  const seedCleaningCategories = async () => {
    setActionLoading("seed-cleaning");
    try {
      const res = await api.post("/admin/categories/seed-cleaning");
      const { added, skipped } = res.data;
      const msg = [
        added.length   ? `Added: ${added.join(", ")}` : null,
        skipped.length ? `Already existed: ${skipped.join(", ")}` : null,
      ].filter(Boolean).join("\n");
      alert(`Category seed complete.\n\n${msg}`);
    }
    catch (e: any) { alert(e?.response?.data?.detail || "Seed failed."); }
    finally { setActionLoading(null); }
  };

  const deleteReview = async (id: string) => {
    if (!confirm("Permanently delete this review?")) return;
    setActionLoading(id);
    try { await api.delete(`/admin/reviews/${id}`); await load("reviews"); }
    catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };
  const messageReviewer = async (id: string) => {
    const message = prompt("Message to send to the homeowner who posted this review:");
    if (!message) return;
    setActionLoading(id);
    try {
      await api.post(`/admin/reviews/${id}/message`, {
        subject: "Thanks for your ProConnect review",
        message,
      });
      alert("Message sent.");
    } catch (e: any) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setActionLoading(null); }
  };

  // Nav items
  // Count unique tradies with pending items (not individual document count)
  const pendingTradieCount = React.useMemo(() => {
    if (!verification) return overview?.stats?.pending_verifications || 0;
    const ids = new Set<string>();
    (verification.profiles || []).forEach(p => ids.add(p.id));
    (verification.certifications || []).forEach(c => { if (c.tradie_id) ids.add(c.tradie_id); });
    (verification.insurance || []).forEach(p => { if (p.tradie_id) ids.add(p.tradie_id); });
    (verification.change_requests || []).forEach(r => { if (r.tradie_id) ids.add(r.tradie_id); });
    return ids.size || 0;
  }, [verification, overview]);

  const navItems: { key: Tab; label: string; icon: React.ElementType; badge?: number }[] = [
    { key: "overview",     label: "Overview",     icon: LayoutDashboard },
    { key: "tradies",      label: "Tradies",      icon: Building2 },
    { key: "homeowners",   label: "Homeowners",   icon: Home },
    { key: "verification", label: "Verification", icon: ShieldCheck,
      badge: pendingTradieCount || undefined },
    { key: "jobs",         label: "Jobs",         icon: Briefcase },
    { key: "completed",    label: "Completed",    icon: CheckCircle2, badge: overview?.stats?.completed_jobs || undefined },
    { key: "disputes",     label: "Disputes",     icon: AlertTriangle, badge: overview?.stats?.open_disputes },
    { key: "uncategorised",label: "Uncategorised",icon: HelpCircle,    badge: uncatTotal || undefined },
    { key: "reviews",      label: "Reviews",      icon: Star },
  ];

  const panelS: React.CSSProperties = { background: C.card, border: `1px solid ${C.line}`, borderRadius: 12, boxShadow: SHADOW, overflow: "hidden" };
  const thS: React.CSSProperties = { padding: "10px 14px", fontSize: 10, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.1em", textAlign: "left", background: C.bg, borderBottom: `1px solid ${C.line}` };
  const tdS: React.CSSProperties = { padding: "11px 14px", fontSize: 12.5, color: C.ink2, borderBottom: `1px solid ${C.line}` };
  const btnS = (bg: string, color: string): React.CSSProperties => ({
    padding: "5px 12px", borderRadius: 7, border: "none", background: bg, color,
    fontSize: 11.5, fontWeight: 700, cursor: "pointer", display: "inline-flex",
    alignItems: "center", gap: 4, fontFamily: UI, whiteSpace: "nowrap",
  });

  // ── Render tabs ──────────────────────────────────────────────────────────────

  const renderOverview = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Stat grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(150px,1fr))", gap: 12 }}>
        {[
          { label: "Tradies",        value: overview?.stats?.total_tradies, color: C.ink },
          { label: "Homeowners",     value: overview?.stats?.total_homeowners, color: C.ink },
          { label: "Total jobs",     value: overview?.stats?.total_jobs, color: C.ink },
          { label: "Completed jobs", value: overview?.stats?.completed_jobs, color: C.green },
          { label: "Open disputes",  value: overview?.stats?.open_disputes, color: C.red },
          { label: "Pending verifs", value: overview?.stats?.pending_verifications, color: C.amber },
        ].map((s, i) => (
          <div key={i} style={{ ...panelS, padding: "16px 18px" }}>
            <p style={{ fontSize: 10, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.1em", margin: "0 0 8px" }}>{s.label}</p>
            <p style={{ fontSize: 30, fontWeight: 800, color: s.color, margin: 0, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{s.value ?? "—"}</p>
          </div>
        ))}
      </div>
      {/* Two-col panels */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(300px,1fr))", gap: 16 }}>
        {/* Recent tradies */}
        <div style={panelS}>
          <div style={{ padding: "12px 16px", borderBottom: `1px solid ${C.line}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: C.ink, margin: 0 }}>Recent tradies</p>
            <button onClick={() => switchTab("tradies")} style={{ fontSize: 11, color: C.blue, background: "none", border: "none", cursor: "pointer", fontWeight: 600, fontFamily: UI }}>See all →</button>
          </div>
          {(overview?.recent_tradies || []).map((t: any) => (
            <div key={t.id} style={{ padding: "10px 16px", borderBottom: `1px solid ${C.line}`, display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 32, height: 32, borderRadius: 9, background: C.blueL, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, color: C.blue, flexShrink: 0 }}>
                {(t.business_name || t.full_name || "?")[0]}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 12.5, fontWeight: 600, color: C.ink, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.business_name || t.full_name}</p>
                <p style={{ fontSize: 11, color: C.ink4, margin: 0 }}>{t.suburb}, {t.state}</p>
              </div>
              <StatusPill status={t.verification_status || "pending"} />
            </div>
          ))}
        </div>
        {/* Recent jobs */}
        <div style={panelS}>
          <div style={{ padding: "12px 16px", borderBottom: `1px solid ${C.line}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: C.ink, margin: 0 }}>Recent jobs</p>
            <button onClick={() => switchTab("jobs")} style={{ fontSize: 11, color: C.blue, background: "none", border: "none", cursor: "pointer", fontWeight: 600, fontFamily: UI }}>See all →</button>
          </div>
          {(overview?.recent_jobs || []).map((j: any) => (
            <div key={j.id} style={{ padding: "10px 16px", borderBottom: `1px solid ${C.line}`, display: "flex", alignItems: "center", gap: 10 }}>
              <Briefcase size={14} color={C.ink4} style={{ flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 12.5, fontWeight: 600, color: C.ink, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{j.title || "Untitled"}</p>
                <p style={{ fontSize: 11, color: C.ink4, margin: 0 }}>{j.suburb}, {j.state} · {timeAgo(j.created_at)}</p>
              </div>
              <StatusPill status={j.status} />
            </div>
          ))}
        </div>
        {/* Disputes */}
        {(overview?.recent_disputes?.length > 0) && (
          <div style={panelS}>
            <div style={{ padding: "12px 16px", borderBottom: `1px solid ${C.line}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <p style={{ fontSize: 13, fontWeight: 700, color: C.red, margin: 0 }}>⚠️ Open disputes</p>
              <button onClick={() => switchTab("disputes")} style={{ fontSize: 11, color: C.blue, background: "none", border: "none", cursor: "pointer", fontWeight: 600, fontFamily: UI }}>See all →</button>
            </div>
            {(overview?.recent_disputes || []).map((d: any) => (
              <div key={d.id} style={{ padding: "10px 16px", borderBottom: `1px solid ${C.line}`, display: "flex", alignItems: "center", gap: 10 }}>
                <AlertTriangle size={14} color={C.red} style={{ flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 12.5, fontWeight: 600, color: C.ink, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.title || "Untitled"}</p>
                  <p style={{ fontSize: 11, color: C.ink4, margin: 0 }}>{d.suburb}, {d.state} · {timeAgo(d.updated_at)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {/* Platform Tools */}
      <div style={{ ...panelS, gridColumn: "1 / -1" }}>
        <div style={{ padding: "12px 16px", borderBottom: `1px solid ${C.line}` }}>
          <p style={{ fontSize: 13, fontWeight: 700, color: C.ink, margin: 0 }}>Platform Tools</p>
        </div>
        <div style={{ padding: "14px 16px", display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <p style={{ fontSize: 12.5, fontWeight: 600, color: C.ink, margin: "0 0 2px" }}>Seed Cleaning Categories</p>
            <p style={{ fontSize: 11.5, color: C.ink4, margin: 0 }}>Add Pool Cleaning and other missing cleaning subcategories to the database (safe to run multiple times)</p>
          </div>
          <button onClick={seedCleaningCategories} disabled={actionLoading === "seed-cleaning"}
            style={btnS(C.amberL, C.amber)}>
            {actionLoading === "seed-cleaning" ? <Loader2 size={11} className="animate-spin" /> : <Zap size={11} />}
            {" "}Seed Pool Cleaning
          </button>
        </div>
      </div>
    </div>
  );

  const renderTradies = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <div style={{ position: "relative", flex: "1 1 200px" }}>
          <Search size={13} style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: C.ink4 }} />
          <input value={tradieSearch} onChange={e => setTradieSearch(e.target.value)}
            onKeyDown={e => e.key === "Enter" && load("tradies")}
            placeholder="Search name, email…"
            style={{ width: "100%", padding: "9px 10px 9px 32px", borderRadius: 9, border: `1px solid ${C.line}`, fontSize: 13, color: C.ink, fontFamily: UI, boxSizing: "border-box", background: C.card }} />
        </div>
        <select value={tradieFilter} onChange={e => { setTradieFilter(e.target.value); }}
          style={{ padding: "9px 12px", borderRadius: 9, border: `1px solid ${C.line}`, fontSize: 13, color: C.ink, fontFamily: UI, background: C.card, minWidth: 150 }}>
          <option value="">All statuses</option>
          {["pending","in_review","verified","rejected","suspended"].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button onClick={() => load("tradies")} style={btnS(C.primary, "#fff")}><Search size={13} /> Search</button>
      </div>
      <p style={{ fontSize: 12, color: C.ink4, margin: 0 }}>{tradiesTotal} tradies</p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", background: C.card, borderRadius: 12, overflow: "hidden", boxShadow: SHADOW }}>
          <thead>
            <tr>
              {["Business", "Email", "Location", "ABN", "Status", "Joined", "Action"].map(h => <th key={h} style={thS}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {tradies.length === 0 && !loading && (
              <tr><td colSpan={7} style={{ ...tdS, textAlign: "center", color: C.ink4, padding: 32 }}>No tradies found</td></tr>
            )}
            {tradies.map(t => (
              <tr key={t.id}>
                <td style={{ ...tdS, fontWeight: 600 }}>{t.business_name || "—"}</td>
                <td style={tdS}>{t.email}</td>
                <td style={tdS}>{t.suburb || "—"}, {t.state || "—"}</td>
                <td style={{ ...tdS, fontVariantNumeric: "tabular-nums", fontSize: 11.5 }}>{t.abn || "—"}</td>
                <td style={tdS}><StatusPill status={t.verification_status || "pending"} /></td>
                <td style={{ ...tdS, fontSize: 11.5, color: C.ink4 }}>{t.created_at ? timeAgo(t.created_at) : "—"}</td>
                <td style={tdS}>
                  <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                    {t.verification_status !== "verified" && (
                      <button onClick={() => setTradieVerification(t.id, "verified")} disabled={actionLoading === t.id}
                        style={btnS(C.greenL, C.green)}>
                        {actionLoading === t.id ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />} Approve
                      </button>
                    )}
                    {t.verification_status !== "rejected" && (
                      <button onClick={() => setTradieVerification(t.id, "rejected")} disabled={actionLoading === t.id}
                        style={btnS(C.redL, C.red)}>
                        <XCircle size={11} /> Reject
                      </button>
                    )}
                    {t.verification_status !== "suspended" && (
                      <button onClick={() => suspendTradie(t.id)} disabled={actionLoading === t.id}
                        style={btnS(C.panel, C.ink4)}>
                        Suspend
                      </button>
                    )}
                    {t.verification_status === "verified" && (
                      <button
                        onClick={() => redistributeLeads(t.id, t.business_name || t.full_name || t.id)}
                        disabled={actionLoading === `redist-${t.id}`}
                        style={btnS(C.amberL, C.amber)}
                        title="Push any waiting open jobs to this tradie's lead queue"
                      >
                        {actionLoading === `redist-${t.id}`
                          ? <Loader2 size={11} className="animate-spin" />
                          : <Zap size={11} />
                        } Leads
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderHomeowners = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <div style={{ position: "relative", flex: "1 1 200px" }}>
          <Search size={13} style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: C.ink4 }} />
          <input value={hwSearch} onChange={e => setHwSearch(e.target.value)}
            onKeyDown={e => e.key === "Enter" && load("homeowners")}
            placeholder="Search name, email…"
            style={{ width: "100%", padding: "9px 10px 9px 32px", borderRadius: 9, border: `1px solid ${C.line}`, fontSize: 13, color: C.ink, fontFamily: UI, boxSizing: "border-box", background: C.card }} />
        </div>
        <button onClick={() => load("homeowners")} style={btnS(C.primary, "#fff")}><Search size={13} /> Search</button>
      </div>
      <p style={{ fontSize: 12, color: C.ink4, margin: 0 }}>{hwTotal} homeowners</p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", background: C.card, borderRadius: 12, overflow: "hidden", boxShadow: SHADOW }}>
          <thead>
            <tr>{["Name", "Email", "Phone", "Verified", "Active", "Joined"].map(h => <th key={h} style={thS}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {homeowners.length === 0 && !loading && (
              <tr><td colSpan={6} style={{ ...tdS, textAlign: "center", color: C.ink4, padding: 32 }}>No homeowners found</td></tr>
            )}
            {homeowners.map(h => (
              <tr key={h.id}>
                <td style={{ ...tdS, fontWeight: 600 }}>{h.full_name}</td>
                <td style={tdS}>{h.email}</td>
                <td style={tdS}>{h.phone || "—"}</td>
                <td style={tdS}><StatusPill status={h.email_verified ? "verified" : "pending"} /></td>
                <td style={tdS}><StatusPill status={h.is_active ? "active" : "suspended"} /></td>
                <td style={{ ...tdS, fontSize: 11.5, color: C.ink4 }}>{h.created_at ? timeAgo(h.created_at) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderVerification = () => {
    const total = (verification?.certifications.length || 0) + (verification?.insurance.length || 0) + (verification?.profiles.length || 0) + (verification?.change_requests?.length || 0);

    // ── Group all pending items by tradie profile id ──────────────────────────
    // This ensures a tradie's profile approval, licences, and insurance all
    // appear together in one card rather than in separate sections.
    type TradieGroup = {
      tradie_id: string;
      business_name: string;
      tradie_email: string;
      full_name: string;
      phone?: string;
      suburb?: string;
      state?: string;
      abn?: string;
      profiles: VerificationItem[];
      certifications: VerificationItem[];
      insurance: VerificationItem[];
      change_requests: VerificationItem[];
    };

    const grouped: Record<string, TradieGroup> = {};

    const ensureGroup = (tradieId: string, item: VerificationItem): TradieGroup => {
      if (!grouped[tradieId]) {
        grouped[tradieId] = {
          tradie_id: tradieId,
          business_name: item.business_name || item.full_name || "Unknown Tradie",
          tradie_email: item.tradie_email || "",
          full_name: item.full_name || "",
          phone: item.phone,
          suburb: (item as any).suburb,
          state: (item as any).state,
          abn: (item as any).abn,
          profiles: [], certifications: [], insurance: [], change_requests: [],
        };
      }
      // Merge phone if we get it from any item (e.g. cert/insurance item carries it)
      if (item.phone && !grouped[tradieId].phone) {
        grouped[tradieId].phone = item.phone;
      }
      return grouped[tradieId];
    };

    // Profiles: their own `id` IS the tradie_profile id
    (verification?.profiles || []).forEach(p => {
      ensureGroup(p.id, p).profiles.push(p);
    });
    // Certs, insurance, change_requests all carry tradie_id
    (verification?.certifications || []).forEach(c => {
      if (c.tradie_id) ensureGroup(c.tradie_id, c).certifications.push(c);
    });
    (verification?.insurance || []).forEach(p => {
      if (p.tradie_id) ensureGroup(p.tradie_id, p).insurance.push(p);
    });
    (verification?.change_requests || []).forEach(r => {
      if (r.tradie_id) ensureGroup(r.tradie_id, r).change_requests.push(r);
    });

    const tradieGroups = Object.values(grouped);

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <p style={{ fontSize: 13, color: C.ink4, margin: 0 }}>
            {total} item{total !== 1 ? "s" : ""} pending review across {tradieGroups.length} tradie{tradieGroups.length !== 1 ? "s" : ""}
          </p>
          <button onClick={() => load("verification")} style={btnS(C.panel, C.ink3)}>Refresh</button>
        </div>

        {/* One card per tradie — all their pending docs together */}
        {tradieGroups.map(group => (
          <div key={group.tradie_id} style={{ ...panelS, overflow: "visible" }}>

            {/* ── Tradie header ── */}
            <div style={{ padding: "14px 18px", borderBottom: `1px solid ${C.line}`, display: "flex", alignItems: "center", gap: 12, background: C.bg, flexWrap: "wrap" }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: C.amberL, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <User size={20} color={C.amber} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 14, fontWeight: 700, color: C.ink, margin: "0 0 3px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {group.business_name}
                </p>
                <p style={{ fontSize: 11.5, color: C.ink4, margin: "0 0 1px" }}>
                  {group.tradie_email}
                  {group.phone ? ` · 📞 ${group.phone}` : ""}
                </p>
                <p style={{ fontSize: 11.5, color: C.ink4, margin: 0 }}>
                  {[group.suburb && group.state ? `${group.suburb}, ${group.state}` : null, group.abn ? `ABN: ${group.abn}` : null].filter(Boolean).join(" · ")}
                </p>
              </div>
              {/* Summary pills — all amber (pending), never green (green = verified in this app) */}
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {group.profiles.length > 0 && (
                  <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 9px", borderRadius: 20, background: C.amberL, color: C.amber, border: `1px solid ${C.amber}30` }}>
                    Profile
                  </span>
                )}
                {group.certifications.length > 0 && (
                  <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 9px", borderRadius: 20, background: C.amberL, color: C.amber, border: `1px solid ${C.amber}30` }}>
                    {group.certifications.length} Licence{group.certifications.length > 1 ? "s" : ""}
                  </span>
                )}
                {group.insurance.length > 0 && (
                  <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 9px", borderRadius: 20, background: C.amberL, color: C.amber, border: `1px solid ${C.amber}30` }}>
                    {group.insurance.length} Insurance
                  </span>
                )}
                {group.change_requests.length > 0 && (
                  <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 9px", borderRadius: 20, background: C.amberL, color: C.amber, border: `1px solid ${C.amber}30` }}>
                    {group.change_requests.length} Change{group.change_requests.length > 1 ? "s" : ""}
                  </span>
                )}
              </div>
            </div>

            {/* ── Profile approval row ── */}
            {group.profiles.map(p => (
              <div key={p.id} style={{ padding: "13px 18px", borderBottom: `1px solid ${C.line}`, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: C.amberL, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <ShieldCheck size={15} color={C.amber} />
                </div>
                <div style={{ flex: 1, minWidth: 160 }}>
                  <p style={{ fontSize: 12.5, fontWeight: 700, color: C.ink, margin: "0 0 1px" }}>Profile approval</p>
                  <p style={{ fontSize: 11.5, color: C.ink4, margin: 0 }}>Submitted {timeAgo(p.created_at)}</p>
                </div>
                <div style={{ display: "flex", gap: 7, flexShrink: 0, flexWrap: "wrap" }}>
                  <button onClick={() => approveProfile(p.id!)} disabled={actionLoading === p.id}
                    style={btnS(C.greenL, C.green)}>
                    {actionLoading === p.id ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />} Approve
                  </button>
                  <button onClick={() => setTradieVerification(p.id!, "rejected")} disabled={actionLoading === p.id}
                    style={btnS(C.redL, C.red)}><XCircle size={11} /> Reject</button>
                </div>
              </div>
            ))}

            {/* ── Certification rows ── */}
            {group.certifications.map(c => (
              <div key={c.id} style={{ padding: "13px 18px", borderBottom: `1px solid ${C.line}` }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 14, flexWrap: "wrap" }}>
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: C.amberL, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1 }}>
                    <FileText size={15} color={C.amber} />
                  </div>
                  <div style={{ flex: 1, minWidth: 160 }}>
                    <p style={{ fontSize: 12.5, fontWeight: 700, color: C.ink, margin: "0 0 2px" }}>
                      Licence — {c.category_name || "Unknown category"}
                    </p>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "2px 12px" }}>
                      {[
                        c.licence_number && `#${c.licence_number}`,
                        c.issuing_state && `${c.issuing_state}`,
                        c.holder_name && `Holder: ${c.holder_name}`,
                        c.expires_at && `Expires: ${c.expires_at}`,
                      ].filter(Boolean).map((item, i) => (
                        <span key={i} style={{ fontSize: 11.5, color: C.ink3 }}>{item}</span>
                      ))}
                    </div>
                    {c.edit_request_note && (
                      <div style={{ marginTop: 7, padding: "6px 10px", background: C.amberL, borderRadius: 7, border: `1px solid ${C.amber}30` }}>
                        <p style={{ fontSize: 11.5, color: C.amber, margin: 0, fontWeight: 600 }}>✏️ Edit request: {c.edit_request_note}</p>
                      </div>
                    )}
                    <p style={{ fontSize: 11, color: C.ink4, margin: "5px 0 0" }}>Submitted {timeAgo(c.created_at)}</p>
                  </div>
                  <div style={{ display: "flex", gap: 7, flexShrink: 0, flexWrap: "wrap", alignItems: "flex-start" }}>
                    {c.photo_url && (
                      <a href={c.photo_url} target="_blank" rel="noreferrer"
                        style={{ ...btnS(C.blueL, C.blue), textDecoration: "none" }}><FileText size={11} /> View doc</a>
                    )}
                    <button onClick={() => approveCert(c.id)} disabled={actionLoading === c.id}
                      style={btnS(C.greenL, C.green)}>
                      {actionLoading === c.id ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />} Approve
                    </button>
                    <button onClick={() => setRejectTarget({ id: c.id, docType: "cert" })} disabled={actionLoading === c.id}
                      style={btnS(C.redL, C.red)}><XCircle size={11} /> Reject</button>
                  </div>
                </div>
              </div>
            ))}

            {/* ── Insurance rows ── */}
            {group.insurance.map(p => (
              <div key={p.id} style={{ padding: "13px 18px", borderBottom: `1px solid ${C.line}` }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 14, flexWrap: "wrap" }}>
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: C.amberL, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1 }}>
                    <Shield size={15} color={C.amber} />
                  </div>
                  <div style={{ flex: 1, minWidth: 160 }}>
                    <p style={{ fontSize: 12.5, fontWeight: 700, color: C.ink, margin: "0 0 2px" }}>
                      Insurance — {p.insurance_type?.replace(/_/g, " ") || "Policy"}
                    </p>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "2px 12px" }}>
                      {[
                        p.insurer_name && `Insurer: ${p.insurer_name}`,
                        p.policy_number && `Policy: ${p.policy_number}`,
                        p.coverage_amount_cents && `Cover: ${fmtCoverage(p.coverage_amount_cents)}`,
                        p.holder_name && `Holder: ${p.holder_name}`,
                        p.expires_at && `Expires: ${p.expires_at}`,
                      ].filter(Boolean).map((item, i) => (
                        <span key={i} style={{ fontSize: 11.5, color: C.ink3 }}>{item}</span>
                      ))}
                    </div>
                    {p.edit_request_note && (
                      <div style={{ marginTop: 7, padding: "6px 10px", background: C.amberL, borderRadius: 7, border: `1px solid ${C.amber}30` }}>
                        <p style={{ fontSize: 11.5, color: C.amber, margin: 0, fontWeight: 600 }}>✏️ Edit request: {p.edit_request_note}</p>
                      </div>
                    )}
                    <p style={{ fontSize: 11, color: C.ink4, margin: "5px 0 0" }}>Submitted {timeAgo(p.created_at)}</p>
                  </div>
                  <div style={{ display: "flex", gap: 7, flexShrink: 0, flexWrap: "wrap", alignItems: "flex-start" }}>
                    {p.document_url && (
                      <a href={p.document_url} target="_blank" rel="noreferrer"
                        style={{ ...btnS(C.blueL, C.blue), textDecoration: "none" }}><FileText size={11} /> View doc</a>
                    )}
                    <button onClick={() => approveInsurance(p.id)} disabled={actionLoading === p.id}
                      style={btnS(C.greenL, C.green)}>
                      {actionLoading === p.id ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />} Approve
                    </button>
                    <button onClick={() => setRejectTarget({ id: p.id, docType: "insurance" })} disabled={actionLoading === p.id}
                      style={btnS(C.redL, C.red)}><XCircle size={11} /> Reject</button>
                  </div>
                </div>
              </div>
            ))}

            {/* ── Change request rows ── */}
            {group.change_requests.map(req => (
              <div key={req.id} style={{ padding: "13px 18px", borderBottom: `1px solid ${C.line}` }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 14, flexWrap: "wrap" }}>
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: C.amberL, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1 }}>
                    <AlertTriangle size={15} color={C.amber} />
                  </div>
                  <div style={{ flex: 1, minWidth: 220 }}>
                    <p style={{ fontSize: 12.5, fontWeight: 700, color: C.ink, margin: "0 0 2px" }}>
                      Change request — {req.request_type?.replace(/_/g, " ") || ""}
                    </p>
                    <pre style={{ whiteSpace: "pre-wrap", margin: "6px 0 0", padding: "8px 10px", background: C.bg, border: `1px solid ${C.line}`, borderRadius: 7, fontSize: 11, color: C.ink2, fontFamily: UI, lineHeight: 1.5 }}>
                      {JSON.stringify(req.payload, null, 2)}
                    </pre>
                    {req.note && <p style={{ fontSize: 11.5, color: C.ink4, margin: "6px 0 0" }}>{req.note}</p>}
                    <p style={{ fontSize: 11, color: C.ink4, margin: "5px 0 0" }}>Submitted {timeAgo(req.created_at)}</p>
                  </div>
                  <div style={{ display: "flex", gap: 7, flexShrink: 0, flexWrap: "wrap" }}>
                    <button onClick={() => approveChangeRequest(req.id)} disabled={actionLoading === req.id}
                      style={btnS(C.greenL, C.green)}><CheckCircle2 size={11} /> Approve</button>
                    <button onClick={() => rejectChangeRequest(req.id)} disabled={actionLoading === req.id}
                      style={btnS(C.redL, C.red)}><XCircle size={11} /> Reject</button>
                  </div>
                </div>
              </div>
            ))}

            {/* ── Card footer — Redistribute Leads ── */}
            <div style={{ padding: "10px 18px", background: C.bg, borderTop: `1px solid ${C.line}`, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <p style={{ fontSize: 11.5, color: C.ink4, margin: 0 }}>
                Force-push waiting open jobs to this tradie's lead queue
              </p>
              <button
                onClick={() => redistributeLeads(group.tradie_id, group.business_name)}
                disabled={actionLoading === `redist-${group.tradie_id}`}
                style={{ ...btnS(C.amberL, C.amber), fontWeight: 700, gap: 5 }}
              >
                {actionLoading === `redist-${group.tradie_id}`
                  ? <Loader2 size={11} className="animate-spin" />
                  : <Zap size={11} />
                }
                Redistribute Leads
              </button>
            </div>

          </div>
        ))}

        {total === 0 && !loading && (
          <div style={{ ...panelS, padding: "48px 24px", textAlign: "center" }}>
            <CheckCircle2 size={32} color={C.green} style={{ margin: "0 auto 12px" }} />
            <p style={{ fontSize: 15, fontWeight: 700, color: C.ink, margin: "0 0 4px" }}>All clear</p>
            <p style={{ fontSize: 13, color: C.ink4, margin: 0 }}>No pending verifications right now.</p>
          </div>
        )}
      </div>
    );
  };

  const [expandedJobId, setExpandedJobId] = React.useState<string | null>(null);

  const renderJobs = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <div style={{ position: "relative", flex: "1 1 200px" }}>
          <Search size={13} style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: C.ink4 }} />
          <input value={jobSearch} onChange={e => setJobSearch(e.target.value)}
            onKeyDown={e => e.key === "Enter" && load("jobs")}
            placeholder="Search job title…"
            style={{ width: "100%", padding: "9px 10px 9px 32px", borderRadius: 9, border: `1px solid ${C.line}`, fontSize: 13, color: C.ink, fontFamily: UI, boxSizing: "border-box", background: C.card }} />
        </div>
        <select value={jobStatusFilter} onChange={e => setJobStatusFilter(e.target.value)}
          style={{ padding: "9px 12px", borderRadius: 9, border: `1px solid ${C.line}`, fontSize: 13, color: C.ink, fontFamily: UI, background: C.card, minWidth: 150 }}>
          <option value="">All statuses</option>
          {[
            { v: "open",        l: "Open" },
            { v: "quoted",      l: "Quoted" },
            { v: "hired",       l: "Hired" },
            { v: "in_progress", l: "In Progress" },
            { v: "completed",   l: "Completed" },
            { v: "confirmed",   l: "Confirmed (done)" },
            { v: "closed",      l: "Closed (done)" },
            { v: "disputed",    l: "Disputed" },
            { v: "cancelled",   l: "Cancelled" },
          ].map(({ v, l }) => <option key={v} value={v}>{l}</option>)}
        </select>
        <button onClick={() => load("jobs")} style={btnS(C.primary, "#fff")}><Search size={13} /> Search</button>
      </div>
      <p style={{ fontSize: 12, color: C.ink4, margin: 0 }}>{jobsTotal} jobs</p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", background: C.card, borderRadius: 12, overflow: "hidden", boxShadow: SHADOW }}>
          <thead><tr>{["Title","Location","Status","Posted","Photos"].map(h => <th key={h} style={thS}>{h}</th>)}</tr></thead>
          <tbody>
            {jobs.length === 0 && !loading && (
              <tr><td colSpan={5} style={{ ...tdS, textAlign: "center", color: C.ink4, padding: 32 }}>No jobs found</td></tr>
            )}
            {jobs.map(j => (
              <React.Fragment key={j.id}>
                <tr
                  onClick={() => setExpandedJobId(expandedJobId === j.id ? null : j.id)}
                  style={{ cursor: "pointer", background: expandedJobId === j.id ? C.bg : "transparent" }}
                >
                  <td style={{ ...tdS, fontWeight: 600 }}>{j.title || "Untitled"}</td>
                  <td style={tdS}>{j.suburb || "—"}, {j.state || "—"}</td>
                  <td style={tdS}><StatusPill status={j.status} /></td>
                  <td style={{ ...tdS, fontSize: 11.5, color: C.ink4 }}>{j.created_at ? timeAgo(j.created_at) : "—"}</td>
                  <td style={tdS}>
                    {(j.after_photos?.length > 0 || j.photo_before_url) ? (
                      <span style={{ fontSize: 10.5, fontWeight: 700, padding: "3px 9px", borderRadius: 20, background: C.blueL, color: C.blue }}>
                        {(j.after_photos?.length || 0) + (j.photo_before_url ? 1 : 0)} photo{((j.after_photos?.length || 0) + (j.photo_before_url ? 1 : 0)) !== 1 ? "s" : ""}
                      </span>
                    ) : <span style={{ color: C.ink4, fontSize: 12 }}>—</span>}
                  </td>
                </tr>
                {expandedJobId === j.id && (
                  <tr>
                    <td colSpan={5} style={{ padding: "14px 18px", background: C.bg, borderBottom: `1px solid ${C.line}` }}>
                      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                        {j.completion_note && (
                          <p style={{ margin: 0, fontSize: 13, color: C.ink2 }}>
                            <strong>Completion note:</strong> {j.completion_note}
                          </p>
                        )}
                        {(j.photo_before_url || j.after_photos?.length > 0) && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                            {j.photo_before_url && (
                              <div>
                                <p style={{ margin: "0 0 4px", fontSize: 11, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.06em" }}>Before</p>
                                <a href={j.photo_before_url} target="_blank" rel="noreferrer">
                                  <img src={j.photo_before_url} alt="Before" style={{ width: 120, height: 90, objectFit: "cover", borderRadius: 8, border: `1px solid ${C.line}` }} />
                                </a>
                              </div>
                            )}
                            {j.after_photos?.length > 0 && (
                              <div>
                                <p style={{ margin: "0 0 4px", fontSize: 11, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.06em" }}>After ({j.after_photos.length})</p>
                                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                  {j.after_photos.map((p: any, i: number) => (
                                    <a key={i} href={p.url} target="_blank" rel="noreferrer">
                                      <img src={p.url} alt={`After ${i + 1}`} style={{ width: 120, height: 90, objectFit: "cover", borderRadius: 8, border: `1px solid ${C.line}` }} />
                                    </a>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                        {!j.photo_before_url && !j.after_photos?.length && !j.completion_note && (
                          <p style={{ margin: 0, fontSize: 13, color: C.ink4 }}>No photos or completion note for this job.</p>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderDisputes = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <p style={{ fontSize: 12, color: C.ink4, margin: 0 }}>{disputes.length} open dispute{disputes.length !== 1 ? "s" : ""}</p>
      {disputes.length === 0 && !loading && (
        <div style={{ ...panelS, padding: "48px 24px", textAlign: "center" }}>
          <CheckCircle2 size={32} color={C.green} style={{ margin: "0 auto 12px" }} />
          <p style={{ fontSize: 15, fontWeight: 700, color: C.ink, margin: "0 0 4px" }}>No open disputes</p>
          <p style={{ fontSize: 13, color: C.ink4, margin: 0 }}>Everything looks good.</p>
        </div>
      )}
      {disputes.map((d: any) => {
        const hw = d.homeowner || {};
        const tr = d.tradie || {};
        return (
          <div key={d.id} style={{ ...panelS, padding: "18px" }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
              <div style={{ width: 38, height: 38, borderRadius: 10, background: C.redL, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <AlertTriangle size={18} color={C.red} />
              </div>
              <div style={{ flex: 1, minWidth: 220 }}>
                <p style={{ fontSize: 15, fontWeight: 700, color: C.ink, margin: "0 0 3px" }}>{d.title || "Untitled job"}</p>
                <p style={{ fontSize: 11.5, color: C.ink4, margin: 0 }}>
                  {d.category ? `${d.category} | ` : ""}{d.suburb}, {d.state} | Disputed {d.dispute_raised_at ? timeAgo(d.dispute_raised_at) : timeAgo(d.updated_at)}
                </p>
              </div>
              <StatusPill status="disputed" />
            </div>

            {/* Homeowner reason -- the key thing admin needs to see */}
            <div style={{ background: C.redL, border: `1px solid ${C.red}33`, borderRadius: 10, padding: "12px 14px", marginBottom: 12 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: C.red, textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 6px" }}>
                Homeowner's reason
              </p>
              <p style={{ fontSize: 13, color: C.ink, margin: 0, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>
                {d.dispute_reason || <span style={{ color: C.ink4, fontStyle: "italic" }}>(no reason supplied)</span>}
              </p>
            </div>

            {/* Tradie completion note -- the other side of the story */}
            {d.completion_note && (
              <div style={{ background: C.greenL, border: `1px solid ${C.green}33`, borderRadius: 10, padding: "12px 14px", marginBottom: 12 }}>
                <p style={{ fontSize: 11, fontWeight: 700, color: C.green, textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 6px" }}>
                  Tradie's completion note
                </p>
                <p style={{ fontSize: 13, color: C.ink, margin: 0, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{d.completion_note}</p>
              </div>
            )}

            {/* Contacts: side-by-side */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <div style={{ background: "#fff", border: `1px solid ${C.line}`, borderRadius: 10, padding: "10px 14px" }}>
                <p style={{ fontSize: 10.5, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 5px" }}>Homeowner</p>
                <p style={{ fontSize: 13, fontWeight: 600, color: C.ink, margin: 0 }}>{hw.name || "-"}</p>
                <p style={{ fontSize: 11.5, color: C.ink3, margin: "2px 0 0" }}>{hw.email || "-"}{hw.phone ? ` | ${hw.phone}` : ""}</p>
              </div>
              <div style={{ background: "#fff", border: `1px solid ${C.line}`, borderRadius: 10, padding: "10px 14px" }}>
                <p style={{ fontSize: 10.5, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 5px" }}>Tradie</p>
                <p style={{ fontSize: 13, fontWeight: 600, color: C.ink, margin: 0 }}>{tr.business_name || tr.full_name || "-"}</p>
                <p style={{ fontSize: 11.5, color: C.ink3, margin: "2px 0 0" }}>{tr.email || "-"}{tr.phone ? ` | ${tr.phone}` : ""}</p>
                {tr.quote_amount != null && (
                  <p style={{ fontSize: 11.5, color: C.ink4, margin: "4px 0 0" }}>Accepted quote: <strong style={{ color: C.ink }}>${tr.quote_amount}</strong></p>
                )}
              </div>
            </div>

            {/* Photos -- before / after */}
            {(d.photo_before_url || d.photo_after_url || (d.after_photos && d.after_photos.length)) && (
              <div style={{ marginBottom: 12 }}>
                <p style={{ fontSize: 10.5, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 6px" }}>Evidence photos</p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {d.photo_before_url && (
                    <a href={d.photo_before_url} target="_blank" rel="noreferrer"
                      style={{ display: "block", width: 80, height: 80, borderRadius: 8, overflow: "hidden", border: `1px solid ${C.line}` }}>
                      <img src={d.photo_before_url} alt="Before" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    </a>
                  )}
                  {d.photo_after_url && (
                    <a href={d.photo_after_url} target="_blank" rel="noreferrer"
                      style={{ display: "block", width: 80, height: 80, borderRadius: 8, overflow: "hidden", border: `1px solid ${C.line}` }}>
                      <img src={d.photo_after_url} alt="After" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    </a>
                  )}
                  {(d.after_photos || []).map((p: any) => (
                    <a key={p.id} href={p.url} target="_blank" rel="noreferrer"
                      style={{ display: "block", width: 80, height: 80, borderRadius: 8, overflow: "hidden", border: `1px solid ${C.line}` }}>
                      <img src={p.url} alt="evidence" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Description + timeline */}
            {d.description && (
              <details style={{ marginTop: 8 }}>
                <summary style={{ cursor: "pointer", fontSize: 11.5, fontWeight: 700, color: C.ink3 }}>Full job description</summary>
                <p style={{ fontSize: 12.5, color: C.ink2, marginTop: 8, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{d.description}</p>
              </details>
            )}
            {/* Tradie's response(s) -- ordered oldest first, as a conversation */}
            {Array.isArray(d.tradie_responses) && d.tradie_responses.length > 0 && (
              <div style={{ background: "#EFF7FF", border: `1px solid #5BB3FF33`, borderRadius: 10, padding: "12px 14px", marginBottom: 12 }}>
                <p style={{ fontSize: 11, fontWeight: 700, color: C.blue, textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 8px" }}>
                  Tradie's response{d.tradie_responses.length > 1 ? `s (${d.tradie_responses.length})` : ""}
                </p>
                {d.tradie_responses.map((r: any) => (
                  <div key={r.id} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: `1px dashed ${C.line}` }}>
                    <p style={{ fontSize: 13, color: C.ink, margin: 0, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{r.response}</p>
                    {r.evidence_url && (
                      <a href={r.evidence_url} target="_blank" rel="noreferrer"
                        style={{ display: "inline-block", marginTop: 6, fontSize: 11.5, color: C.blue, textDecoration: "underline" }}>
                        View attached evidence
                      </a>
                    )}
                    <p style={{ fontSize: 11, color: C.ink4, margin: "4px 0 0" }}>{timeAgo(r.created_at)}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Resolution buttons -- four explicit paths */}
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${C.line}` }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: C.ink3, textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 10px" }}>
                Resolve dispute
              </p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button onClick={() => setResolveTarget({ id: d.id, resolution: "refund_homeowner", title: d.title })}
                  style={{ padding: "8px 12px", borderRadius: 8, background: C.red, color: "#fff", border: "none", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                  Refund homeowner
                </button>
                <button onClick={() => setResolveTarget({ id: d.id, resolution: "partial_refund", title: d.title })}
                  style={{ padding: "8px 12px", borderRadius: 8, background: C.amber, color: "#fff", border: "none", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                  Partial refund
                </button>
                <button onClick={() => setResolveTarget({ id: d.id, resolution: "side_tradie", title: d.title })}
                  style={{ padding: "8px 12px", borderRadius: 8, background: C.green, color: "#fff", border: "none", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                  Side with tradie
                </button>
                <button onClick={() => setResolveTarget({ id: d.id, resolution: "redo_work", title: d.title })}
                  style={{ padding: "8px 12px", borderRadius: 8, background: "#B85C00", color: "#fff", border: "none", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                  Order rework
                </button>
              </div>
            </div>

            {Array.isArray(d.timeline) && d.timeline.length > 0 && (
              <details style={{ marginTop: 12 }}>
                <summary style={{ cursor: "pointer", fontSize: 11.5, fontWeight: 700, color: C.ink3 }}>Timeline ({d.timeline.length})</summary>
                <div style={{ marginTop: 8, fontSize: 11.5, color: C.ink2 }}>
                  {d.timeline.map((ev: any, i: number) => (
                    <div key={i} style={{ display: "flex", gap: 8, padding: "4px 0", borderTop: i > 0 ? `1px solid ${C.line}` : "none" }}>
                      <span style={{ minWidth: 110, color: C.ink4 }}>{timeAgo(ev.created_at)}</span>
                      <span style={{ flex: 1 }}>
                        <strong>{ev.actor_role}</strong>: {ev.note || `${ev.old_value?.status || "?"} -> ${ev.new_value?.status || "?"}`}
                      </span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        );
      })}
    </div>
  );

  const renderReviews = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <p style={{ fontSize: 12, color: C.ink4, margin: 0 }}>{reviewsTotal} reviews</p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", background: C.card, borderRadius: 12, overflow: "hidden", boxShadow: SHADOW }}>
          <thead><tr>{["Rating","Comment","Posted","Action"].map(h => <th key={h} style={thS}>{h}</th>)}</tr></thead>
          <tbody>
            {reviews.length === 0 && !loading && (
              <tr><td colSpan={4} style={{ ...tdS, textAlign: "center", color: C.ink4, padding: 32 }}>No reviews</td></tr>
            )}
            {reviews.map(r => (
              <tr key={r.id}>
                <td style={tdS}><span style={{ fontWeight: 700, color: C.amber }}>{"★".repeat(r.rating)}</span><span style={{ color: C.line }}>{"★".repeat(5 - r.rating)}</span></td>
                <td style={{ ...tdS, maxWidth: 300 }}>{r.comment || <span style={{ color: C.ink4 }}>No comment</span>}</td>
                <td style={{ ...tdS, fontSize: 11.5, color: C.ink4 }}>{r.created_at ? timeAgo(r.created_at) : "—"}</td>
                <td style={tdS}>
                  <button onClick={() => messageReviewer(r.id)} disabled={actionLoading === r.id}
                    style={{ ...btnS(C.greenL, C.green), marginRight: 6 }}>
                    <Mail size={11} /> Message
                  </button>
                  <button onClick={() => deleteReview(r.id)} disabled={actionLoading === r.id}
                    style={btnS(C.redL, C.red)}>
                    {actionLoading === r.id ? <Loader2 size={11} className="animate-spin" /> : <XCircle size={11} />} Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const fmtDate = (d: string | null) => d ? new Date(d).toLocaleString("en-AU", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

  const renderCompleted = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* Filters */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <div style={{ position: "relative", flex: "1 1 200px" }}>
          <Search size={13} style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: C.ink4 }} />
          <input value={completedSearch} onChange={e => setCompletedSearch(e.target.value)}
            onKeyDown={e => e.key === "Enter" && load("completed")}
            placeholder="Search job title…"
            style={{ width: "100%", padding: "9px 10px 9px 32px", borderRadius: 9, border: `1px solid ${C.line}`, fontSize: 13, color: C.ink, fontFamily: UI, boxSizing: "border-box", background: C.card }} />
        </div>
        <select value={completedStatusFilter} onChange={e => setCompletedStatusFilter(e.target.value)}
          style={{ padding: "9px 12px", borderRadius: 9, border: `1px solid ${C.line}`, fontSize: 13, color: C.ink, fontFamily: UI, background: C.card, minWidth: 160 }}>
          <option value="">All (completed / confirmed / closed)</option>
          <option value="completed">Completed</option>
          <option value="confirmed">Confirmed</option>
          <option value="closed">Closed</option>
        </select>
        <button onClick={() => load("completed")} style={btnS(C.primary, "#fff")}><Search size={13} /> Search</button>
      </div>

      <p style={{ fontSize: 12, color: C.ink4, margin: 0 }}>{completedTotal} finished job{completedTotal !== 1 ? "s" : ""}</p>

      {completedJobs.length === 0 && !loading && (
        <div style={{ ...panelS, padding: "48px 24px", textAlign: "center" }}>
          <CheckCircle2 size={32} color={C.green} style={{ margin: "0 auto 12px" }} />
          <p style={{ fontSize: 15, fontWeight: 700, color: C.ink, margin: "0 0 4px" }}>No completed jobs yet</p>
          <p style={{ fontSize: 13, color: C.ink4, margin: 0 }}>Finished jobs will appear here.</p>
        </div>
      )}

      {completedJobs.map(j => (
        <div key={j.id} style={{ ...panelS, overflow: "visible" }}>
          {/* ── Summary row (always visible, click to expand) ── */}
          <div
            onClick={() => setExpandedCompletedId(expandedCompletedId === j.id ? null : j.id)}
            style={{ padding: "14px 16px", cursor: "pointer", display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
              background: expandedCompletedId === j.id ? C.bg : C.card, borderRadius: 12 }}
          >
            {/* Status dot */}
            <div style={{ width: 10, height: 10, borderRadius: "50%", flexShrink: 0,
              background: (j.status === "confirmed" || j.status === "closed" || j.status === "completed") ? C.green : C.amber }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: C.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {j.title || "Untitled job"}
              </p>
              <p style={{ margin: "2px 0 0", fontSize: 12, color: C.ink4 }}>
                {j.category || "—"} · {j.suburb || "—"}, {j.state || "—"}
                {j.tradie ? ` · ${j.tradie.business_name}` : ""}
              </p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
              {j.tradie?.quote_amount != null && (
                <span style={{ fontSize: 13, fontWeight: 700, color: C.green }}>${j.tradie.quote_amount.toLocaleString("en-AU")}</span>
              )}
              <StatusPill status={j.status} />
              {j.review && (
                <span style={{ fontSize: 11, background: C.amberL, color: C.amber, borderRadius: 20, padding: "3px 8px", fontWeight: 700 }}>
                  {"★".repeat(j.review.rating)}
                </span>
              )}
              {(j.after_photos?.length > 0 || j.photo_before_url) && (
                <span style={{ fontSize: 11, background: C.blueL, color: C.blue, borderRadius: 20, padding: "3px 8px", fontWeight: 700 }}>
                  {(j.after_photos?.length || 0) + (j.photo_before_url ? 1 : 0)} photo{((j.after_photos?.length || 0) + (j.photo_before_url ? 1 : 0)) !== 1 ? "s" : ""}
                </span>
              )}
              <ChevronDown size={14} color={C.ink4}
                style={{ transform: expandedCompletedId === j.id ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
            </div>
          </div>

          {/* — Expanded detail panel — */}
          {expandedCompletedId === j.id && (
            <div style={{ borderTop: `1px solid ${C.line}`, padding: "18px 18px 20px", display: "flex", flexDirection: "column", gap: 18 }}>

              {/* Row 1: Job info + Timeline */}
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                <div style={{ flex: "1 1 220px", background: C.bg, borderRadius: 10, padding: "12px 14px" }}>
                  <p style={{ margin: "0 0 8px", fontSize: 10, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.08em" }}>Job Details</p>
                  <p style={{ margin: "0 0 4px", fontSize: 13, fontWeight: 700, color: C.ink }}>{j.title}</p>
                  {j.description && <p style={{ margin: "0 0 8px", fontSize: 12.5, color: C.ink3, lineHeight: 1.55 }}>{j.description}</p>}
                  <p style={{ margin: "0 0 3px", fontSize: 12, color: C.ink3 }}><strong>Category:</strong> {j.category || "—"}</p>
                  <p style={{ margin: "0 0 3px", fontSize: 12, color: C.ink3 }}><strong>Location:</strong> {j.suburb}, {j.state} {j.postcode}</p>
                  <p style={{ margin: "0 0 3px", fontSize: 12, color: C.ink3 }}><strong>Urgency:</strong> {j.urgency || "—"}</p>
                  <p style={{ margin: 0, fontSize: 12, color: C.ink3 }}><strong>Job ID:</strong> <span style={{ fontFamily: "monospace", fontSize: 11 }}>{j.id}</span></p>
                </div>
                <div style={{ flex: "1 1 220px", background: C.bg, borderRadius: 10, padding: "12px 14px" }}>
                  <p style={{ margin: "0 0 8px", fontSize: 10, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.08em" }}>Timeline</p>
                  {[
                    { label: "Posted",    value: j.created_at },
                    { label: "Completed", value: j.completed_at },
                    { label: "Confirmed by homeowner", value: j.confirmed_by_user_at },
                    { label: "Last updated", value: j.updated_at },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, color: C.ink4 }}>{label}</span>
                      <span style={{ fontSize: 12, color: C.ink2, fontWeight: value ? 600 : 400 }}>{fmtDate(value)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Row 2: Homeowner + Tradie */}
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                <div style={{ flex: "1 1 200px", background: C.bg, borderRadius: 10, padding: "12px 14px" }}>
                  <p style={{ margin: "0 0 8px", fontSize: 10, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.08em" }}>Homeowner</p>
                  <p style={{ margin: "0 0 3px", fontSize: 13, fontWeight: 700, color: C.ink }}>{j.homeowner?.name || "—"}</p>
                  <p style={{ margin: "0 0 3px", fontSize: 12, color: C.ink3 }}>{j.homeowner?.email || "—"}</p>
                  <p style={{ margin: 0, fontSize: 12, color: C.ink3 }}>{j.homeowner?.phone || "No phone"}</p>
                </div>
                <div style={{ flex: "1 1 200px", background: C.bg, borderRadius: 10, padding: "12px 14px" }}>
                  <p style={{ margin: "0 0 8px", fontSize: 10, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.08em" }}>Tradie</p>
                  {j.tradie ? (
                    <>
                      <p style={{ margin: "0 0 3px", fontSize: 13, fontWeight: 700, color: C.ink }}>{j.tradie.business_name}</p>
                      <p style={{ margin: "0 0 3px", fontSize: 12, color: C.ink3 }}>{j.tradie.full_name}</p>
                      <p style={{ margin: "0 0 3px", fontSize: 12, color: C.ink3 }}>{j.tradie.email}</p>
                      <p style={{ margin: "0 0 6px", fontSize: 12, color: C.ink3 }}>{j.tradie.phone || "No phone"}</p>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <StatusPill status={j.tradie.verification_status} />
                        <span style={{ fontSize: 13, fontWeight: 700, color: C.green }}>
                          Quote: ${j.tradie.quote_amount?.toLocaleString("en-AU")}
                        </span>
                      </div>
                      {j.tradie.quote_message && (
                        <p style={{ margin: "8px 0 0", fontSize: 12, color: C.ink3, fontStyle: "italic", lineHeight: 1.5 }}>"{j.tradie.quote_message}"</p>
                      )}
                    </>
                  ) : (
                    <p style={{ margin: 0, fontSize: 12, color: C.ink4 }}>No accepted quote found</p>
                  )}
                </div>
              </div>

              {/* Row 3: Work evidence photos */}
              {(j.photo_before_url || j.after_photos?.length > 0) && (
                <div>
                  <p style={{ margin: "0 0 10px", fontSize: 10, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.08em" }}>Work Evidence</p>
                  <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
                    {j.photo_before_url && (
                      <div>
                        <p style={{ margin: "0 0 6px", fontSize: 11, fontWeight: 700, color: C.ink3 }}>BEFORE</p>
                        <a href={j.photo_before_url} target="_blank" rel="noreferrer">
                          <img src={j.photo_before_url} alt="Before"
                            style={{ width: 140, height: 105, objectFit: "cover", borderRadius: 10, border: `2px solid ${C.line}`, display: "block" }} />
                        </a>
                      </div>
                    )}
                    {j.after_photos?.length > 0 && (
                      <div>
                        <p style={{ margin: "0 0 6px", fontSize: 11, fontWeight: 700, color: C.green }}>AFTER ({j.after_photos.length})</p>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          {j.after_photos.map((p: any, i: number) => (
                            <a key={i} href={p.url} target="_blank" rel="noreferrer">
                              <img src={p.url} alt={`After ${i + 1}`}
                                style={{ width: 140, height: 105, objectFit: "cover", borderRadius: 10, border: `2px solid ${C.green}40`, display: "block" }} />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  {j.completion_note && (
                    <div style={{ marginTop: 10, background: C.greenL, borderRadius: 8, padding: "10px 14px" }}>
                      <p style={{ margin: 0, fontSize: 12.5, color: C.ink2, lineHeight: 1.6 }}>
                        <strong>Completion note:</strong> {j.completion_note}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Row 4: Review */}
              {j.review && (
                <div style={{ background: C.amberL, borderRadius: 10, padding: "12px 14px" }}>
                  <p style={{ margin: "0 0 6px", fontSize: 10, fontWeight: 700, color: C.ink4, textTransform: "uppercase", letterSpacing: "0.08em" }}>Homeowner Review</p>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 18, color: C.amber, letterSpacing: 2 }}>
                      {"★".repeat(j.review.rating)}{"☆".repeat(5 - j.review.rating)}
                    </span>
                    <span style={{ fontSize: 12, color: C.ink4 }}>{fmtDate(j.review.created_at)}</span>
                    <StatusPill status={j.review.status} />
                  </div>
                  {j.review.comment
                    ? <p style={{ margin: 0, fontSize: 13, color: C.ink2, lineHeight: 1.6, fontStyle: "italic" }}>"{j.review.comment}"</p>
                    : <p style={{ margin: 0, fontSize: 12, color: C.ink4 }}>No comment left.</p>
                  }
                </div>
              )}
              {!j.review && (
                <p style={{ margin: 0, fontSize: 12, color: C.ink4 }}>No review submitted for this job.</p>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );


  const renderUncategorised = () => (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: C.ink, margin: 0 }}>Uncategorised service requests</h2>
          <p style={{ fontSize: 12.5, color: C.ink3, margin: "4px 0 0" }}>
            Homeowners who couldn't find their service in the picker. Classify into a real trade
            (lead distribution starts immediately) or close out with a polite note.
          </p>
        </div>
        <span style={{ fontSize: 11.5, color: C.ink3 }}>{uncatTotal} pending</span>
      </div>

      {uncatItems.length === 0 ? (
        <div style={{ padding: "40px 20px", textAlign: "center", color: C.ink3, fontSize: 13, background: C.card, borderRadius: 12, boxShadow: SHADOW }}>
          Nothing in the queue — the picker has covered every recent request.
        </div>
      ) : uncatItems.map(j => (
        <div key={j.id} style={{ background: C.card, borderRadius: 12, padding: 16, boxShadow: SHADOW }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 240 }}>
              <p style={{ fontSize: 13, fontWeight: 700, color: C.ink, margin: 0 }}>{j.title || "(no title)"}</p>
              <p style={{ fontSize: 11, color: C.ink3, margin: "3px 0 8px" }}>
                {j.suburb ? `${j.suburb}${j.state ? `, ${j.state}` : ""} · ` : ""}
                {timeAgo(j.created_at)}
              </p>
              <p style={{ fontSize: 12.5, color: C.ink, margin: 0, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>
                {j.description || "(no description)"}
              </p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 220 }}>
              {uncatClassifyId === j.id ? (
                <>
                  <input value={uncatClassifySlug} onChange={e => setUncatClassifySlug(e.target.value)}
                    placeholder="e.g. plumbing, electrical, cleaning"
                    style={{ padding: "8px 10px", borderRadius: 8, border: `1px solid ${C.line}`, fontSize: 12, fontFamily: UI }} />
                  <div style={{ display: "flex", gap: 6 }}>
                    <button onClick={async () => {
                      try {
                        await api.post(`/admin/uncategorised/${j.id}/classify`, { category_slug: uncatClassifySlug.trim() });
                        setUncatClassifyId(null); setUncatClassifySlug("");
                        await load("uncategorised");
                      } catch (e: any) {
                        alert(e?.response?.data?.detail || "Could not classify.");
                      }
                    }} style={{ flex: 1, padding: "8px 10px", borderRadius: 8, background: C.green, color: "#fff", border: "none", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}>
                      Send to trade
                    </button>
                    <button onClick={() => { setUncatClassifyId(null); setUncatClassifySlug(""); }}
                      style={{ padding: "8px 10px", borderRadius: 8, background: "#f5f5f5", color: C.ink3, border: "none", fontSize: 11.5, cursor: "pointer" }}>
                      Cancel
                    </button>
                  </div>
                </>
              ) : uncatCloseId === j.id ? (
                <>
                  <textarea value={uncatCloseNote} onChange={e => setUncatCloseNote(e.target.value)}
                    placeholder="(Optional) note for the homeowner email"
                    rows={3}
                    style={{ padding: "8px 10px", borderRadius: 8, border: `1px solid ${C.line}`, fontSize: 12, fontFamily: UI, resize: "vertical" }} />
                  <div style={{ display: "flex", gap: 6 }}>
                    <button onClick={async () => {
                      try {
                        await api.post(`/admin/uncategorised/${j.id}/close`, { admin_note: uncatCloseNote.trim() || undefined });
                        setUncatCloseId(null); setUncatCloseNote("");
                        await load("uncategorised");
                      } catch (e: any) {
                        alert(e?.response?.data?.detail || "Could not close.");
                      }
                    }} style={{ flex: 1, padding: "8px 10px", borderRadius: 8, background: C.red, color: "#fff", border: "none", fontSize: 11.5, fontWeight: 700, cursor: "pointer" }}>
                      Close as not supported
                    </button>
                    <button onClick={() => { setUncatCloseId(null); setUncatCloseNote(""); }}
                      style={{ padding: "8px 10px", borderRadius: 8, background: "#f5f5f5", color: C.ink3, border: "none", fontSize: 11.5, cursor: "pointer" }}>
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <button onClick={() => setUncatClassifyId(j.id)}
                    style={{ padding: "8px 12px", borderRadius: 8, background: C.green, color: "#fff", border: "none", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                    Classify into a trade
                  </button>
                  <button onClick={() => setUncatCloseId(j.id)}
                    style={{ padding: "8px 12px", borderRadius: 8, background: "#fff", color: C.red, border: `1px solid ${C.red}40`, fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                    Close as not supported
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );

  const tabContent: Record<Tab, () => React.ReactNode> = {
    overview:     renderOverview,
    tradies:      renderTradies,
    homeowners:   renderHomeowners,
    verification: renderVerification,
    jobs:         renderJobs,
    completed:    renderCompleted,
    disputes:     renderDisputes,
    reviews:      renderReviews,
    uncategorised:renderUncategorised,
  };

  // Layout
  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: UI }}>

      {rejectTarget && (
        <RejectModal
          onClose={() => setRejectTarget(null)}
          onReject={(reason, note) => {
            if (rejectTarget.docType === "cert") rejectCert(rejectTarget.id, reason, note);
            else rejectInsurance(rejectTarget.id, reason, note);
          }}
        />
      )}

      {resolveTarget && (
        <div onClick={() => !resolveBusy && setResolveTarget(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div onClick={e => e.stopPropagation()}
            style={{ background: "#fff", borderRadius: 14, maxWidth: 480, width: "100%", padding: 22 }}>
            <h3 style={{ margin: "0 0 6px", fontSize: 17, fontWeight: 700, color: C.ink }}>
              Resolve: {resolveTarget.resolution.replace("_", " ")}
            </h3>
            <p style={{ margin: "0 0 14px", fontSize: 12.5, color: C.ink3 }}>
              Job: <strong>{resolveTarget.title}</strong>
            </p>
            {resolveTarget.resolution === "partial_refund" && (
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: C.ink3, display: "block", marginBottom: 4 }}>Refund amount (AUD)</label>
                <input type="number" min="0" step="0.01" value={resolveRefund} onChange={e => setResolveRefund(e.target.value)}
                  placeholder="e.g. 120.00"
                  style={{ width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${C.line}`, fontSize: 13, fontFamily: UI }} />
              </div>
            )}
            <label style={{ fontSize: 11.5, fontWeight: 700, color: C.ink3, display: "block", marginBottom: 4 }}>Decision note (sent to both parties)</label>
            <textarea value={resolveNote} onChange={e => setResolveNote(e.target.value)}
              placeholder="Explain the decision so both parties understand why."
              rows={4}
              style={{ width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${C.line}`, fontSize: 13, fontFamily: UI, resize: "vertical" }} />
            <div style={{ display: "flex", gap: 8, marginTop: 14, justifyContent: "flex-end" }}>
              <button onClick={() => setResolveTarget(null)} disabled={resolveBusy}
                style={{ padding: "9px 14px", borderRadius: 8, background: "#f5f5f5", color: C.ink3, border: "none", fontSize: 12.5, cursor: "pointer" }}>
                Cancel
              </button>
              <button onClick={async () => {
                if (!resolveTarget) return;
                if (resolveTarget.resolution === "partial_refund" && !(parseFloat(resolveRefund) > 0)) {
                  alert("Enter a positive refund amount."); return;
                }
                setResolveBusy(true);
                try {
                  await api.post(`/admin/disputes/${resolveTarget.id}/resolve`, {
                    resolution:    resolveTarget.resolution,
                    note:          resolveNote.trim() || undefined,
                    refund_amount: resolveTarget.resolution === "partial_refund" ? parseFloat(resolveRefund) : undefined,
                  });
                  setResolveTarget(null); setResolveNote(""); setResolveRefund("");
                  await load("disputes");
                } catch (e: any) {
                  alert(e?.response?.data?.detail || "Could not resolve dispute.");
                } finally { setResolveBusy(false); }
              }} disabled={resolveBusy}
                style={{ padding: "9px 16px", borderRadius: 8, background: C.ink, color: "#fff", border: "none", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>
                {resolveBusy ? "Resolving..." : "Confirm decision"}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @media (min-width: 768px) {
          .admin-sidebar { display: flex !important; }
          .admin-mobile-nav { display: none !important; }
          .admin-main { margin-left: 220px !important; }
        }
        @media (max-width: 767px) {
          .admin-sidebar { transform: translateX(-100%); transition: transform 0.25s; }
          .admin-sidebar.open { transform: translateX(0) !important; }
          .admin-main { margin-left: 0 !important; padding-bottom: 64px !important; }
        }
        .nav-item-btn:hover { background: rgba(255,255,255,0.06) !important; }
        .nav-item-btn:hover .nav-label { color: #D4AA3A !important; }
        .nav-item-btn.active-nav { background: rgba(212,170,58,0.14) !important; border: 1px solid rgba(212,170,58,0.22) !important; }
        tr:hover td { background: #FFF8E7; }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>

      {sidebarOpen && (
        <div onClick={() => setSidebarOpen(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 39 }} />
      )}

      <div className={`admin-sidebar${sidebarOpen ? " open" : ""}`}
        style={{ position: "fixed", top: 0, left: 0, bottom: 0, width: 220, background: C.primary,
          zIndex: 40, display: "flex", flexDirection: "column", boxShadow: SHADOW_MD }}>
        <div style={{ padding: "18px 16px 14px", borderBottom: "1px solid rgba(255,255,255,0.08)", display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 9, background: "#D4AA3A", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "0 3px 10px rgba(212,170,58,0.35)" }}>
            <Shield size={16} color="#071D36" fill="#071D36" />
          </div>
          <div>
            <p style={{ fontSize: 14, fontWeight: 800, color: "#D4AA3A", margin: 0, letterSpacing: "-0.01em" }}>ProConnect</p>
            <p style={{ fontSize: 9, color: "rgba(255,255,255,0.4)", margin: "2px 0 0", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.14em" }}>Admin Console</p>
          </div>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "10px 8px" }}>
          <p style={{ fontSize: 9, fontWeight: 700, color: "rgba(255,255,255,0.35)", textTransform: "uppercase", letterSpacing: "0.14em", padding: "8px 12px 6px", margin: 0 }}>Navigation</p>
          {navItems.map(n => {
            const Icon = n.icon;
            const active = tab === n.key;
            const badge = n.key === "verification"
              ? (pendingTradieCount || n.badge)
              : n.key === "disputes" ? (disputes.length || n.badge) : n.badge;
            return (
              <button key={n.key} onClick={() => switchTab(n.key)}
                className={`nav-item-btn${active ? " active-nav" : ""}`}
                style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "9px 12px",
                  borderRadius: 9, border: active ? "1px solid rgba(212,170,58,0.22)" : "1px solid transparent",
                  cursor: "pointer", background: active ? "rgba(212,170,58,0.14)" : "transparent",
                  color: active ? "#D4AA3A" : "rgba(255,255,255,0.75)", fontSize: 13, fontWeight: active ? 600 : 500, fontFamily: UI,
                  textAlign: "left", marginBottom: 2, transition: "all 0.15s" }}>
                <Icon size={15} style={{ flexShrink: 0, color: active ? "#D4AA3A" : "#5BB3FF" }} />
                <span className="nav-label" style={{ flex: 1, color: "inherit", transition: "color 0.15s" }}>{n.label}</span>
                {badge ? (
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 10,
                    background: "rgba(239,68,68,0.2)", color: "#ff8a80", border: "1px solid rgba(239,68,68,0.3)" }}>
                    {badge}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
        <div style={{ padding: "12px 16px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
          <p style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", margin: "0 0 8px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user?.email}</p>
          <button onClick={() => router.push("/")}
            style={{ display: "flex", alignItems: "center", gap: 8, background: "none", border: "none",
              color: "rgba(255,255,255,0.45)", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: UI, padding: 0, transition: "color 0.15s" }}
            onMouseEnter={e => (e.currentTarget.style.color = "#FF6B6B")}
            onMouseLeave={e => (e.currentTarget.style.color = "rgba(255,255,255,0.45)")}>
            <LogOut size={13} /> Exit admin
          </button>
        </div>
      </div>

      <div className="admin-main" style={{ transition: "margin 0.25s" }}>
        <div style={{ position: "sticky", top: 0, zIndex: 30, background: "#071D36",
          borderBottom: "1px solid rgba(255,255,255,0.08)", padding: "0 20px", height: 52,
          display: "flex", alignItems: "center", justifyContent: "space-between", boxShadow: "0 2px 12px rgba(7,29,54,0.4)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button onClick={() => setSidebarOpen(v => !v)}
              style={{ background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.12)", cursor: "pointer", color: "rgba(255,255,255,0.8)",
                display: "flex", alignItems: "center", padding: "5px 6px", borderRadius: 8 }}>
              <Menu size={18} />
            </button>
            <p style={{ fontSize: 15, fontWeight: 700, color: "#D4AA3A", margin: 0 }}>
              {navItems.find(n => n.key === tab)?.label}
            </p>
          </div>
          <button onClick={() => load(tab)} disabled={loading}
            style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 14px",
              borderRadius: 8, border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.08)",
              color: "rgba(255,255,255,0.75)", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: UI, transition: "all 0.15s" }}
            onMouseEnter={e => { e.currentTarget.style.background = "rgba(212,170,58,0.15)"; e.currentTarget.style.color = "#D4AA3A"; }}
            onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.08)"; e.currentTarget.style.color = "rgba(255,255,255,0.75)"; }}>
            Refresh
          </button>
        </div>

        <div style={{ padding: "20px 20px 40px", maxWidth: 1200, margin: "0 auto" }}>
          {error && (
            <div style={{ padding: "12px 16px", background: C.redL, border: `1px solid ${C.red}30`,
              borderRadius: 10, marginBottom: 16, fontSize: 13, color: C.red, fontWeight: 600 }}>
              {error}
            </div>
          )}
          {loading ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, gap: 10 }}>
              <Loader2 size={20} color={C.primary} className="animate-spin" />
              <span style={{ fontSize: 13, color: C.ink3, fontWeight: 600 }}>Loading…</span>
            </div>
          ) : (
            tabContent[tab]?.()
          )}
        </div>
      </div>
    </div>
  );
}
