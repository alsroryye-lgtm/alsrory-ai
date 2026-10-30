"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, mediaUrl } from "@/lib/api";
import type { Health, Project } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { ProjectCreateModal } from "@/components/ProjectCreateModal";
import { Toast, type ToastState } from "@/components/Toast";
import {
  ArrowLeftIcon,
  ClockIcon,
  CpuIcon,
  FilmIcon,
  LayersIcon,
  PlayIcon,
  PlusIcon,
  SparklesIcon,
  TrashIcon,
  WandIcon,
} from "@/components/icons";

const FEATURES = [
  {
    title: "نص → فيديو",
    desc: "اكتب المشهد بالعربية، واختر النسبة والمدة والبذرة. المسودة السريعة ثم نسخة نهائية.",
    badge: "متاح",
    tone: "ok",
    icon: SparklesIcon,
  },
  {
    title: "صورة → فيديو",
    desc: "حرّك صورة ثابتة مع التحكم بشدة الحركة. يحتاج Workflow مناسب في المحرّك.",
    badge: "جاهز للمحرّك",
    tone: "brand",
    icon: FilmIcon,
  },
  {
    title: "أفاتار وصوت",
    desc: "تعليق صوتي عربي، مزامنة شفاه، وموسيقى خلفية — على خارطة الطريق القريبة.",
    badge: "قريباً",
    tone: "",
    icon: WandIcon,
  },
  {
    title: "مونتاج وتصدير",
    desc: "رتّب المشاهد، اقصص، وصدّر MP4 جاهزاً للمنصات من داخل التطبيق.",
    badge: "أساسي",
    tone: "brand",
    icon: LayersIcon,
  },
];

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [videos, setVideos] = useState(0);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [pendingPrompt, setPendingPrompt] = useState("");
  const [toast, setToast] = useState<ToastState>(null);
  const [offline, setOffline] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [projectList, healthData, assets] = await Promise.all([
        api.projects.list(),
        api.health(),
        api.assets.list(undefined, "video", 200).catch(() => []),
      ]);
      setProjects(projectList);
      setHealth(healthData);
      setVideos(assets.length);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const totals = useMemo(
    () => ({
      projects: projects.length,
      videos,
      pending: health?.pending_jobs ?? 0,
      duration: 0,
    }),
    [projects, videos, health],
  );

  const startPrompt = () => {
    const text = prompt.trim();
    if (!text) {
      setToast({ message: "اكتب وصفاً للمشهد أولاً", kind: "err" });
      return;
    }
    if (!projects.length) {
      setPendingPrompt(text);
      setModalOpen(true);
      return;
    }
    router.push(`/studio?project=${projects[0].id}&prompt=${encodeURIComponent(text)}`);
  };

  const onCreated = (project: Project) => {
    setProjects((prev) => [project, ...prev]);
    const text = pendingPrompt || prompt;
    router.push(
      `/studio?project=${project.id}${text ? `&prompt=${encodeURIComponent(text)}` : ""}`,
    );
  };

  const removeProject = async (project: Project) => {
    if (!window.confirm(`حذف «${project.name}» وكل مشاهده نهائياً؟`)) return;
    try {
      await api.projects.remove(project.id);
      setProjects((prev) => prev.filter((item) => item.id !== project.id));
      setToast({ message: "حُذف المشروع", kind: "ok" });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر حذف المشروع",
        kind: "err",
      });
    }
  };

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">alsrory studio</div>
          <h1 className="page-title">حوّل فكرتك إلى فيديو</h1>
          <p className="page-sub">
            استوديو محلي مفتوح المصدر: نماذج فيديو مفتوحة، تحكّم كامل، ولا اشتراكات.
            ابدأ بمشهد قصير ثم اجمع مشاهده في المونتاج.
          </p>
        </div>
        <div className="row wrap">
          <Link href="/library" className="btn btn-ghost">
            <FilmIcon size={16} />
            المكتبة
          </Link>
          <button className="btn btn-primary" onClick={() => setModalOpen(true)}>
            <PlusIcon size={17} />
            مشروع جديد
          </button>
        </div>
      </header>

      {offline ? (
        <div
          className="card card-pad"
          style={{
            marginBottom: 16,
            borderColor: "rgba(255,107,107,.3)",
            background: "rgba(255,107,107,.06)",
          }}
        >
          <div className="row" style={{ color: "#ffc0c0" }}>
            <CpuIcon size={18} />
            <div className="grow">
              <strong style={{ fontSize: 13.5 }}>خادم alsrory.AI لا يستجيب</strong>
              <div className="tiny muted">
                شغّل <span className="mono">.\\scripts\\run.ps1</span> ثم أعد تحميل الصفحة.
              </div>
            </div>
            <button className="btn btn-sm" onClick={load}>
              إعادة المحاولة
            </button>
          </div>
        </div>
      ) : null}

      <section className="hero">
        <div className="hero-copy">
          <span className="badge brand">
            <SparklesIcon size={12} />
            محرّك مفتوح · قابل للتبديل
          </span>
          <h1>
            من فكرة إلى <em>مشهد سينمائي</em>
            <br />
            في دقائق.
          </h1>
          <p>
            اكتب الوصف، اختر النسبة والمدة، ودع المحرّك يرسم الحركة. كل نسخة محفوظة
            ببذرتها وإعداداتها، وكل مشهد جاهز للمونتاج.
          </p>
          <div className="hero-actions">
            <Link href="/studio" className="btn btn-primary btn-lg">
              <PlayIcon size={17} />
              افتح الاستوديو
            </Link>
            <Link href="/settings" className="btn btn-lg">
              <CpuIcon size={17} />
              إعداد المحرّك
            </Link>
          </div>
        </div>
        <div className="hero-art" aria-hidden>
          <div className="orb one" />
          <div className="orb two" />
          <div className="orb three" />
          <div className="play-orb">
            <PlayIcon size={34} />
          </div>
          <span className="hero-badge">LATENT MOTION · 24FPS</span>
        </div>
      </section>

      <div className="stat-grid">
        <div className="stat">
          <div className="stat-label">
            <LayersIcon size={14} /> المشاريع
          </div>
          <div className="stat-value">{loading ? "—" : totals.projects}</div>
        </div>
        <div className="stat">
          <div className="stat-label">
            <FilmIcon size={14} /> المقاطع المولّدة
          </div>
          <div className="stat-value">{loading ? "—" : totals.videos}</div>
        </div>
        <div className="stat">
          <div className="stat-label">
            <ClockIcon size={14} /> في الطابور
          </div>
          <div className="stat-value">
            {loading ? "—" : totals.pending}
            <small>مهمة</small>
          </div>
        </div>
        <div className="stat">
          <div className="stat-label">
            <CpuIcon size={14} /> المحرّك الحالي
          </div>
          <div className="stat-value" style={{ fontSize: 17, marginTop: 8 }}>
            {health?.default_engine || "—"}
            <small>{health?.ffmpeg ? "FFmpeg جاهز" : "FFmpeg مفقود"}</small>
          </div>
        </div>
      </div>

      {health?.default_engine === "mock" ? (
        <div className="card card-pad" style={{ marginTop: 14 }}>
          <div className="row wrap" style={{ color: "var(--muted)" }}>
            <span className="badge">وضع العرض</span>
            <span className="tiny grow">
              أنت على المحرّك التجريبي: يولّد فيديو إجرائياً سريعاً لتجربة الواجهة.
              لتوليد حقيقي اربط ComfyUI محلياً أو عبر Colab مجاناً.
            </span>
            <Link href="/settings" className="btn btn-sm btn-soft">
              ربط محرّك حقيقي
              <ArrowLeftIcon size={14} />
            </Link>
          </div>
        </div>
      ) : null}

      <section className="card card-pad" style={{ marginTop: 16 }}>
        <div className="label" style={{ marginBottom: 9 }}>
          <span>ابدأ بوصف سريع</span>
          <span className="hint">Enter للتوليد</span>
        </div>
        <div className="row" style={{ gap: 10 }}>
          <input
            className="input"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") startPrompt();
            }}
            placeholder="مثال: شارع عربي قديم عند الغروب، أطفال يلعبون، كاميرا تتحرك ببطء للأمام"
          />
          <button className="btn btn-primary" onClick={startPrompt} disabled={!prompt.trim()}>
            <SparklesIcon size={16} />
            ولّد
          </button>
        </div>
        <div className="row wrap tiny" style={{ color: "var(--muted-2)", marginTop: 9 }}>
          <button
            className="chip"
            onClick={() =>
              setPrompt("مدينة عربية قديمة عند الغروب، أزقة ضيقة، حركة كاميرا بطيئة، إضاءة ذهبية")
            }
          >
            مدينة عربية
          </button>
          <button
            className="chip"
            onClick={() =>
              setPrompt("منتج عطري على صخور سوداء، رذاذ ماء، إضاءة استوديو ناعمة، دوران بطيء")
            }
          >
            إعلان منتج
          </button>
          <button
            className="chip"
            onClick={() =>
              setPrompt("غابة ضبابية عند الفجر، أشعة ضوء بين الأشجار، كاميرا تتقدم ببطء")
            }
          >
            طبيعة سينمائية
          </button>
        </div>
      </section>

      <div className="section-head">
        <h2 className="section-title">
          مشاريعك <span className="count">{projects.length}</span>
        </h2>
        {projects.length ? (
          <Link href="/library" className="btn btn-sm btn-ghost">
            كل الأصول
            <ArrowLeftIcon size={14} />
          </Link>
        ) : null}
      </div>

      {loading ? (
        <div className="project-grid">
          {[1, 2, 3].map((key) => (
            <div key={key} className="skeleton" style={{ height: 190 }} />
          ))}
        </div>
      ) : projects.length ? (
        <div className="project-grid">
          {projects.map((project) => (
            <Link
              key={project.id}
              href={`/studio?project=${project.id}`}
              className="project-card"
            >
              <div className="project-cover">
                {project.cover_asset_id ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={mediaUrl(`/api/assets/${project.cover_asset_id}/file`)}
                    alt=""
                    loading="lazy"
                  />
                ) : null}
              </div>
              <div className="project-body">
                <div className="project-name">
                  <span
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {project.name}
                  </span>
                  <button
                    className="btn-icon"
                    style={{ width: 28, height: 28 }}
                    onClick={(event) => {
                      event.preventDefault();
                      removeProject(project);
                    }}
                    aria-label="حذف المشروع"
                  >
                    <TrashIcon size={13} />
                  </button>
                </div>
                <div className="project-meta">
                  <span>
                    <FilmIcon size={12} /> {project.asset_count ?? 0} مقطع
                  </span>
                  <span>
                    <SparklesIcon size={12} /> {project.generation_count ?? 0} توليد
                  </span>
                  <span style={{ marginInlineStart: "auto" }}>{timeAgo(project.updated_at)}</span>
                </div>
                {project.description ? (
                  <div className="project-desc">{project.description}</div>
                ) : null}
              </div>
            </Link>
          ))}
          <button className="new-card" onClick={() => setModalOpen(true)}>
            <span className="plus-circle">
              <PlusIcon size={20} />
            </span>
            مشروع جديد
          </button>
        </div>
      ) : (
        <div className="empty">
          <div className="ring">
            <FilmIcon size={26} />
          </div>
          <strong>لا توجد مشاريع بعد</strong>
          <div className="tiny">ابدأ بمشروع واحد، وكل مشاهده ستُجمع هنا.</div>
          <button className="btn btn-primary" onClick={() => setModalOpen(true)}>
            <PlusIcon size={16} />
            إنشاء أول مشروع
          </button>
        </div>
      )}

      <div className="section-head">
        <h2 className="section-title">الاستوديو</h2>
        <span className="tiny muted">الميزات المتاحة الآن والقادمة</span>
      </div>
      <div className="project-grid">
        {FEATURES.map((feature) => {
          const Icon = feature.icon;
          return (
            <div key={feature.title} className="card card-pad" style={{ minHeight: 168 }}>
              <div className="row-between" style={{ alignItems: "flex-start" }}>
                <div className="engine-icon">
                  <Icon size={20} />
                </div>
                <span className={`badge ${feature.tone}`}>{feature.badge}</span>
              </div>
              <div style={{ fontWeight: 750, marginTop: 12, fontSize: 14 }}>
                {feature.title}
              </div>
              <div className="tiny muted" style={{ marginTop: 4 }}>
                {feature.desc}
              </div>
            </div>
          );
        })}
      </div>

      <div className="section-head">
        <h2 className="section-title">كيف يعمل؟</h2>
      </div>
      <div className="grid-2">
        {[
          {
            n: "01",
            t: "اكتب المشهد",
            d: "وصف عربي أو إنجليزي، مع نسبة العرض والمدة. زر «حسّن الوصف» يضيف تفاصيل الإضاءة والحركة.",
          },
          {
            n: "02",
            t: "ولّد وراجع",
            d: "كل توليد يدخل الطابور مع تقدّم حيّ. احتفظ بأفضل نسخة (Take) وأعد التوليد بنفس البذرة.",
          },
          {
            n: "03",
            t: "اجمع وصدّر",
            d: "رتّب المشاهد في المونتاج، ثم صدّر MP4 بمقاس المنصة (9:16 أو 16:9).",
          },
          {
            n: "04",
            t: "اربط GPU مجاناً",
            d: "على جهاز بلا كرت شاشة، شغّل دفتر Colab/Kaggle وألصق رابط النفق في الإعدادات.",
          },
        ].map((step) => (
          <div key={step.n} className="card card-pad">
            <div className="row">
              <span
                className="mono"
                style={{
                  color: "var(--brand)",
                  fontWeight: 800,
                  fontSize: 13,
                  background: "rgba(139,108,255,.1)",
                  border: "1px solid rgba(139,108,255,.25)",
                  borderRadius: 8,
                  padding: "2px 8px",
                }}
              >
                {step.n}
              </span>
              <strong style={{ fontSize: 14 }}>{step.t}</strong>
            </div>
            <div className="tiny muted" style={{ marginTop: 8 }}>
              {step.d}
            </div>
          </div>
        ))}
      </div>

      <ProjectCreateModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={onCreated}
      />
      <Toast state={toast} onClose={() => setToast(null)} />
    </>
  );
}
