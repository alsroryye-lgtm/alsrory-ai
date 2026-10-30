# المساهمة في alsrory.AI

شكراً لرغبتك في المساهمة! **alsrory.AI** مشروع مجاني ومفتوح المصدر يهدف إلى استوديو فيديو بالذكاء الاصطناعي يعمل محلياً بواجهة عربية. أي مساهمة — كود، وثائق، ترجمة، أو تقرير خطأ — مرحّب بها.

<div dir="rtl" align="right">

## قبل أن تبدأ

- ابحث في [Issues](https://github.com/alsroryye-lgtm/alsrory-ai/issues) عن مشكلة مشابهة قبل فتح واحدة جديدة.
- للتغييرات الكبيرة (ميزة جديدة، تغيير في المعمارية، إضافة محرّك) افتح **Issue للنقاش** أولاً حتى لا تبني شيئاً قد لا يُقبل.
- لا تُرفق في أي Issue أو PR: مفاتيح API، رموز النفق (`X-Alsrory-Token`)، أو مجلد `data/` الذي يحتوي مشاريعك.
- كن لطيفاً ومحترماً؛ نحن هنا لنتعلّم. راجع [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) للتفاصيل.
- للثغرات الأمنية اتبع [`SECURITY.md`](SECURITY.md) ولا تفتح Issue عاماً.

## بيئة التطوير

### Windows (الأسهل)

</div>

```powershell
# 1) Install the portable toolchain once (Node + Python venv)
.\scripts\setup.ps1

# 2) Start API + web
.\scripts\run.ps1
```

<div dir="rtl" align="right">

هذا يشغّل الـ API على `http://127.0.0.1:8787` والواجهة على `http://localhost:3000`.
الواجهة تعمل افتراضياً على **المحرّك التجريبي (Mock)**، لذا لا تحتاج GPU لتطوير الواجهة.

### يدوياً (Linux / macOS / أي نظام)

</div>

```bash
# API
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r services/api/requirements.txt
uvicorn app.main:app --reload --port 8787 --app-dir services/api

# Web (terminal second)
cd apps/web
npm install
npm run dev                        # http://localhost:3000
```

<div dir="rtl" align="right">

## الفحوصات قبل إرسال PR

شغّل هذه الأوامر وتأكد أنها تنجح:

</div>

```bash
# API tests
python -m pytest

# Web type check
cd apps/web && npm run typecheck

# Web production build
cd apps/web && npm run build
```

<div dir="rtl" align="right">

> ⚠️ **مهم:** لا تشغّل `npm run build` أثناء عمل `npm run dev`. الاثنان يستخدمان مجلد `.next` نفسه، وقد يتلف خادم التطوير (أخطاء `__webpack_modules__ is not a function`).
> أوقف `dev` أولاً، احذف `.next`، ثم ابنِ. وبعد البناء، احذف `.next` مرة أخرى قبل إعادة `dev`.

## بنية الكود

| المسار | المحتوى |
|---|---|
| `apps/web/` | واجهة Next.js 15 (App Router) + Tailwind 4، عربية RTL |
| `services/api/app/routers/` | مسارات REST (مشاريع، توليد، أصول، تصدير، إعدادات) |
| `services/api/app/engines/` | محرّكات التوليد: `mock`، `comfy`، `hfspace` |
| `services/api/app/services/` | قاعدة البيانات، التخزين، طابور المهام، التصدير |
| `services/api/tests/` | اختبارات pytest |
| `workers/comfy/` | قوالب ComfyUI API + دليل الربط |
| `workers/colab/` | دفتر Colab/Kaggle + وسيط الحماية بالرمز |
| `docs/` | الرؤية، المعمارية، الميزات، العتاد، خارطة الطريق، التثبيت، القرارات |

## إضافة محرّك جديد

1. أنشئ ملفاً في `services/api/app/engines/` ينفّذ واجهة `Engine` المعرّفة في `engines/base.py`:
   `id`, `label`, `capabilities`, ثم `health()`, `submit()`, `poll()`, `fetch()`, `cancel()`.
2. سجّل المحرّك في `services/api/app/engines/registry.py`.
3. أعد `EngineArtifact` مع `path` (وليس `data`) للملفات الكبيرة، وحدّد `duration_s`/`width`/`height` إن كانت معروفة.
4. أضف اختباراً في `services/api/tests/` يغطي `health()` وحالة عدم التوفّر.
5. أضف صفاً في جدول «الحالة الحالية» في `README.md` ووثّق إعداداته في `docs/`.

## إضافة Workflow لـ ComfyUI

- ضع القالب في `workers/comfy/workflows/<type>.json` مستخدماً العناصر النائبة `{{prompt}}`, `{{negative_prompt}}`, `{{width}}`, `{{height}}`, `{{frames}}`, `{{fps}}`, `{{seed}}` حسب الحاجة.
- استخدم صيغة **API** من ComfyUI (Save → Export API)، لا صيغة الواجهة.
- اذكر اسم القالب والموديل المطلوب في `workers/comfy/README.md`.

## قواعد الكود والواجهة

- **الواجهة عربية RTL**: كل نص جديد يراه المستخدم يجب أن يكون عربياً، مع خصائص CSS منطقية (`ms-*`, `me-*`, `start-*`, `end-*`) بدل `ml-*`/`mr-*`.
- **الكود والتعليقات بالإنجليزية**، أسماء واضحة، بلا سحر أو اختصارات غامضة.
- **لا أسرار في الكود**: كل ما هو خاص يوضع في متغيرات البيئة أو `services/api/.env` (وهو مستبعد من Git).
- **لا ترفع ملفات ثقيلة**: `data/`, `exports/`, `node_modules/`, `tools/` كلها في `.gitignore` — أبقِها كذلك.
- حافظ على نمط الملفات المحيطة بك (تنسيق، أسماء، بنية imports) بدل إعادة اختراع الأسلوب.

## الاعتماديات والتحديثات

- **Dependabot** يفتح PRs أسبوعياً لترقيات `minor`/`patch` فقط في `apps/web` و`services/api`، ولترقيات GitHub Actions.
- **الترقيات الكبرى (`major`) تُراجع يدوياً**: مثل Next.js 15 → 16 أو Pydantic 2 → 3 تحتاج تعديلات واختباراً كاملاً، فلا تُدمج آلياً.
- **تحديثات الأمان** تصل تلقائياً وتتجاوز قاعدة تجاهل الإصدارات الكبرى — لا تُغلقها إلا إذا أثبتت أنها غير مؤثرة.
- لا ترفع `node_modules/` أو `.venv/`، وحدّث `apps/web/package-lock.json` مع أي تغيير في اعتماديات الواجهة.
- **CodeQL** يفحص JavaScript/TypeScript وPython عند كل push وPR، وأسبوعياً كل يوم اثنين.

## الفروع والرسائل والـ PR

- اشتقّ فرعك من `main`: `feat/<short-name>` أو `fix/<short-name>` أو `docs/<short-name>`.
- اكتب رسائل كوميت مختصرة بصيغة Conventional Commits، مثال:
  `feat(api): add wan2.2 workflow mapping` — `fix(web): keep timeline order after export`.
- PR واحد = غرض واحد. لا تخلط إعادة تنسيق ضخمة مع إصلاح وظيفي.
- املأ قالب الـ PR: ماذا تغيّر، وكيف اختبرته، وأي خطوات يدوية مطلوبة.
- أضف لقطات شاشة للتغييرات في الواجهة (قبل/بعد إن أمكن).
- قد يُطلب منك تعديلات في المراجعة — هذا طبيعي وليس رفضاً.

## الرخصة

بإرسالك مساهمة، فإنك توافق على نشرها تحت رخصة **AGPL-3.0** نفسها التي يستخدمها المشروع. استخدم، عدّل، وشارك بحرية — وإذا قدّمت الخدمة للعامة عبر الشبكة، انشر تعديلاتك.

</div>
