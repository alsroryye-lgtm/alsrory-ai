"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { api, mediaUrl } from "@/lib/api";
import type { Asset, Project } from "@/lib/types";
import { ASPECT_LABELS, formatDuration } from "@/lib/utils";
import { Toast, type ToastState } from "@/components/Toast";
import { VideoModal } from "@/components/VideoModal";
import {
  ArrowLeftIcon,
  CheckIcon,
  ClockIcon,
  DownloadIcon,
  FilmIcon,
  LayersIcon,
  PlayIcon,
  PlusIcon,
  ScissorsIcon,
  TrashIcon,
  UploadIcon,
} from "@/components/icons";

function EditorInner() {
  const params = useSearchParams();
  const queryProject = params.get("project") || "";

  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [timeline, setTimeline] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [aspect, setAspect] = useState("16:9");
  const [filename, setFilename] = useState("alsrory-final.mp4");
  const [exporting, setExporting] = useState(false);
  const [exportAsset, setExportAsset] = useState<Asset | null>(null);
  const [modalAsset, setModalAsset] = useState<Asset | null>(null);
  const [toast, setToast] = useState<ToastState>(null);
  const [loading, setLoading] = useState(true);

  const loadProjects = useCallback(async () => {
    try {
      const list = await api.projects.list();
      setProjects(list);
      const target = list.find((item) => item.id === queryProject)?.id || list[0]?.id || "";
      setProjectId((current) => current || target);
      const project = list.find((item) => item.id === (target || queryProject));
      if (project) setAspect(project.aspect_ratio);
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر تحميل المشاريع",
        kind: "err",
      });
    }
  }, [queryProject]);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.assets.list(projectId || undefined, undefined, 200);
      const videos = list.filter((item) => item.kind === "video");
      setAssets(list);
      setTimeline((current) => {
        if (current.length) return current;
        // Exports stay in the library; they are not auto-appended as clips.
        return [...videos].reverse().map((item) => item.id);
      });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر تحميل الأصول",
        kind: "err",
      });
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    setTimeline([]);
    setSelectedId("");
    setExportAsset(null);
    loadAssets();
  }, [loadAssets]);

  const byId = useMemo(() => new Map(assets.map((asset) => [asset.id, asset])), [assets]);
  const thumbs = useMemo(() => {
    const map = new Map<string, string>();
    assets
      .filter((asset) => asset.kind === "thumbnail" && asset.generation_id)
      .forEach((asset) => {
        if (asset.generation_id && !map.has(asset.generation_id)) {
          map.set(asset.generation_id, asset.url);
        }
      });
    return map;
  }, [assets]);

  const clips = useMemo(
    () =>
      timeline
        .map((id) => byId.get(id))
        .filter((asset): asset is Asset => Boolean(asset)),
    [timeline, byId],
  );

  const available = useMemo(
    () =>
      assets.filter(
        (asset) =>
          (asset.kind === "video" || asset.kind === "export") &&
          !timeline.includes(asset.id),
      ),
    [assets, timeline],
  );

  const selected = useMemo(
    () => clips.find((clip) => clip.id === selectedId) || clips[0] || null,
    [clips, selectedId],
  );

  const totalSeconds = clips.reduce((sum, clip) => sum + (clip.duration_s || 0), 0);

  const move = (index: number, direction: -1 | 1) => {
    setTimeline((current) => {
      const next = [...current];
      const target = index + direction;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const remove = (index: number) => {
    setTimeline((current) => current.filter((_, idx) => idx !== index));
  };

  const addToTimeline = (asset: Asset) => {
    setTimeline((current) => [...current, asset.id]);
    setSelectedId(asset.id);
  };

  const posterFor = (asset: Asset) =>
    asset.generation_id ? thumbs.get(asset.generation_id) : undefined;

  // Resolve the link target from the trusted project list (not the raw <select> value),
  // and encode it so the id can never break out of the query string.
  const currentProject = projects.find((project) => project.id === projectId) ?? null;
  const studioHref = currentProject
    ? `/studio?project=${encodeURIComponent(currentProject.id)}`
    : "/studio";

  const doExport = async () => {
    if (!clips.length) {
      setToast({ message: "أضف مقطعاً واحداً على الأقل", kind: "err" });
      return;
    }
    setExporting(true);
    try {
      const asset = await api.exports.create({
        asset_ids: clips.map((clip) => clip.id),
        aspect_ratio: aspect,
        filename: filename || "final.mp4",
      });
      setExportAsset(asset);
      setAssets((prev) => [asset, ...prev]);
      setToast({ message: "تم التصدير بنجاح", kind: "ok" });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر التصدير",
        kind: "err",
      });
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">timeline</div>
          <h1 className="page-title">المونتاج</h1>
          <p className="page-sub">
            رتّب المشاهد، اضبط المقاس، ثم صدّر ملف MP4 جاهزاً للنشر.
          </p>
        </div>
        <div className="row wrap">
          <select
            className="select"
            style={{ width: 220 }}
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          >
            <option value="">اختر مشروعاً</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          <Link href={studioHref} className="btn">
            <PlusIcon size={16} />
            مشهد جديد
          </Link>
        </div>
      </header>

      {loading ? (
        <div className="skeleton" style={{ height: 380 }} />
      ) : !projectId ? (
        <div className="empty">
          <div className="ring">
            <ScissorsIcon size={26} />
          </div>
          <strong>لا يوجد مشروع للمونتاج</strong>
          <div className="tiny">أنشئ مشروعاً وولّد مشاهد أولاً.</div>
          <Link href="/studio" className="btn btn-primary">
            إلى الاستوديو
          </Link>
        </div>
      ) : (
        <>
          <div className="studio-grid">
            <div className="side-stack">
              <div className="card">
                <div className="card-head">
                  <div className="card-title">
                    <FilmIcon size={16} />
                    معاينة المشهد
                  </div>
                  <span className="badge">{ASPECT_LABELS[aspect]}</span>
                </div>
                <div
                  className={`preview-stage${aspect === "9:16" ? " vertical" : ""}`}
                  style={{ borderRadius: 0, border: 0, aspectRatio: undefined, height: 260 }}
                >
                  {selected ? (
                    <video
                      key={selected.id}
                      src={mediaUrl(selected.url)}
                      poster={posterFor(selected) ? mediaUrl(posterFor(selected)!) : undefined}
                      controls
                      playsInline
                    />
                  ) : (
                    <div className="stage-empty">
                      <div className="ring">
                        <FilmIcon size={24} />
                      </div>
                      <div className="tiny">اختر مقطعاً من التايم لاين</div>
                    </div>
                  )}
                </div>
              </div>

              <div className="card">
                <div className="card-head">
                  <div className="card-title">إعدادات التصدير</div>
                </div>
                <div className="stack" style={{ padding: 16 }}>
                  <div className="field">
                    <label className="label">المقاس النهائي</label>
                    <div className="chips">
                      {Object.entries(ASPECT_LABELS).map(([key, label]) => (
                        <button
                          key={key}
                          className={`chip${aspect === key ? " active" : ""}`}
                          onClick={() => setAspect(key)}
                        >
                          {key}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="field">
                    <label className="label">اسم الملف</label>
                    <input
                      className="input"
                      value={filename}
                      onChange={(event) => setFilename(event.target.value)}
                      maxLength={80}
                    />
                  </div>
                  <div className="row-between tiny muted">
                    <span className="row" style={{ gap: 5 }}>
                      <ClockIcon size={13} /> {formatDuration(totalSeconds)}
                    </span>
                    <span>{clips.length} مقطع</span>
                  </div>
                  <button
                    className="btn btn-primary"
                    onClick={doExport}
                    disabled={exporting || !clips.length}
                    style={{ width: "100%" }}
                  >
                    {exporting ? <span className="spinner" /> : <LayersIcon size={16} />}
                    {exporting ? "جارٍ التصدير…" : "تصدير MP4"}
                  </button>
                  <div className="tiny" style={{ color: "var(--muted-2)" }}>
                    يُعاد ترميز المقاطع لتوحيد المقاس و30 إطاراً/ث. الصوت يُضاف في
                    مرحلة قادمة.
                  </div>
                </div>
              </div>

              {exportAsset ? (
                <div className="card card-pad" style={{ borderColor: "rgba(74,222,128,.35)" }}>
                  <div className="row" style={{ color: "var(--ok)" }}>
                    <CheckIcon size={17} />
                    <strong style={{ fontSize: 13 }}>الملف النهائي جاهز</strong>
                  </div>
                  <div className="tiny muted" style={{ margin: "6px 0 10px" }}>
                    {formatDuration(exportAsset.duration_s)} ·{" "}
                    {(exportAsset.size_bytes / 1024 / 1024).toFixed(1)} م.ب
                  </div>
                  <div className="row">
                    <button className="btn btn-sm" onClick={() => setModalAsset(exportAsset)}>
                      <PlayIcon size={14} />
                      معاينة
                    </button>
                    <a
                      className="btn btn-sm btn-primary"
                      href={mediaUrl(exportAsset.download_url)}
                      download
                      target="_blank"
                      rel="noreferrer"
                    >
                      <DownloadIcon size={14} />
                      تنزيل
                    </a>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="stack">
              <div className="card">
                <div className="card-head">
                  <div className="card-title">
                    <ScissorsIcon size={16} />
                    التايم لاين
                    <span className="count">{clips.length}</span>
                  </div>
                  <span className="tiny muted">{formatDuration(totalSeconds)}</span>
                </div>
                {clips.length ? (
                  <div className="timeline">
                    {clips.map((clip, index) => (
                      <div
                        key={`${clip.id}-${index}`}
                        className="clip"
                        style={{
                          borderColor:
                            selected?.id === clip.id ? "rgba(139,108,255,.5)" : undefined,
                          background:
                            selected?.id === clip.id
                              ? "rgba(139,108,255,.08)"
                              : undefined,
                          cursor: "pointer",
                        }}
                        onClick={() => setSelectedId(clip.id)}
                      >
                        <span
                          className="mono"
                          style={{ color: "var(--muted-2)", width: 20, textAlign: "center" }}
                        >
                          {index + 1}
                        </span>
                        <div className="clip-thumb">
                          {posterFor(clip) ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={mediaUrl(posterFor(clip)!)} alt="" />
                          ) : (
                            <video src={mediaUrl(clip.url)} muted preload="metadata" />
                          )}
                        </div>
                        <div className="clip-body">
                          <div className="clip-title">
                            {clip.kind === "export" ? "ملف مصدّر" : "مشهد مولّد"}
                          </div>
                          <div className="clip-meta">
                            {formatDuration(clip.duration_s)} · {clip.id.slice(-6)}
                          </div>
                        </div>
                        <div className="clip-actions" onClick={(event) => event.stopPropagation()}>
                          <button
                            className="btn-icon"
                            style={{ width: 28, height: 28 }}
                            onClick={() => move(index, -1)}
                            disabled={index === 0}
                            title="أعلى"
                          >
                            ↑
                          </button>
                          <button
                            className="btn-icon"
                            style={{ width: 28, height: 28 }}
                            onClick={() => move(index, 1)}
                            disabled={index === clips.length - 1}
                            title="أسفل"
                          >
                            ↓
                          </button>
                          <button
                            className="btn-icon danger"
                            style={{ width: 28, height: 28 }}
                            onClick={() => remove(index)}
                            title="إزالة"
                          >
                            <TrashIcon size={12} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty" style={{ margin: 12 }}>
                    <div className="tiny">التايم لاين فارغ — أضف مقاطع من الأسفل.</div>
                  </div>
                )}
              </div>

              <div className="card">
                <div className="card-head">
                  <div className="card-title">
                    <PlusIcon size={16} />
                    مقاطع متاحة
                    <span className="count">{available.length}</span>
                  </div>
                  <Link href="/library" className="btn btn-sm btn-ghost">
                    المكتبة
                    <ArrowLeftIcon size={14} />
                  </Link>
                </div>
                {available.length ? (
                  <div className="asset-grid" style={{ padding: 12 }}>
                    {available.map((asset) => (
                      <div key={asset.id} className="asset-card">
                        <div
                          className="asset-thumb"
                          style={{ aspectRatio: "16/9" }}
                          onClick={() => addToTimeline(asset)}
                        >
                          {posterFor(asset) ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={mediaUrl(posterFor(asset)!)} alt="" loading="lazy" />
                          ) : (
                            <video src={mediaUrl(asset.url)} muted preload="metadata" />
                          )}
                          <div className="asset-play">
                            <PlusIcon size={16} />
                          </div>
                        </div>
                        <div className="asset-info">
                          <div className="asset-title">
                            {formatDuration(asset.duration_s)} · {asset.kind}
                          </div>
                          <button
                            className="btn btn-sm"
                            onClick={() => addToTimeline(asset)}
                          >
                            إضافة
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty" style={{ margin: 12 }}>
                    <UploadIcon size={20} />
                    <div className="tiny">كل المقاطع في التايم لاين. ولّد المزيد من الاستوديو.</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      <VideoModal asset={modalAsset} onClose={() => setModalAsset(null)} />
      <Toast state={toast} onClose={() => setToast(null)} />
    </>
  );
}

export default function EditorPage() {
  return (
    <Suspense fallback={<div className="skeleton" style={{ height: 420 }} />}>
      <EditorInner />
    </Suspense>
  );
}
