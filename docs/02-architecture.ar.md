# 02 — المعمارية

## نظرة عامة

```
┌──────────────────────────────────────────────────────────────────┐
│                      المتصفح (127.0.0.1:3000)                     │
│  Next.js 15 · App Router · TypeScript · Tailwind · RTL عربي      │
└───────────────┬──────────────────────────────────────────────────┘
                │  REST + SSE (JSON)
┌───────────────▼──────────────────────────────────────────────────┐
│                    خدمات API (127.0.0.1:8787)                     │
│  FastAPI · Pydantic · SQLite · asyncio Job Queue · FFmpeg        │
│                                                                   │
│  routers: projects · generations · assets · engines · settings     │
│  services: jobs · storage · media · prompt · planner               │
└───────────────┬──────────────────────────────────────────────────┘
                │  Engine Protocol
     ┌──────────┼───────────────┬──────────────────┐
     ▼          ▼               ▼                  ▼
 ┌───────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────┐
 │ Mock  │ │ ComfyUI    │ │ ComfyUI      │ │ HF Space     │
 │ تجريبي│ │ محلي       │ │ بعيد (Colab) │ │ (gradio API) │
 └───────┘ └────────────┘ └──────────────┘ └──────────────┘
                │               │
                ▼               ▼
        نماذج مفتوحة: Wan 2.2 · LTX-Video · HunyuanVideo
        صوت: ACE-Step · MMAudio · edge-tts / Piper
        مزامنة شفاه: LatentSync · Wav2Lip
        تكبير: Real-ESRGAN · FlashVSR · RIFE
```

## الطبقات

### 1) الواجهة — `apps/web`

- **Next.js 15 (App Router)** مع `output: 'standalone'` اختياري.
- **لا منطق توليد في الواجهة.** كل شيء عبر API.
- حالة الخادم عبر `fetch` + `EventSource` (SSE) للتقدّم الحيّ.
- تصميم: نظام مكوّنات محلي (بدون مكتبة UI ثقيلة) + Tailwind.
- RTL: `<html dir="rtl" lang="ar">`، واستخدام خصائص منطقية (`ms-*`, `me-*`, `ps-*`, `pe-*`).

### 2) الخادم — `services/api`

| الوحدة | المسؤولية |
|---|---|
| `routers/` | نقاط HTTP رقيقة: تحقّق مدخلات + استدعاء خدمة |
| `services/jobs.py` | طابور asyncio، دورة حياة المهمة، إلغاء، إعادة محاولة |
| `services/storage.py` | مسارات الأصول، أسماء آمنة، بث الملفات |
| `services/media.py` | FFmpeg: فحص، مصغّرات، دمج صوت، تصدير |
| `engines/` | تنفيذ `Engine` protocol لكل مزوّد |
| `db.py` | SQLite + WAL + migrations بسيطة |
| `config.py` | إعدادات من `.env` وملف إعدادات المستخدم |

**لماذا FastAPI؟** Python لغة نماذج الفيديو، وFastAPI يعطي async + OpenAPI + SSE بأقل تعقيد.
**لماذا SQLite؟** مستخدم واحد، صفر إعداد، ونسخ احتياطي = نسخ ملف.
**لماذا asyncio بدل Celery/Redis؟** لا نحتاج وسيطاً خارجياً؛ الطابور داخل العملية مع حد تزامن (1 افتراضياً لأن GPU واحد).

### 3) المحرّكات — `engines/`

عقد موحّد (انظر أدناه). كل محرّك يترجم `GenerationSpec` إلى صيغته:

- **MockEngine** — يولّد فيديو إجرائي (تدرّج + نص) عبر Pillow/FFmpeg. للاختبار والعرض.
- **ComfyEngine** — يرسل Workflow JSON إلى ComfyUI (`/prompt`)، يتابع `/history`، ينزّل الناتج.
  - يدعم محلياً (`http://127.0.0.1:8188`) أو بعيداً عبر نفق Cloudflare من Colab.
  - قوالب Workflows في `workers/comfy/workflows/` مع متغيّرات `{{prompt}}` وغيرها.
- **HFSpaceEngine** — يستدعي Space عاماً عبر `gradio_client` بلا أي مفتاح (افتراضياً LTX-Video على ZeroGPU)، ويولّد في الخلفية ثم ينقل الملف إلى مجلد المهمة.
- **Registry** — يقرأ إعدادات المستخدم، يبني المحرّكات، ويختار الافتراضي حسب نوع المهمة.

### 4) المنفّذون — `workers/`

- `workers/colab/alsrory_engine.ipynb`: يثبّت ComfyUI + نموذج Wan/LTX، يفتح نفقاً، ويطبع عنوان الاتصال.
- `workers/comfy/workflows/*.json`: قوالب مُصدّرة من ComfyUI مع Placeholders.
- مبدأ التصميم: **لا نكتب عقد ComfyUI يدوياً في الكود.** المستخدم يصدّر Workflow يعمل عنده، والتطبيق يحقن القيم.

## تدفّق طلب التوليد

```
POST /api/generations
  │ 1. تحقّق + إنشاء صف بحالة queued
  │ 2. إرجاع 202 + id فوراً
  ▼
JobQueue (asyncio)
  │ 3. اختيار المحرّك حسب type + إعدادات المستخدم
  │ 4. engine.submit(spec) → engine_job_id
  │ 5. حلقة poll كل 1.5s → تحديث progress في DB + بث SSE
  │ 6. engine.fetch(result) → ملفات في data/assets/<project>/<gen>/
  │ 7. postprocess (مصغّرات، دمج صوت، ffprobe)
  ▼
SSE: queued → running(progress) → postprocessing → completed(assets)
```

**الإلغاء:** `POST /generations/{id}/cancel` يضبط علماً؛ الحلقة تستدعي `engine.cancel()` إن كان مدعوماً، وإلا تتوقف عن المتابعة وتعلّم المهمة ملغاة.

**الفشل وإعادة المحاولة:** كل خطأ يُخزَّن مع `stage` و`detail`. `POST /generations/{id}/retry` ينشئ مهمة جديدة بنفس المواصفات.

## نموذج البيانات

```sql
projects(id, name, description, aspect_ratio, style_preset,
         created_at, updated_at)

scenes(id, project_id, title, prompt, negative_prompt,
       order_index, duration_s, engine, settings_json, created_at)

generations(id, project_id, scene_id, type, status, progress,
            prompt, negative_prompt, params_json, engine_id,
            engine_job_id, error_stage, error_detail,
            seed, created_at, started_at, finished_at)

assets(id, project_id, generation_id, kind, path, mime,
       width, height, duration_s, size_bytes, meta_json, created_at)

settings(key, value_json, updated_at)   -- مفتاح/قيمة للإعدادات
```

- `type`: `text2video | image2video | video2video | avatar | audio | upscale | interpolate | subtitles | export`
- `status`: `queued | running | postprocessing | completed | failed | canceled`
- `kind`: `video | image | audio | subtitle | thumbnail`

## عقد المحرّك (Engine Protocol)

```python
class Engine(Protocol):
    id: str
    capabilities: set[GenerationType]

    async def health(self) -> EngineHealth: ...
    async def submit(self, job: EngineJob) -> str: ...
    async def poll(self, engine_job_id: str) -> EngineProgress: ...
    async def fetch(self, engine_job_id: str) -> list[EngineArtifact]: ...
    async def cancel(self, engine_job_id: str) -> None: ...
```

```python
EngineJob      = {generation_id, type, prompt, negative_prompt,
                  image_path?, video_path?, audio_path?,
                  width, height, frames, fps, seed, extra: dict}
EngineProgress = {status, progress: 0..1, message?, error?}
EngineArtifact = {kind, filename, data: bytes} | {kind, url}
```

**قاعدة ذهبية:** المحرّك لا يعرف شيئاً عن قاعدة البيانات أو الواجهة. يرى ملفات ومواصفات، ويعيد ملفات.

## الأمان والخصوصية

- الخادم يربط `127.0.0.1` فقط افتراضياً (`API_HOST=127.0.0.1`).
- رفع الملفات: حدّ حجم، فحص نوع حقيقي (magic bytes)، أسماء مُولّدة لا مُدخلة.
- تنفيذ FFmpeg بمصفوفة وسائط (بدون shell)، ومهلات زمنية.
- لا توجد بيانات اعتماد في الكود؛ كل المفاتيح في `.env` أو جدول `settings` (محلي).
- عند استخدام محرّك بعيد: تنبيه واضح أن الملفات ستُرسل إلى ذلك العنوان.
- CORS مقيّد بـ `http://localhost:3000`.

## الأداء

| نقطة | القرار |
|---|---|
| توليد واحد في كل مرة | `MAX_CONCURRENT_JOBS=1` افتراضياً (GPU واحد) |
| تقدّم حيّ | SSE، مع polling احتياطي كل 3 ثوانٍ |
| ملفات كبيرة | بث بـ Range، ومصغّرات WebP/JPEG |
| إعادة التوليد | تخزين `seed + params` لإعادة الإنتاج |
| الذاكرة | لا تحميل فيديوهات كاملة في RAM؛ FFmpeg يتعامل معها على القرص |

## قابلية التوسّع لاحقاً

- استبدال SQLite بـ Postgres: طبقة `db.py` معزولة.
- استبدال الطابور بـ Redis/RQ عند تعدد المستخدمين.
- إضافة مصادقة (JWT) في router middleware دون تغيير المحرّكات.
- إضافة WebSocket لتقدّم أدق.
