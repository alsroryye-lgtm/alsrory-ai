"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, mediaUrl } from "@/lib/api";
import type { Asset, Project } from "@/lib/types";
import { formatBytes, formatDuration, timeAgo } from "@/lib/utils";
import { Toast, type ToastState } from "@/components/Toast";
import { VideoModal } from "@/components/VideoModal";
import {
  DownloadIcon,
  FilmIcon,
  LibraryIcon,
  PlayIcon,
  PlusIcon,
  ScissorsIcon,
  TrashIcon,
  UploadIcon,
} from "@/components/icons";

const FILTERS = [
  { id: "", label: "الكل" },
  { id: "video", label: "فيديو" },
  { id: "image", label: "صور" },
  { id: "audio", label: "صوت" },
  { id: "export", label: "تصدير" },
];

export default function LibraryPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [filter, setFilter] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalAsset, setModalAsset] = useState<Asset | null>(null);
  const [toast, setToast] = useState<ToastState>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadProjects = useCallback(async () => {
    try {
      const list = await api.projects.list();
      setProjects(list);
      setProjectId((current) => current || list[0]?.id || "");
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر تحميل المشاريع",
        kind: "err",
      });
    }
  }, []);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.assets.list(projectId || undefined, filter || undefined, 200);
      setAssets(list.filter((item) => item.kind !== "thumbnail"));
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر تحميل المكتبة",
        kind: "err",
      });
    } finally {
      setLoading(false);
    }
  }, [projectId, filter]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  const stats = useMemo(() => {
    const videos = assets.filter((a) => a.kind === "video" || a.kind === "export");
    return {
      count: assets.length,
      videos: videos.length,
      bytes: assets.reduce((sum, a) => sum + a.size_bytes, 0),
      seconds: videos.reduce((sum, a) => sum + (a.duration_s || 0), 0),
    };
  }, [assets]);

  const remove = async (asset: Asset) => {
    if (!window.confirm("حذف هذا الأصل نهائياً من القرص؟")) return;
    try {
      await api.assets.remove(asset.id);
      setAssets((prev) => prev.filter((item) => item.id !== asset.id));
      setToast({ message: "حُذف الأصل", kind: "ok" });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر الحذف",
        kind: "err",
      });
    }
  };

  const upload = async (file: File) => {
    if (!projectId) {
      setToast({ message: "أنشئ مشروعاً أولاً", kind: "err" });
      return;
    }
    setUploading(true);
    try {
      const kind = file.type.startsWith("video")
        ? "video"
        : file.type.startsWith("audio")
          ? "audio"
          : "image";
      await api.assets.upload(projectId, file, kind);
      setToast({ message: "رُفع الملف إلى المكتبة", kind: "ok" });
      loadAssets();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر رفع الملف",
        kind: "err",
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">library</div>
          <h1 className="page-title">المكتبة</h1>
          <p className="page-sub">
            كل ما ولّدته أو رفعته، في مكان واحد. عاين، نزّل، أو أرسل المشهد إلى
            المونتاج.
          </p>
        </div>
        <div className="row wrap">
          <select
            className="select"
            style={{ width: 220 }}
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          >
            <option value="">كل المشاريع</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          <input
            ref={fileRef}
            type="file"
            hidden
            accept="video/*,image/*,audio/*"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload(file);
              event.target.value = "";
            }}
          />
          <button
            className="btn btn-primary"
            onClick={() => fileRef.current?.click()}
            disabled={uploading || !projectId}
          >
            {uploading ? <span className="spinner" /> : <UploadIcon size={16} />}
            رفع ملف
          </button>
          <Link href="/studio" className="btn">
            <PlusIcon size={16} />
            توليد جديد
          </Link>
        </div>
      </header>

      <div className="stat-grid">
        <div className="stat">
          <div className="stat-label">
            <LibraryIcon size={14} /> الأصول
          </div>
          <div className="stat-value">{stats.count}</div>
        </div>
        <div className="stat">
          <div className="stat-label">
            <FilmIcon size={14} /> مقاطع
          </div>
          <div className="stat-value">{stats.videos}</div>
        </div>
        <div className="stat">
          <div className="stat-label">
            <PlayIcon size={14} /> إجمالي المدة
          </div>
          <div className="stat-value" style={{ fontSize: 20 }}>
            {formatDuration(stats.seconds)}
          </div>
        </div>
        <div className="stat">
          <div className="stat-label">
            <DownloadIcon size={14} /> الحجم
          </div>
          <div className="stat-value" style={{ fontSize: 20 }}>
            {formatBytes(stats.bytes)}
          </div>
        </div>
      </div>

      <div className="section-head" style={{ marginTop: 22 }}>
        <div className="chips">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              className={`chip${filter === item.id ? " active" : ""}`}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <span className="tiny muted">{assets.length} نتيجة</span>
      </div>

      {loading ? (
        <div className="asset-grid">
          {[1, 2, 3, 4, 5, 6].map((key) => (
            <div key={key} className="skeleton" style={{ height: 190 }} />
          ))}
        </div>
      ) : assets.length ? (
        <div className="asset-grid">
          {assets.map((asset) => {
            const isVideo = asset.mime.startsWith("video/") || asset.kind === "export";
            const isImage = asset.mime.startsWith("image/");
            const isAudio = asset.mime.startsWith("audio/");
            return (
              <div key={asset.id} className="asset-card">
                <div className="asset-thumb" onClick={() => setModalAsset(asset)}>
                  {isVideo ? (
                    <video
                      src={mediaUrl(asset.url)}
                      muted
                      loop
                      playsInline
                      preload="metadata"
                      onMouseEnter={(event) => event.currentTarget.play().catch(() => {})}
                      onMouseLeave={(event) => {
                        event.currentTarget.pause();
                        event.currentTarget.currentTime = 0;
                      }}
                    />
                  ) : isImage ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={mediaUrl(asset.url)} alt="" loading="lazy" />
                  ) : (
                    <div
                      style={{
                        height: "100%",
                        display: "grid",
                        placeItems: "center",
                        color: "var(--muted-2)",
                      }}
                    >
                      <LibraryIcon size={30} />
                    </div>
                  )}
                  {isVideo || isAudio ? (
                    <div className="asset-play">
                      <PlayIcon size={16} />
                    </div>
                  ) : null}
                  <span className="asset-chip">{asset.kind.toUpperCase()}</span>
                </div>
                <div className="asset-info">
                  <div style={{ minWidth: 0 }}>
                    <div className="asset-title">
                      {formatDuration(asset.duration_s)} · {timeAgo(asset.created_at)}
                    </div>
                    <div className="tiny" style={{ color: "var(--muted-2)" }}>
                      {formatBytes(asset.size_bytes)}
                    </div>
                  </div>
                  <div className="asset-actions">
                    <a
                      className="btn-icon"
                      style={{ width: 28, height: 28 }}
                      href={mediaUrl(asset.download_url)}
                      download
                      target="_blank"
                      rel="noreferrer"
                      title="تنزيل"
                    >
                      <DownloadIcon size={13} />
                    </a>
                    <button
                      className="btn-icon danger"
                      style={{ width: 28, height: 28 }}
                      onClick={() => remove(asset)}
                      title="حذف"
                    >
                      <TrashIcon size={13} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="empty">
          <div className="ring">
            <LibraryIcon size={26} />
          </div>
          <strong>المكتبة فارغة</strong>
          <div className="tiny">ولّد مشهداً من الاستوديو أو ارفع ملفاً للبدء.</div>
          <div className="row">
            <Link href="/studio" className="btn btn-primary">
              <FilmIcon size={16} />
              إلى الاستوديو
            </Link>
            <Link href="/editor" className="btn">
              <ScissorsIcon size={16} />
              المونتاج
            </Link>
          </div>
        </div>
      )}

      <VideoModal asset={modalAsset} onClose={() => setModalAsset(null)} />
      <Toast state={toast} onClose={() => setToast(null)} />
    </>
  );
}
