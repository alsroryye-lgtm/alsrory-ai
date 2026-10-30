"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { EngineSettings, EngineStatus, Health } from "@/lib/types";
import { Toast, type ToastState } from "@/components/Toast";
import {
  AlertIcon,
  CheckIcon,
  CpuIcon,
  DownloadIcon,
  FilmIcon,
  LayersIcon,
  RefreshIcon,
  SettingsIcon,
  SparklesIcon,
} from "@/components/icons";

function StatusPill({ status }: { status?: EngineStatus }) {
  if (!status) return <span className="badge">غير مختبر</span>;
  return (
    <span className={`badge ${status.ready ? "ok" : "bad"}`}>
      {status.ready ? <CheckIcon size={11} /> : <AlertIcon size={11} />}
      {status.ready ? "متصل" : "غير متاح"}
    </span>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<EngineSettings | null>(null);
  const [statuses, setStatuses] = useState<Record<string, EngineStatus>>({});
  const [health, setHealth] = useState<Health | null>(null);
  const [testing, setTesting] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [config, healthData] = await Promise.all([api.settings.get(), api.health()]);
      setSettings(config);
      setHealth(healthData);
      api.engines
        .status()
        .then((list) => {
          const map: Record<string, EngineStatus> = {};
          list.forEach((item) => (map[item.id] = item));
          setStatuses(map);
        })
        .catch(() => {});
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر تحميل الإعدادات",
        kind: "err",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const update = <K extends keyof EngineSettings>(key: K, value: EngineSettings[K]) => {
    setSettings((current) => (current ? { ...current, [key]: value } : current));
  };

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      const saved = await api.settings.update({
        default_engine: settings.default_engine,
        comfy_url: settings.comfy_url,
        comfy_token: settings.comfy_token,
        comfy_workflow: settings.comfy_workflow,
        hf_space_id: settings.hf_space_id,
        hf_api_name: settings.hf_api_name,
        hf_token: settings.hf_token,
      });
      setSettings(saved);
      setToast({ message: "حُفظت الإعدادات وأُعيد تحميل المحرّكات", kind: "ok" });
      api.engines.status().then((list) => {
        const map: Record<string, EngineStatus> = {};
        list.forEach((item) => (map[item.id] = item));
        setStatuses(map);
      });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "تعذّر الحفظ",
        kind: "err",
      });
    } finally {
      setSaving(false);
    }
  };

  const test = async (engineId: string) => {
    setTesting(engineId);
    try {
      const result = await api.engines.test(engineId);
      setStatuses((current) => ({ ...current, [engineId]: result }));
      setToast({
        message: result.ready ? `المحرّك ${engineId} جاهز` : result.detail,
        kind: result.ready ? "ok" : "err",
      });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "فشل الاختبار",
        kind: "err",
      });
    } finally {
      setTesting("");
    }
  };

  const engines = useMemo(() => settings?.available_engines || [], [settings]);

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">settings</div>
          <h1 className="page-title">الإعدادات</h1>
          <p className="page-sub">
            اختر المحرّك، اربط ComfyUI محلياً أو عبر GPU مجاني، وتحكّم في مسار
            التوليد.
          </p>
        </div>
        <div className="row">
          <button className="btn" onClick={load} disabled={loading}>
            <RefreshIcon size={16} />
            تحديث الحالة
          </button>
          <button className="btn btn-primary" onClick={save} disabled={saving || !settings}>
            {saving ? <span className="spinner" /> : <CheckIcon size={16} />}
            حفظ
          </button>
        </div>
      </header>

      {loading || !settings ? (
        <div className="stack">
          <div className="skeleton" style={{ height: 120 }} />
          <div className="skeleton" style={{ height: 260 }} />
        </div>
      ) : (
        <div className="stack" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-head">
              <div className="card-title">
                <CpuIcon size={17} />
                المحرّكات
              </div>
              <span className="tiny muted">التوليد يمرّ عبر محرّك واحد في كل مهمة</span>
            </div>
            <div className="stack" style={{ padding: 16 }}>
              {engines.map((engine) => (
                <div key={engine.id} className="engine-card">
                  <div className="engine-icon">
                    {engine.id === "mock" ? (
                      <SparklesIcon size={20} />
                    ) : engine.id === "comfy" ? (
                      <FilmIcon size={20} />
                    ) : (
                      <LayersIcon size={20} />
                    )}
                  </div>
                  <div className="engine-body">
                    <div className="engine-name">
                      {engine.label}
                      {engine.id === settings.default_engine ? (
                        <span className="badge brand">افتراضي</span>
                      ) : null}
                    </div>
                    <div className="engine-detail">
                      {statuses[engine.id]?.detail || "لم يُختبر بعد"}
                    </div>
                  </div>
                  <div className="row" style={{ gap: 6 }}>
                    <StatusPill status={statuses[engine.id]} />
                    <button
                      className="btn btn-sm"
                      onClick={() => test(engine.id)}
                      disabled={testing === engine.id}
                    >
                      {testing === engine.id ? <span className="spinner" /> : null}
                      اختبار
                    </button>
                    {engine.id !== settings.default_engine ? (
                      <button
                        className="btn btn-sm btn-soft"
                        onClick={() => update("default_engine", engine.id)}
                      >
                        اجعله افتراضياً
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid-2" style={{ alignItems: "start" }}>
            <div className="card">
              <div className="card-head">
                <div className="card-title">
                  <FilmIcon size={16} />
                  ComfyUI
                </div>
                <span className={`badge ${statuses.comfy?.ready ? "ok" : ""}`}>
                  {statuses.comfy?.ready ? "متصل" : "غير متصل"}
                </span>
              </div>
              <div className="stack" style={{ padding: 16 }}>
                <div className="field">
                  <label className="label">
                    عنوان الاتصال
                    <span className="hint">محلي أو نفق Colab</span>
                  </label>
                  <input
                    className="input mono"
                    dir="ltr"
                    value={settings.comfy_url}
                    onChange={(event) => update("comfy_url", event.target.value)}
                    placeholder="http://127.0.0.1:8188"
                  />
                </div>
                <div className="field">
                  <label className="label">
                    الرمز السري
                    <span className="hint">يضيفه دفتر Colab</span>
                  </label>
                  <input
                    className="input mono"
                    dir="ltr"
                    type="password"
                    value={settings.comfy_token}
                    onChange={(event) => update("comfy_token", event.target.value)}
                    placeholder={settings.comfy_token_set ? "محفوظ — اكتب بديلاً" : "اختياري"}
                  />
                </div>
                <div className="field">
                  <label className="label">
                    ملف Workflow
                    <span className="hint">نسبةً لجذر المشروع</span>
                  </label>
                  <input
                    className="input mono"
                    dir="ltr"
                    value={settings.comfy_workflow}
                    onChange={(event) => update("comfy_workflow", event.target.value)}
                    placeholder="workers/comfy/workflows/text2video.json"
                  />
                </div>
                <div className="tiny muted">
                  صدّر Workflow من ComfyUI عبر <strong>Export (API)</strong>، وضع
                  المتغيّرات مثل <span className="mono">{"{{prompt}}"}</span> و
                  <span className="mono">{"{{seed}}"}</span> في العقد.
                </div>
                <button
                  className="btn btn-sm"
                  onClick={() => test("comfy")}
                  disabled={testing === "comfy"}
                >
                  {testing === "comfy" ? <span className="spinner" /> : <CheckIcon size={14} />}
                  اختبار الاتصال
                </button>
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <div className="card-title">
                  <LayersIcon size={16} />
                  Hugging Face Space
                </div>
                <span className="badge">بدون مفتاح</span>
              </div>
              <div className="stack" style={{ padding: 16 }}>
                <div className="field">
                  <label className="label">
                    معرّف Space
                    <span className="hint">user/space-name</span>
                  </label>
                  <input
                    className="input mono"
                    dir="ltr"
                    value={settings.hf_space_id}
                    onChange={(event) => update("hf_space_id", event.target.value)}
                    placeholder="Lightricks/ltx-video-distilled"
                  />
                </div>
                <div className="field">
                  <label className="label">اسم الدالة</label>
                  <input
                    className="input mono"
                    dir="ltr"
                    value={settings.hf_api_name}
                    onChange={(event) => update("hf_api_name", event.target.value)}
                    placeholder="/text_to_video"
                  />
                </div>
                <div className="field">
                  <label className="label">
                    رمز Hugging Face
                    <span className="hint">اختياري</span>
                  </label>
                  <input
                    className="input mono"
                    dir="ltr"
                    type="password"
                    value={settings.hf_token}
                    onChange={(event) => update("hf_token", event.target.value)}
                    placeholder="hf_..."
                  />
                </div>
                <div className="tiny muted">
                  الفضاء الافتراضي <span className="mono">Lightricks/ltx-video-distilled</span>{" "}
                  يعمل على GPU مجاني <strong>بلا أي مفتاح</strong>. يُرسل الوصف (والصورة في
                  صورة→فيديو) إلى خدمة Hugging Face العامة.
                  <br />
                  الحصة المجانية: <strong>دقيقتان يومياً</strong> بلا حساب،
                  و<strong>5 دقائق</strong> مع حساب Hugging Face مجاني (رمز مجاني من{" "}
                  <span className="mono">huggingface.co/settings/tokens</span>).
                </div>
                <button
                  className="btn btn-sm"
                  onClick={() => test("hfspace")}
                  disabled={testing === "hfspace"}
                >
                  {testing === "hfspace" ? <span className="spinner" /> : <CheckIcon size={14} />}
                  اختبار الاتصال
                </button>
              </div>
            </div>
          </div>

          <div className="grid-2" style={{ alignItems: "start" }}>
            <div className="card card-pad">
              <div className="row" style={{ marginBottom: 10 }}>
                <div className="engine-icon">
                  <DownloadIcon size={19} />
                </div>
                <div>
                  <strong style={{ fontSize: 14 }}>GPU مجاني في 5 خطوات</strong>
                  <div className="tiny muted">Kaggle أو Colab</div>
                </div>
              </div>
              <ol
                className="tiny"
                style={{
                  color: "var(--muted)",
                  paddingInlineStart: 18,
                  margin: 0,
                  lineHeight: 2,
                }}
              >
                <li>افتح دفتر workers/colab/alsrory_engine.ipynb.</li>
                <li>اختر GPU T4 (Kaggle: T4 x2).</li>
                <li>شغّل الخلايا حتى يظهر رابط النفق.</li>
                <li>الصق الرابط والرمز هنا واضغط حفظ.</li>
                <li>اضغط «اختبار الاتصال» ثم ولّد مشهداً.</li>
              </ol>
            </div>

            <div className="card card-pad">
              <div className="row" style={{ marginBottom: 10 }}>
                <div className="engine-icon">
                  <SettingsIcon size={19} />
                </div>
                <div>
                  <strong style={{ fontSize: 14 }}>بياناتك</strong>
                  <div className="tiny muted">كل شيء محلي على جهازك</div>
                </div>
              </div>
              <div className="stack tiny" style={{ gap: 7, color: "var(--muted)" }}>
                <div className="row-between">
                  <span>مجلد البيانات</span>
                  <span className="mono" dir="ltr" style={{ fontSize: 10.5 }}>
                    {health?.data_dir}
                  </span>
                </div>
                <div className="row-between">
                  <span>FFmpeg</span>
                  <span className={`badge ${health?.ffmpeg ? "ok" : "bad"}`}>
                    {health?.ffmpeg ? "متاح" : "مفقود"}
                  </span>
                </div>
                <div className="row-between">
                  <span>الإصدار</span>
                  <span className="mono">{health?.version}</span>
                </div>
                <div className="row-between">
                  <span>المهام المعلّقة</span>
                  <span>{health?.pending_jobs ?? 0}</span>
                </div>
                <div className="divider" />
                <div>
                  النسخ الاحتياطي = نسخ مجلد <span className="mono">data</span> بعد
                  إيقاف التطبيق.
                </div>
              </div>
            </div>
          </div>

          <div
            className="card card-pad"
            style={{ borderColor: "rgba(245,199,106,.25)", background: "rgba(245,199,106,.04)" }}
          >
            <div className="row" style={{ alignItems: "flex-start", color: "#f7dda3" }}>
              <AlertIcon size={18} style={{ flex: "none", marginTop: 2 }} />
              <div className="tiny">
                <strong>تذكير:</strong> المحرّك التجريبي يولّد فيديو إجرائياً للتجربة
                فقط. الجودة الحقيقية تحتاج نماذج مفتوحة على GPU. لا تشارك رابط نفق
                Colab — من يملكه يستطيع استخدام محرّكك.
              </div>
            </div>
          </div>
        </div>
      )}

      <Toast state={toast} onClose={() => setToast(null)} />
    </>
  );
}
