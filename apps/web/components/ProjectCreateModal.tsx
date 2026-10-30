"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { ASPECT_LABELS, ASPECT_SIZES, STYLE_PRESETS } from "@/lib/utils";
import { PlusIcon, XIcon } from "./icons";

export function ProjectCreateModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (project: Project) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [aspect, setAspect] = useState("16:9");
  const [style, setStyle] = useState("cinematic");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const project = await api.projects.create({
        name: name.trim(),
        description: description.trim(),
        aspect_ratio: aspect,
        style_preset: style,
      });
      setName("");
      setDescription("");
      onCreated(project);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذّر إنشاء المشروع");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form
        className="modal"
        style={{ maxWidth: 560 }}
        onClick={(event) => event.stopPropagation()}
        onSubmit={submit}
      >
        <div className="card-head">
          <div className="card-title">
            <PlusIcon size={17} />
            مشروع جديد
          </div>
          <button type="button" className="btn-icon" onClick={onClose} aria-label="إغلاق">
            <XIcon size={16} />
          </button>
        </div>
        <div className="stack" style={{ padding: 20 }}>
          <div className="field">
            <label className="label">
              اسم المشروع <span className="hint">مطلوب</span>
            </label>
            <input
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="مثال: إعلان مطعم — ريلز"
              maxLength={120}
              autoFocus
            />
          </div>
          <div className="field">
            <label className="label">الوصف</label>
            <textarea
              className="textarea"
              style={{ minHeight: 74 }}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="فكرة المشروع، الجمهور، النبرة…"
              maxLength={2000}
            />
          </div>
          <div className="field">
            <label className="label">نسبة العرض</label>
            <div className="chips">
              {Object.entries(ASPECT_LABELS).map(([key, label]) => (
                <button
                  type="button"
                  key={key}
                  className={`chip${aspect === key ? " active" : ""}`}
                  onClick={() => setAspect(key)}
                >
                  {label}
                  <span style={{ opacity: 0.55, marginInlineStart: 6, fontSize: 10 }}>
                    {ASPECT_SIZES[key].join("×")}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label className="label">الأسلوب الافتراضي</label>
            <div className="chips">
              {STYLE_PRESETS.map((preset) => (
                <button
                  type="button"
                  key={preset.id}
                  className={`chip${style === preset.id ? " active" : ""}`}
                  onClick={() => setStyle(preset.id)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
          {error ? (
            <div className="tiny" style={{ color: "var(--danger)" }}>
              {error}
            </div>
          ) : null}
          <div className="row" style={{ justifyContent: "flex-end", marginTop: 6 }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              إلغاء
            </button>
            <button className="btn btn-primary" disabled={busy || !name.trim()}>
              {busy ? <span className="spinner" /> : <PlusIcon size={16} />}
              إنشاء المشروع
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
