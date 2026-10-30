"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api, eventsUrl, mediaUrl } from "@/lib/api";
import type {
  Asset,
  EngineInfo,
  Generation,
  Project,
} from "@/lib/types";
import {
  ASPECT_LABELS,
  ASPECT_SIZES,
  STATUS_LABELS,
  STYLE_PRESETS,
  formatDuration,
  timeAgo,
} from "@/lib/utils";
import { ProjectCreateModal } from "@/components/ProjectCreateModal";
import { Toast, type ToastState } from "@/components/Toast";
import { VideoModal } from "@/components/VideoModal";
import {
  AlertIcon,
  CheckIcon,
  ClockIcon,
  FilmIcon,
  PlayIcon,
  PlusIcon,
  SparklesIcon,
  UploadIcon,
  WandIcon,
} from "@/components/icons";

const MODES = [
  { id: "text2video", label: "نص → فيديو", ready: true },
  { id: "image2video", label: "صورة → فيديو", ready: true },
  { id: "avatar", label: "أفاتار", ready: false },
] as const;

function StudioInner() {
  const params = useSearchParams();
  const queryProject = params.get("project") || "";
  const queryPrompt = params.get("prompt") || "";

  const [projects, setProjects] = useState<Project[]>([]);
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [projectId, setProjectId] = useState("");
  const [mode, setMode] = useState<string>("text2video");
  const [prompt, setPrompt] = useState(queryPrompt);
  const [negative, setNegative] = useState("");
  const [aspect, setAspect] = useState("16:9");
  const [seconds, setSeconds] = useState(4);
  const [fps, setFps] = useState(24);
  const [seed, setSeed] = useState("");
  const [style, setStyle] = useState("cinematic");
  const [engineId, setEngineId] = useState("");
  const [imageAsset, setImageAsset] = useState<Asset | null>(null);
  const [imageBusy, setImageBusy] = useState(false);
  const [tips, setTips] = useState<string[]>([]);
  const [enhancing, setEnhancing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [active, setActive] = useState<Generation | null>(null);
  const [takes, setTakes] = useState<Asset[]>([]);
  const [selected, setSelected] = useState<Asset | null>(null);
  const [modalAsset, setModalAsset] = useState<Asset | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [loading, setLoading] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const project = useMemo(
    () => projects.find((item) => item.id === projectId),
    [projects, projectId],
  );

  const loadProjects = useCallback(async () => {
    try {
      const [list, engineList] = await Promise.all([
        api.projects.list(),
        api.engines.list(),
      ]);
      setProjects(list);
      setEngines(engineList);
      const target =
        list.find((item) => item.id === queryProject)?.id || list[0]?.id || "";
      setProjectId((current) => current || target);
      if (target) {
        const current = list.find((item) => item.id === target);
        if (current) {
          setAspect(current.aspect_ratio);
          setStyle(current.style_preset || "cinematic");
        }
      }
      setEngineId(
        (current) => current || engineList.find((item) => item.is_default)?.id || "mock",
      );
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر تحميل المشاريع",
        kind: "err",
      });
    } finally {
      setLoading(false);
    }
  }, [queryProject]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const loadTakes = useCallback(async () => {
    if (!projectId) {
      setTakes([]);
      return;
    }
    try {
      const assets = await api.assets.list(projectId, "video", 24);
      setTakes(assets);
      setSelected((current) => current || assets[0] || null);
    } catch {
      /* silent */
    }
  }, [projectId]);

  useEffect(() => {
    if (project) {
      setAspect(project.aspect_ratio);
      setStyle(project.style_preset || "cinematic");
    }
  }, [project]);

  useEffect(() => {
    setSelected(null);
    loadTakes();
  }, [loadTakes]);

  // Live progress over SSE, with a polling fallback.
  useEffect(() => {
    if (!active) return;
    if (!["queued", "running", "postprocessing"].includes(active.status)) return;

    let closed = false;
    const source = new EventSource(eventsUrl(active.id));

    const handle = (event: MessageEvent) => {
      if (closed) return;
      try {
        const data = JSON.parse(event.data) as Generation;
        if (data && data.id) {
          setActive(data);
        }
      } catch {
        /* ignore malformed frame */
      }
    };

    source.addEventListener("progress", handle as EventListener);
    source.onmessage = handle;
    source.addEventListener("done", () => {
      source.close();
      setGenerating(false);
      loadTakes();
    });
    source.onerror = () => {
      source.close();
      if (!closed) {
        // Fallback: poll once every 2 seconds until terminal.
        const timer = setInterval(async () => {
          try {
            const fresh = await api.generations.get(active.id);
            setActive(fresh);
            if (["completed", "failed", "canceled"].includes(fresh.status)) {
              clearInterval(timer);
              setGenerating(false);
              loadTakes();
            }
          } catch {
            /* keep trying */
          }
        }, 2000);
        setTimeout(() => clearInterval(timer), 30 * 60 * 1000);
      }
    };

    return () => {
      closed = true;
      source.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.id]);

  useEffect(() => {
    if (active && ["completed", "failed", "canceled"].includes(active.status)) {
      setGenerating(false);
      loadTakes();
    }
  }, [active, loadTakes]);

  const enhance = async () => {
    if (!prompt.trim()) {
      setToast({ message: "اكتب وصفاً أولاً ثم حسّنه", kind: "err" });
      return;
    }
    setEnhancing(true);
    try {
      const result = await api.prompts.enhance(prompt, style);
      setPrompt(result.prompt);
      if (!negative) setNegative(result.negative_prompt);
      setTips(result.tips);
      setToast({ message: "حُسّن الوصف", kind: "ok" });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر تحسين الوصف",
        kind: "err",
      });
    } finally {
      setEnhancing(false);
    }
  };

  const uploadImage = async (file: File) => {
    if (!projectId) {
      setToast({ message: "اختر مشروعاً أولاً", kind: "err" });
      return;
    }
    setImageBusy(true);
    try {
      const asset = await api.assets.upload(projectId, file, "image");
      setImageAsset(asset);
      setMode("image2video");
      setToast({ message: "رُفعت الصورة المرجعية", kind: "ok" });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر رفع الصورة",
        kind: "err",
      });
    } finally {
      setImageBusy(false);
    }
  };

  const generate = async () => {
    if (!projectId) {
      setCreateOpen(true);
      return;
    }
    if (!prompt.trim() && mode !== "image2video") {
      setToast({ message: "اكتب وصف المشهد", kind: "err" });
      return;
    }
    if (mode === "image2video" && !imageAsset) {
      setToast({ message: "ارفع صورة مرجعية أولاً", kind: "err" });
      return;
    }

    setGenerating(true);
    setTips([]);
    try {
      const [width, height] = ASPECT_SIZES[aspect] || [832, 480];
      const generation = await api.generations.create({
        project_id: projectId,
        type: mode,
        prompt: prompt.trim(),
        negative_prompt: negative.trim(),
        engine_id: engineId || undefined,
        params: {
          width,
          height,
          seconds,
          fps,
          aspect_ratio: aspect,
          seed: seed.trim() ? Number(seed) : null,
          style_preset: style,
          image_asset_id: imageAsset?.id || null,
        },
      });
      setActive(generation);
      setToast({ message: "أُضيفت المهمة إلى الطابور", kind: "ok" });
    } catch (err) {
      setGenerating(false);
      setToast({
        message: err instanceof Error ? err.message : "تعذّر بدء التوليد",
        kind: "err",
      });
    }
  };

  const cancel = async () => {
    if (!active) return;
    try {
      await api.generations.cancel(active.id);
      setGenerating(false);
      setToast({ message: "أُلغيت المهمة", kind: "ok" });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر الإلغاء",
        kind: "err",
      });
    }
  };

  const retry = async () => {
    if (!active) return;
    try {
      const fresh = await api.generations.retry(active.id);
      setActive(fresh);
      setGenerating(true);
      setToast({ message: "أُعيدت المهمة إلى الطابور", kind: "ok" });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّرت إعادة المحاولة",
        kind: "err",
      });
    }
  };

  const activeVideo = active?.assets?.find(
    (asset) => asset.kind === "video" || asset.kind === "export",
  );
  const previewAsset = activeVideo || selected;
  const running =
    active && ["queued", "running", "postprocessing"].includes(active.status);

  const onCreated = (created: Project) => {
    setProjects((prev) => [created, ...prev]);
    setProjectId(created.id);
    setAspect(created.aspect_ratio);
  };

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">studio</div>
          <h1 className="page-title">الاستوديو</h1>
          <p className="page-sub">
            اكتب المشهد، اختر الإعدادات، وراقب التوليد لحظة بلحظة. كل نسخة تُحفظ
            في مكتبة المشروع.
          </p>
        </div>
        <div className="row wrap">
          <select
            className="select"
            style={{ width: 220 }}
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            disabled={!projects.length}
          >
            {projects.length ? (
              projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))
            ) : (
              <option value="">لا توجد مشاريع</option>
            )}
          </select>
          <button className="btn" onClick={() => setCreateOpen(true)}>
            <PlusIcon size={16} />
            مشروع
          </button>
        </div>
      </header>

      {!loading && !projects.length ? (
        <div className="empty">
          <div className="ring">
            <FilmIcon size={26} />
          </div>
          <strong>ابدأ بمشروع</strong>
          <div className="tiny">المشروع يجمع المشاهد والإعدادات والأصول.</div>
          <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
            <PlusIcon size={16} />
            إنشاء مشروع
          </button>
        </div>
      ) : (
        <div className="studio-grid">
          <div className="side-stack">
            <div className="card">
              <div className="card-head">
                <div className="card-title">
                  <SparklesIcon size={16} />
                  وصف المشهد
                </div>
                <button className="btn btn-sm btn-soft" onClick={enhance} disabled={enhancing}>
                  {enhancing ? <span className="spinner" /> : <WandIcon size={14} />}
                  حسّن
                </button>
              </div>
              <div className="stack" style={{ padding: 16 }}>
                <div className="seg">
                  {MODES.map((item) => (
                    <button
                      key={item.id}
                      className={mode === item.id ? "active" : ""}
                      onClick={() => {
                        if (!item.ready) {
                          setToast({ message: "الأفاتار على خارطة الطريق — قريباً", kind: "err" });
                          return;
                        }
                        setMode(item.id);
                      }}
                      type="button"
                    >
                      {item.label}
                      {!item.ready ? " · قريباً" : ""}
                    </button>
                  ))}
                </div>

                <textarea
                  className="textarea"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="صف المشهد: المكان، الشخصيات، الحركة، الإضاءة، المزاج…"
                  maxLength={4000}
                  style={{ minHeight: 120 }}
                />

                {mode === "image2video" ? (
                  <div className="field">
                    <label className="label">
                      الصورة المرجعية <span className="hint">أول إطار</span>
                    </label>
                    <div className="row">
                      <input
                        ref={fileRef}
                        type="file"
                        accept="image/*"
                        hidden
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) uploadImage(file);
                        }}
                      />
                      <button
                        className="btn grow"
                        onClick={() => fileRef.current?.click()}
                        disabled={imageBusy}
                        type="button"
                      >
                        {imageBusy ? <span className="spinner" /> : <UploadIcon size={15} />}
                        {imageAsset ? "تغيير الصورة" : "رفع صورة"}
                      </button>
                      {imageAsset ? (
                        <div
                          style={{
                            width: 54,
                            height: 40,
                            borderRadius: 8,
                            overflow: "hidden",
                            border: "1px solid var(--line)",
                            flex: "none",
                          }}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={mediaUrl(imageAsset.url)}
                            alt=""
                            style={{ width: "100%", height: "100%", objectFit: "cover" }}
                          />
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                <div className="chips">
                  {STYLE_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      className={`chip${style === preset.id ? " active" : ""}`}
                      onClick={() => setStyle(preset.id)}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>

                <details
                  className="tiny"
                  style={{ color: "var(--muted)" }}
                  open={advanced}
                  onToggle={(event) =>
                    setAdvanced((event.target as HTMLDetailsElement).open)
                  }
                >
                  <summary style={{ cursor: "pointer", fontWeight: 650 }}>
                    الوصف السلبي (ما لا تريده)
                  </summary>
                  <textarea
                    className="textarea"
                    style={{ minHeight: 64, marginTop: 8 }}
                    value={negative}
                    onChange={(event) => setNegative(event.target.value)}
                    placeholder="تشويه، نص، علامة مائية…"
                    maxLength={2000}
                  />
                </details>

                {tips.length ? (
                  <div className="tips">
                    {tips.map((tip) => (
                      <div key={tip} className="row" style={{ alignItems: "flex-start", gap: 6 }}>
                        <span style={{ color: "var(--gold)", flex: "none" }}>•</span>
                        <span>{tip}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <div className="card-title">إعدادات التوليد</div>
                <span className="badge">{ASPECT_LABELS[aspect]}</span>
              </div>
              <div className="stack" style={{ padding: 16 }}>
                <div className="field">
                  <label className="label">نسبة العرض</label>
                  <div className="chips">
                    {Object.keys(ASPECT_LABELS).map((key) => (
                      <button
                        key={key}
                        type="button"
                        className={`chip${aspect === key ? " active" : ""}`}
                        onClick={() => setAspect(key)}
                      >
                        {key}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="field">
                  <label className="label">
                    المدة
                    <span className="hint">{seconds} ثانية</span>
                  </label>
                  <input
                    className="range"
                    type="range"
                    min={2}
                    max={10}
                    step={1}
                    value={seconds}
                    onChange={(event) => setSeconds(Number(event.target.value))}
                  />
                </div>

                <div className="grid-2">
                  <div className="field">
                    <label className="label">الإطارات/ث</label>
                    <select
                      className="select"
                      value={fps}
                      onChange={(event) => setFps(Number(event.target.value))}
                    >
                      <option value={16}>16</option>
                      <option value={24}>24</option>
                      <option value={30}>30</option>
                    </select>
                  </div>
                  <div className="field">
                    <label className="label">البذرة</label>
                    <div className="row" style={{ gap: 6 }}>
                      <input
                        className="input"
                        value={seed}
                        onChange={(event) =>
                          setSeed(event.target.value.replace(/[^0-9]/g, ""))
                        }
                        placeholder="عشوائي"
                        inputMode="numeric"
                      />
                      <button
                        type="button"
                        className="btn-icon"
                        title="بذرة عشوائية"
                        onClick={() => setSeed(String(Math.floor(Math.random() * 2 ** 31)))}
                      >
                        <WandIcon size={15} />
                      </button>
                    </div>
                  </div>
                </div>

                <div className="field">
                  <label className="label">المحرّك</label>
                  <select
                    className="select"
                    value={engineId}
                    onChange={(event) => setEngineId(event.target.value)}
                  >
                    {engines.map((engine) => (
                      <option key={engine.id} value={engine.id}>
                        {engine.label}
                        {engine.is_default ? " (افتراضي)" : ""}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  className="btn btn-primary btn-lg"
                  onClick={generate}
                  disabled={generating}
                  style={{ width: "100%" }}
                >
                  {generating ? <span className="spinner" /> : <PlayIcon size={17} />}
                  {generating ? "جارٍ التوليد…" : "ولّد المشهد"}
                </button>
                <div className="tiny" style={{ color: "var(--muted-2)", textAlign: "center" }}>
                  {ASPECT_SIZES[aspect]?.join("×")} · {seconds} ث · {fps} إطار/ث
                </div>
              </div>
            </div>
          </div>

          <div className="stack" style={{ gap: 14 }}>
            <div className={`preview-stage${aspect === "9:16" ? " vertical" : ""}`}>
              {previewAsset ? (
                <>
                  <video
                    key={previewAsset.id}
                    src={mediaUrl(previewAsset.url)}
                    controls
                    autoPlay
                    loop
                    muted
                    playsInline
                  />
                  <div className="stage-overlay">
                    <div className="row" style={{ gap: 8 }}>
                      <span className="stage-badge">{previewAsset.kind.toUpperCase()}</span>
                      <span className="tiny" style={{ color: "#d6d6e2" }}>
                        {formatDuration(previewAsset.duration_s)}
                        {previewAsset.width && previewAsset.height
                          ? ` · ${previewAsset.width}×${previewAsset.height}`
                          : ""}
                      </span>
                    </div>
                    <button
                      className="btn btn-sm"
                      onClick={() => setModalAsset(previewAsset)}
                    >
                      تكبير
                    </button>
                  </div>
                </>
              ) : (
                <div className="stage-empty">
                  <div className="ring">
                    <FilmIcon size={28} />
                  </div>
                  <div>
                    <strong style={{ color: "var(--text)", fontSize: 14 }}>لا يوجد مشهد بعد</strong>
                    <div className="tiny" style={{ marginTop: 4 }}>
                      اكتب وصفاً واضغط «ولّد المشهد» — سيظهر الناتج هنا.
                    </div>
                  </div>
                </div>
              )}
            </div>

            {active ? (
              <div className="card job-card">
                <div className="job-top">
                  <div className={`job-status ${active.status}`}>
                    {active.status === "completed" ? (
                      <CheckIcon size={15} />
                    ) : active.status === "failed" ? (
                      <AlertIcon size={15} />
                    ) : active.status === "queued" ? (
                      <ClockIcon size={15} />
                    ) : (
                      <span className="spinner" />
                    )}
                    {STATUS_LABELS[active.status] || active.status}
                  </div>
                  <div className="row" style={{ gap: 6 }}>
                    <span className="tiny muted mono">{active.id}</span>
                    {running ? (
                      <button className="btn btn-sm btn-danger" onClick={cancel}>
                        إلغاء
                      </button>
                    ) : active.status === "failed" ? (
                      <button className="btn btn-sm" onClick={retry}>
                        إعادة المحاولة
                      </button>
                    ) : (
                      <button className="btn btn-sm" onClick={() => setActive(null)}>
                        مسح
                      </button>
                    )}
                  </div>
                </div>
                <div className="bar">
                  <div
                    className="bar-fill"
                    style={{ width: `${Math.max(3, Math.round(active.progress * 100))}%` }}
                  />
                </div>
                <div className="row-between tiny" style={{ color: "var(--muted)" }}>
                  <span>{Math.round(active.progress * 100)}%</span>
                  <span>
                    {active.engine_id} · {active.type}
                    {active.seed ? ` · بذرة ${active.seed}` : ""}
                  </span>
                  <span>{timeAgo(active.created_at)}</span>
                </div>
                {active.error_detail ? (
                  <div
                    className="tiny"
                    style={{
                      color: "#ffb1b1",
                      background: "rgba(255,107,107,.07)",
                      border: "1px solid rgba(255,107,107,.2)",
                      borderRadius: 10,
                      padding: "8px 10px",
                    }}
                  >
                    <strong>{active.error_stage}: </strong>
                    {active.error_detail}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="card">
              <div className="card-head">
                <div className="card-title">
                  <FilmIcon size={16} />
                  نسخ هذا المشروع
                  <span className="count">{takes.length}</span>
                </div>
                <Link href="/library" className="btn btn-sm btn-ghost">
                  المكتبة
                </Link>
              </div>
              {takes.length ? (
                <div className="asset-grid" style={{ padding: 12 }}>
                  {takes.map((asset) => (
                    <div
                      key={asset.id}
                      className="asset-card"
                      style={{
                        borderColor:
                          selected?.id === asset.id ? "rgba(139,108,255,.55)" : undefined,
                      }}
                    >
                      <div className="asset-thumb" onClick={() => setSelected(asset)}>
                        <video
                          src={mediaUrl(asset.url)}
                          muted
                          loop
                          playsInline
                          onMouseEnter={(event) => event.currentTarget.play().catch(() => {})}
                          onMouseLeave={(event) => {
                            event.currentTarget.pause();
                            event.currentTarget.currentTime = 0;
                          }}
                        />
                        <div className="asset-play">
                          <PlayIcon size={16} />
                        </div>
                        <span className="asset-chip">TAKE</span>
                      </div>
                      <div className="asset-info">
                        <div className="asset-title">
                          {formatDuration(asset.duration_s)} · {timeAgo(asset.created_at)}
                        </div>
                        <button
                          className="btn-icon"
                          style={{ width: 26, height: 26 }}
                          onClick={() => setModalAsset(asset)}
                          aria-label="عرض"
                        >
                          <PlayIcon size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty" style={{ margin: 12, padding: 30 }}>
                  <div className="tiny">ستظهر هنا كل النسخ المكتملة لهذا المشروع.</div>
                </div>
              )}
            </div>

            <div className="card card-pad">
              <div className="row" style={{ color: "var(--muted)" }}>
                <AlertIcon size={17} style={{ color: "var(--gold)" }} />
                <div className="tiny grow">
                  <strong style={{ color: "var(--text)" }}>نصيحة:</strong> ابدأ بمقطع 3–5
                  ثوانٍ للاختبار، ثم أعد التوليد بنفس البذرة بعد ضبط الوصف. المقاطع
                  القصيرة تُجمع في المونتاج.
                </div>
                <Link href="/editor" className="btn btn-sm">
                  المونتاج
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      <ProjectCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={onCreated}
      />
      <VideoModal asset={modalAsset} onClose={() => setModalAsset(null)} />
      <Toast state={toast} onClose={() => setToast(null)} />
    </>
  );
}

export default function StudioPage() {
  return (
    <Suspense fallback={<div className="skeleton" style={{ height: 420 }} />}>
      <StudioInner />
    </Suspense>
  );
}
