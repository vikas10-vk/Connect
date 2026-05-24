"use client";

/**
 * MarkCompleteModal — practice mode: completion note only (no photo upload).
 * POST /jobs/{job_id}/complete with { completion_note }.
 * Re-enable photos when R2/storage API keys are configured.
 */

import React, { useState } from "react";
import { CheckCircle2, Loader2, X, AlertCircle } from "lucide-react";
import api from "@/src/lib/api";

interface Props {
  jobId: string;
  jobTitle?: string;
  onClose: () => void;
  onCompleted: () => void;
}

type Stage = "idle" | "submitting" | "success";

/** Minimum note length — keep low for practice; raise when photos are required again. */
const MIN_NOTE_LEN = 5;

export default function MarkCompleteModal({
  jobId,
  jobTitle,
  onClose,
  onCompleted,
}: Props) {
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const busy = stage === "submitting";
  const trimmedNote = note.trim();
  const hasValidNote = trimmedNote.length >= MIN_NOTE_LEN;
  const canSubmit = hasValidNote;

  const handleSubmit = async () => {
    if (!canSubmit) {
      setError(`Please enter a completion note (at least ${MIN_NOTE_LEN} characters).`);
      return;
    }
    setError(null);

    try {
      setStage("submitting");
      await api.post(`/jobs/${jobId}/complete`, {
        photo_after_urls: [],
        completion_note: trimmedNote,
      });

      setStage("success");
      setTimeout(() => {
        onCompleted();
        onClose();
      }, 1400);
    } catch (err: unknown) {
      setStage("idle");
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      const raw = e?.response?.data?.detail ?? e?.message;
      const msg =
        typeof raw === "string"
          ? raw
          : Array.isArray(raw)
            ? (raw as any[]).map((x: { msg?: string }) => x?.msg).filter(Boolean).join(". ")
            : "Something went wrong. Please try again.";
      setError(msg || "Something went wrong. Please try again.");
    }
  };

  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !busy) onClose();
  };

  return (
    <div
      onClick={handleOverlayClick}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(7, 29, 54, 0.55)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
      }}
    >
      <div
        style={{
          background: "#FFFFFF",
          borderRadius: 24,
          width: "100%",
          maxWidth: 520,
          maxHeight: "90vh",
          overflowY: "auto",
          boxShadow: "0 24px 72px rgba(7,29,54,0.22), 0 4px 16px rgba(7,29,54,0.08)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "20px 24px 18px",
            borderBottom: "1px solid #E8D9B0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            position: "sticky",
            top: 0,
            background: "#FFFFFF",
            zIndex: 1,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                background: "#EDF3EE",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <CheckCircle2 size={20} color="#5B7560" />
            </div>
            <div>
              <p style={{ fontWeight: 800, fontSize: 16, color: "#071D36", margin: 0, lineHeight: 1.3 }}>
                Mark job as complete
              </p>
              {jobTitle && (
                <p
                  style={{
                    fontSize: 12,
                    color: "#56677A",
                    margin: "2px 0 0",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: 300,
                  }}
                >
                  {jobTitle}
                </p>
              )}
            </div>
          </div>
          {!busy && stage !== "success" && (
            <button
              type="button"
              onClick={onClose}
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                border: "1px solid #D7E4F1",
                background: "#FFF8E7",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#56677A",
                flexShrink: 0,
              }}
            >
              <X size={15} />
            </button>
          )}
        </div>

        <div style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
          {stage === "success" ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 12,
                padding: "28px 0",
                textAlign: "center",
              }}
            >
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 16,
                  background: "#EDF3EE",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <CheckCircle2 size={28} color="#5B7560" />
              </div>
              <p style={{ fontWeight: 800, fontSize: 17, color: "#071D36", margin: 0 }}>
                Job marked as complete!
              </p>
              <p style={{ fontSize: 13, color: "#56677A", margin: "6px 0 0", lineHeight: 1.6 }}>
                The homeowner has 48 hours to confirm or raise a dispute.
              </p>
            </div>
          ) : (
            <>
              <div
                style={{
                  padding: "11px 14px",
                  borderRadius: 11,
                  background: "#EDF3EE",
                  border: "1px solid #5B756040",
                }}
              >
                <p style={{ fontSize: 12, color: "#4A6350", margin: 0, lineHeight: 1.6 }}>
                  Photo upload is paused while storage is being set up. Describe the work you
                  completed in the note below to mark this job done.
                </p>
              </div>

              <div>
                <p
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "#56677A",
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    margin: "0 0 8px",
                  }}
                >
                  Completion note{" "}
                  <span style={{ color: "#A8423A" }}>*</span>
                </p>
                <textarea
                  value={note}
                  onChange={(e) => {
                    setNote(e.target.value);
                    if (error) setError(null);
                  }}
                  disabled={busy}
                  placeholder="e.g. Pool cleaned, chemicals balanced, site left tidy."
                  maxLength={1000}
                  rows={4}
                  style={{
                    width: "100%",
                    padding: "12px 14px",
                    borderRadius: 12,
                    border: `1.5px solid ${hasValidNote ? "#5B7560" : "#D7E4F1"}`,
                    background: busy ? "#FFF8E7" : "#FFFFFF",
                    color: "#071D36",
                    fontSize: 13.5,
                    lineHeight: 1.6,
                    resize: "vertical",
                    outline: "none",
                    fontFamily: "inherit",
                    boxSizing: "border-box",
                  }}
                />
                <p style={{ fontSize: 11, color: "#8A9BA8", textAlign: "right", margin: "4px 0 0" }}>
                  {note.length}/1000
                  {trimmedNote.length > 0 && trimmedNote.length < MIN_NOTE_LEN && (
                    <span style={{ color: "#A8423A", marginLeft: 8 }}>
                      {MIN_NOTE_LEN - trimmedNote.length} more character
                      {MIN_NOTE_LEN - trimmedNote.length === 1 ? "" : "s"} needed
                    </span>
                  )}
                </p>
              </div>

              {error && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: "#F7E6E4",
                    border: "1px solid #A8423A30",
                  }}
                >
                  <AlertCircle size={15} color="#A8423A" style={{ flexShrink: 0, marginTop: 1 }} />
                  <p style={{ fontSize: 13, color: "#A8423A", fontWeight: 600, margin: 0, lineHeight: 1.5 }}>
                    {error}
                  </p>
                </div>
              )}

              <div
                style={{
                  padding: "11px 14px",
                  borderRadius: 11,
                  background: "#FFF8E7",
                  border: "1px solid #E8D9B0",
                }}
              >
                <p style={{ fontSize: 12, color: "#56677A", margin: 0, lineHeight: 1.6 }}>
                  <strong style={{ color: "#071D36" }}>What happens next:</strong> The homeowner
                  is notified and has <strong>48 hours</strong> to confirm or raise a dispute.
                </p>
              </div>
            </>
          )}
        </div>

        {stage !== "success" && (
          <div
            style={{
              padding: "16px 24px 20px",
              borderTop: "1px solid #E8D9B0",
              display: "flex",
              gap: 10,
              position: "sticky",
              bottom: 0,
              background: "#FFFFFF",
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              style={{
                flex: 1,
                padding: "12px",
                borderRadius: 12,
                border: "1.5px solid #D7E4F1",
                background: "#FFF8E7",
                color: "#56677A",
                fontSize: 13.5,
                fontWeight: 700,
                cursor: busy ? "default" : "pointer",
                opacity: busy ? 0.5 : 1,
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={busy || !canSubmit}
              style={{
                flex: 2,
                padding: "12px",
                borderRadius: 12,
                border: "none",
                background: canSubmit && !busy
                  ? "linear-gradient(135deg, #5B7560, #4A6350)"
                  : "#C8D8E6",
                color: canSubmit && !busy ? "#FFFFFF" : "#8A9BA8",
                fontSize: 13.5,
                fontWeight: 700,
                cursor: canSubmit && !busy ? "pointer" : "not-allowed",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                boxShadow: canSubmit && !busy ? "0 4px 14px rgba(91,117,96,0.28)" : "none",
              }}
            >
              {busy ? (
                <>
                  <Loader2 size={15} className="animate-spin" /> Submitting...
                </>
              ) : (
                <>
                  <CheckCircle2 size={15} /> Mark as complete
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
