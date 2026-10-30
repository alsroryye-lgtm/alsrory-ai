# 06 — التثبيت والتشغيل

## المتطلبات

- Windows 10/11 (64-bit)
- Python 3.10 أو 3.11 (لا تستخدم 3.13+ مع حزم الذكاء الاصطناعي)
- Node.js 20 LTS أو أحدث
- FFmpeg (يُثبّت تلقائياً عبر `imageio-ffmpeg` كبديل، لكن نسخة النظام أفضل)

> على جهازك الحالي: Python 3.10 موجود في `C:\Users\HP\AppData\Local\Programs\Python\Python310`. لا يوجد Node ولا FFmpeg. سكربت التثبيت يجهّز Node محمولاً داخل `tools\node` دون تغيير النظام.

## التثبيت

```powershell
cd F:\المشاريع\alsrory-ai
.\scripts\setup.ps1
```

أو بالنقر المزدوج: `scripts\setup.bat` (يشغّل نفس السكربت مع تجاوز سياسة PowerShell).

ماذا يفعل؟
1. ينشئ `.venv` باستخدام Python 3.10.
2. يثبّت متطلبات الخادم (`requirements.txt`).
3. ينزّل Node.js المحمول إلى `tools\node` إن لم يكن موجوداً.
4. يثبّت حزم الواجهة (`npm install`).
5. ينشئ `services/api/.env` من `.env.example`.
6. ينشئ مجلدات `data/`.

## التشغيل

```powershell
.\scripts\run.ps1
```

أو `scripts\run.bat` بالنقر المزدوج، وللإيقاف `scripts\stop.bat`.

- الواجهة: http://localhost:3000
- API: http://127.0.0.1:8787
- توثيق API التفاعلي: http://127.0.0.1:8787/docs
- الإيقاف: `Ctrl+C` أو `.\scripts\stop.ps1`

## الإعدادات

`services/api/.env`:

```env
API_HOST=127.0.0.1
API_PORT=8787
DATA_DIR=data
DEFAULT_ENGINE=mock
MAX_CONCURRENT_JOBS=1
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
COMFY_URL=http://127.0.0.1:8188
COMFY_TOKEN=
COMFY_WORKFLOW=workers/comfy/workflows/text2video.json
HF_SPACE_ID=Lightricks/ltx-video-distilled
HF_API_NAME=/text_to_video
FFMPEG_PATH=
```

> `DATA_DIR=data` يُفسَّر نسبةً إلى جذر المشروع، فتكون قاعدة البيانات في `data\alsrory.db`.
> يمكنك أيضاً ضبط `COMFY_URL` و`COMFY_TOKEN` من واجهة الإعدادات دون إعادة تشغيل؛ تُحفظ في قاعدة البيانات.

| المفتاح | المعنى |
|---|---|
| `DEFAULT_ENGINE` | `mock` أو `comfy` أو `hfspace` |
| `COMFY_URL` | عنوان ComfyUI (محلي أو نفق Colab) |
| `COMFY_TOKEN` | الرمز السري الذي يضيفه دفتر Colab |
| `HF_SPACE_ID` | فضاء Hugging Face بلا مفتاح (افتراضياً `Lightricks/ltx-video-distilled`) — اتركه فارغاً للتعطيل |
| `HF_API_NAME` | اسم دالة الفضاء (افتراضياً `/text_to_video`) |
| `FFMPEG_PATH` | مسار ffmpeg.exe إن لم يكن في PATH |

## توصيل ComfyUI محلي

1. ثبّت [ComfyUI](https://github.com/comfyanonymous/ComfyUI) وComfyUI-Manager.
2. نزّل نموذجاً (مثلاً LTX-Video 2B أو Wan 2.2 TI2V-5B) إلى `ComfyUI/models/checkpoints`.
3. شغّل ComfyUI: `python main.py --listen 127.0.0.1 --port 8188`.
4. افتح الواجهة، صمّم Workflow يعمل، ثم **Export (API)** إلى JSON.
5. ضع الملف في `workers/comfy/workflows/` واستخدم المتغيّرات:
   `{{prompt}}`, `{{negative}}`, `{{width}}`, `{{height}}`, `{{frames}}`, `{{fps}}`, `{{seed}}`, `{{image}}`.
6. في alsrory.AI → الإعدادات → المحرّكات → اختبار الاتصال.

## توصيل GPU مجاني (Colab/Kaggle)

راجع [`04-hardware-and-free-gpu.ar.md`](04-hardware-and-free-gpu.ar.md). باختصار:

1. شغّل `workers/colab/alsrory_engine.ipynb`.
2. انسخ `ALSROY_ENGINE_URL` و`ALSROY_TOKEN`.
3. الصقهما في إعدادات التطبيق أو في `.env`.

## حل المشاكل

| المشكلة | السبب | الحل |
|---|---|---|
| `python not found` | متجر Windows يعترض | استخدم `.venv` أو `py -3.10` |
| `Port 3000 in use` | نسخة سابقة تعمل | `.\scripts\stop.ps1` أو غيّر المنفذ |
| الواجهة تفتح لكن لا بيانات | API لم يبدأ | تحقّق من http://127.0.0.1:8787/api/health |
| التوليد يعلق عند 0% | ComfyUI لا يستجيب | اختبر الاتصال من الإعدادات، راجع سجل الخادم |
| فيديو بلا صوت | FFmpeg غير متاح | ثبّت FFmpeg أو استخدم `imageio-ffmpeg` |
| خطأ CORS | فتح الواجهة بعنوان آخر | استخدم `localhost:3000` أو عدّل `ALLOWED_ORIGINS` |
| نفاد المساحة | نماذج + فيديوهات | احذف من المكتبة، نظّف `data/assets` |
| `500` في كل الصفحات بعد `next build` | `next build` و`next dev` يتشاركان مجلد `.next` | أوقف dev، ثم `npm run build`، أو أعد تشغيل dev بعد حذف `.next` |
| التوليد على ComfyUI يفشل فوراً | لا يوجد Workflow للنوع المطلوب | راجع `workers/comfy/README.md` وصدّر ملفاً باسم النوع (`image2video.json` مثلاً) |
| ComfyUI يستهلك كل الذاكرة | T4 16GB مع نموذج كبير | شغّل بـ `--lowvram` أو استخدم نموذج fp8 |

## النسخ الاحتياطي

كل شيء في `data/`:

```
data/
├─ alsrory.db          # المشاريع والمهام
├─ assets/             # الفيديوهات والصور والصوت
└─ thumbnails/
```

أوقف التطبيق، ثم انسخ المجلد كاملاً. للاستعادة، أعده مكانه.

## التطوير

```powershell
# الخادم مع إعادة التحميل التلقائي
.\.venv\Scripts\uvicorn app.main:app --reload --port 8787 --app-dir services/api

# الواجهة
cd apps\web
npm run dev

# فحص الأنواع والإنتاج (أوقف dev أولاً — يتشاركان .next)
npm run typecheck
npm run build
```

الاختبارات:

```powershell
.\.venv\Scripts\pytest -q
```
