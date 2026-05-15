"use client";

/**
 * MarkCompleteModal
 *
 * Tradie marks an in-progress job as complete.
 * Flow:
 *  1. Tradie picks 1–3 after-photos (at least one required by backend).
 *  2. Optionally adds a short completion note.
 *  3. On submit:
 *       a. POST /api/upload-photo for each photo → [public_url, ...]
 *       b. POST /jobs/{job_id}/complete  → { photo_after_urls, status, message }
 *  4. On success → calls onCompleted() so the parent can refresh.
 */

import React, { useCallback, useRef, useState } from "react";
import {
  Camera,
  CheckCircle2,
  Loader2,
  Plus,
  Trash2,
  X,
  AlertCircle,
  ImageIcon,
} from "lucide-react";
import api from "@/src/lib/api";

interface Props {
  jobId: string;
  jobTitle?: string;
  onClose: () => void;
  onCompleted: () => void;
}

type Stage = "idle" | "uploading" | "submitting" | "success";

interface PhotoEntry {
  file: File;
  preview: string; // data-URL for display
}

const MAX_PHOTOS = 3;

export default function MarkCompleteModal({
  jobId,
  jobTitle,
  onClose,
  onCompleted,
}: Props) {
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [photos, setPhotos] = useState<PhotoEntry[]>([]);
  const [note, setNote] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0); // 0–100
  const fileInputRef = useRef<HTMLInputElement>(null);

  const busy = stage === "uploading" || stage === "submitting";

  // ── Photo helpers ──────────────────────────────────────────────────────────

  const addFiles = (files: FileList | File[]) => {
    const arr = Array.from(files);
    const remaining = MAX_PHOTOS - photos.length;
    if (remaining <= 0) {
      setError(`Maximum ${MAX_PHOTOS} photos allowed.`);
      return;
    }
    const toAdd = arr.slice(0, remaining);
    const invalid = toAdd.find((f) => !f.type.startsWith("image/"));
    if (invalid) {
      setError("Please select image files only (JPG, PNG, HEIC…).");
      return;
    }
    const tooBig = toAdd.find((f) => f.size > 10_000_000);
    if (tooBig) {
      setError("Each photo must be under 10 MB.");
      return;
    }
    setError(null);

    // Generate previews
    toAdd.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        setPhotos((prev) => {
          if (prev.length >= MAX_PHOTOS) return prev;
          return [...prev, { file, preview: e.target?.result as string }];
        });
      };
      reader.readAsDataURL(file);
    });
  };

  const removePhoto = (idx: number) => {
    setPhotos((prev) => prev.filter((_, i) => i !== idx));
    setError(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) addFiles(e.target.files);
    e.target.value = "";
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [photos.length]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const handleDragLeave = () => setIsDragging(false);

  // ── Submit ─────────────────────────────────────────────────────────────────

  const handleSubmit = async () => {
    if (photos.length === 0) {
      setError("At least one after-photo is required to mark the job complete.");
      return;
    }
    setError(null);

    try {
      // Step 1 — upload each photo, track progress
      setStage("uploading");
      const publicUrls: string[] = [];

      for (let i = 0; i < photos.length; i++) {
        setUploadProgress(Math.round((i / photos.length) * 100));
        const fd = new FormData();
        fd.append("file", photos[i].file);
        const res = await fetch("/api/upload-photo", { method: "POST", body: fd });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body?.detail || `Photo ${i + 1} upload failed. Please try again.`);
        }
        const { public_url } = await res.json();
        publicUrls.push(public_url);
      }
      setUploadProgress(100);

      // Step 2 — mark job complete with all photo URLs
      setStage("submitting");
      await api.post(`/jobs/${jobId}/complete`, {
        photo_after_urls: publicUrls,
        completion_note: note.trim() || undefined,
      });

      setStage("success");
      setTimeout(() => {
        onCompleted();
        onClose();
      }, 1400);
    } catch (err: any) {
      setStage("idle");
      setUploadProgress(0);
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Something went wrong. Please try again.";
      setError(msg);
    }
  };

  // ── Overlay click ──────────────────────────────────────────────────────────
  const handleOverlayClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !busy) onClose();
  };

  // ── Render ─────────────────────────────────────────────────────────────────
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
        {/* ── Header ─────────────────────────────────────────────────────── */}
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

        {/* ── Body ───────────────────────────────────────────────────────── */}
        <div style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 18 }}>

          {/* Success */}
          {stage === "success" ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
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
              <div>
                <p style={{ fontWeight: 800, fontSize: 17, color: "#071D36", margin: 0 }}>
                  Job marked as complete!
                </p>
                <p style={{ fontSize: 13, color: "#56677A", margin: "6px 0 0", lineHeight: 1.6 }}>
                  The homeowner has 48 hours to confirm or raise a dispute.
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* ── Photo section ── */}
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <p style={{ fontSize: 12, fontWeight: 700, color: "#56677A", textTransform: "uppercase", letterSpacing: "0.08em", margin: 0 }}>
                    After photos{" "}
                    <span style={{ color: "#A8423A" }}>*</span>
                  </p>
                  <span style={{ fontSize: 11.5, color: photos.length >= MAX_PHOTOS ? "#5B7560" : "#8A9BA8", fontWeight: 600 }}>
                    {photos.length} / {MAX_PHOTOS}
                  </span>
                </div>

                {/* Photo grid */}
                {photos.length > 0 && (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: photos.length === 1 ? "1fr" : "repeat(3, 1fr)",
                      gap: 8,
                      marginBottom: 10,
                    }}
                  >
                    {photos.map((p, idx) => (
                      <div key={idx} style={{ position: "relative", borderRadius: 12, overflow: "hidden" }}>
                        <img
                          src={p.preview}
                          alt={`Completion photo ${idx + 1}`}
                          style={{
                            width: "100%",
                            height: photos.length === 1 ? 180 : 110,
                            objectFit: "cover",
                            display: "block",
                            border: "1px solid #D7E4F1",
                            borderRadius: 12,
                          }}
                        />
                        {!busy && (
                          <button
                            onClick={() => removePhoto(idx)}
                            style={{
                              position: "absolute",
                              top: 6,
                              right: 6,
                              width: 26,
                              height: 26,
                              borderRadius: 7,
                              background: "rgba(255,255,255,0.92)",
                              border: "1px solid #D7E4F1",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              color: "#A8423A",
                            }}
                          >
                            <Trash2 size={12} />
                          </button>
                        )}
                        <div
                          style={{
                            position: "absolute",
                            bottom: 6,
                            left: 6,
                            background: "rgba(7,29,54,0.6)",
                            color: "#fff",
                            fontSize: 10,
                            fontWeight: 700,
                            padding: "2px 7px",
                            borderRadius: 6,
                          }}
                        >
                          {idx + 1}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Upload zone — shown if under max */}
                {photos.length < MAX_PHOTOS && (
                  <div
                    onClick={() => !busy && fileInputRef.current?.click()}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    style={{
                      border: `2px dashed ${isDragging ? "#5B7560" : "#D7E4F1"}`,
                      borderRadius: 14,
                      padding: photos.length === 0 ? "28px 20px" : "14px 20px",
                      textAlign: "center",
                      cursor: busy ? "default" : "pointer",
                      background: isDragging ? "#EDF3EE" : "#FFF8E7",
                      transition: "all 0.15s",
                      display: "flex",
                      flexDirection: photos.length === 0 ? "column" : "row",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: photos.length === 0 ? 10 : 8,
                      opacity: busy ? 0.5 : 1,
                    }}
                  >
                    {photos.length === 0 ? (
                      <>
                        <div
                          style={{
                            width: 44,
                            height: 44,
                            borderRadius: 12,
                            background: "#F5EDD0",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          <ImageIcon size={20} color="#56677A" />
                        </div>
                        <div>
                          <p style={{ fontWeight: 700, fontSize: 14, color: "#071D36", margin: 0 }}>
                            Upload completion photos
                          </p>
                          <p style={{ fontSize: 12, color: "#56677A", margin: "4px 0 0" }}>
                            Click to select or drag &amp; drop · up to {MAX_PHOTOS} photos · JPG, PNG, HEIC · max 10 MB each
                          </p>
                        </div>
                        <div
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            padding: "8px 16px",
                            borderRadius: 9,
                            background: "#071D36",
                            color: "#fff",
                            fontSize: 12.5,
                            fontWeight: 600,
                            marginTop: 4,
                          }}
                        >
                          <Camera size={13} /> Choose photos
                        </div>
                      </>
                    ) : (
                      <>
                        <Plus size={15} color="#56677A" />
                        <span style={{ fontSize: 13, fontWeight: 600, color: "#56677A" }}>
                          Add another photo ({MAX_PHOTOS - photos.length} remaining)
                        </span>
                      </>
                    )}
                  </div>
                )}

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  capture="environment"
                  style={{ display: "none" }}
                  onChange={handleFileChange}
                />
              </div>

              {/* ── Upload progress bar (during upload) ── */}
              {stage === "uploading" && (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: "#56677A" }}>
                      Uploading photos…
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "#5B7560" }}>
                      {uploadProgress}%
                    </span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: "#F5EDD0", overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${uploadProgress}%`,
                        background: "linear-gradient(90deg, #5B7560, #4A6350)",
                        borderRadius: 3,
                        transition: "width 0.3s ease",
                      }}
                    />
                  </div>
                </div>
              )}

              {/* ── Completion note ── */}
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
                  <span style={{ color: "#8A785A", fontWeight: 500, textTransform: "none", letterSpacing: 0 }}>
                    (optional)
                  </span>
                </p>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  disabled={busy}
                  placeholder="e.g. All work completed as agreed. Cleaned up the site. Please let me know if you have any questions."
                  maxLength={1000}
                  rows={3}
                  style={{
                    width: "100%",
                    padding: "12px 14px",
                    borderRadius: 12,
                    border: "1.5px solid #D7E4F1",
                    background: busy ? "#FFF8E7" : "#FFFFFF",
                    color: "#071D36",
                    fontSize: 13.5,
                    lineHeight: 1.6,
                    resize: "vertical",
                    outline: "none",
                    fontFamily: "inherit",
                    boxSizing: "border-box",
                    transition: "border-color 0.15s",
                  }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = "#5B7560")}
                  onBlur={(e) => (e.currentTarget.style.borderColor = "#D7E4F1")}
                />
                <p style={{ fontSize: 11, color: "#8A9BA8", textAlign: "right", margin: "4px 0 0" }}>
                  {note.length}/1000
                </p>
              </div>

              {/* ── Error ── */}
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

              {/* ── Info note ── */}
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
                  If they don't respond, the job closes automatically.
                </p>
              </div>
            </>
          )}
        </div>

        {/* ── Footer ─────────────────────────────────────────────────────── */}
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
                transition: "all 0.15s",
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={busy || photos.length === 0}
              style={{
                flex: 2,
                padding: "12px",
                borderRadius: 12,
                border: "none",
                background:
                  busy || photos.length === 0
                    ? "#C8D8E6"
                    : "linear-gradient(135deg, #5B7560, #4A6350)",
                color: busy || photos.length === 0 ? "#8A9BA8" : "#FFFFFF",
                fontSize: 13.5,
                fontWeight: 700,
                cursor: busy || photos.length === 0 ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                transition: "all 0.15s",
                boxShadow:
                  !busy && photos.length > 0
                    ? "0 4px 14px rgba(91,117,96,0.28)"
                    : "none",
              }}
            >
              {stage === "uploading" ? (
                <><Loader2 size={15} className="animate-spin" /> Uploading {photos.length} photo{photos.length > 1 ? "s" : ""}…</>
              ) : stage === "submitting" ? (
                <><Loader2 size={15} className="animate-spin" /> Submitting…</>
              ) : (
                <><CheckCircle2 size={15} /> Mark as complete</>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
