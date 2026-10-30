from __future__ import annotations

import re

from fastapi import APIRouter

from ..schemas import PromptEnhanceRequest

router = APIRouter(prefix="/api/prompts", tags=["prompts"])

_STYLE_WORDS = {
    "cinematic": "أسلوب سينمائي، إضاءة درامية، عمق ميداني، تدرّج لوني فاخر",
    "realistic": "واقعية عالية، تفاصيل دقيقة، إضاءة طبيعية، عدسة 35mm",
    "anime": "أسلوب أنمي، خطوط نظيفة، ألوان مشبعة، خلفية مرسومة",
    "product": "تصوير منتج احترافي، إضاءة استوديو ناعمة، خلفية بسيطة، تفاصيل حادة",
    "nature": "طبيعة خلابة، ضوء ذهبي، ضباب خفيف، حركة هواء واقعية",
    "scifi": "أسلوب خيال علمي، أضواء نيون، أجواء مستقبلية، انعكاسات معدنية",
}

_NEGATIVE_BASE = (
    "تشويه، أطراف زائدة، أصابع مشوّهة، نص، شعار، علامة مائية، ضبابية، "
    "تقطيع، وميض، تبدّل مفاجئ في الملامح، إضاءة مسطّحة"
)

_CAMERA_SUGGESTIONS = [
    "حركة كاميرا بطيئة للأمام",
    "لقطة واسعة ثابتة",
    "تتبّع جانبي ناعم",
    "دوران بطيء حول الموضوع",
]


def _has_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))


@router.post("/enhance")
def enhance_prompt(body: PromptEnhanceRequest) -> dict:
    base = " ".join(body.prompt.split())
    style = _STYLE_WORDS.get(body.style, _STYLE_WORDS["cinematic"])

    additions: list[str] = []
    if len(base) < 160:
        additions.append(style)
    if not re.search(r"كاميرا|لقطة|زاوية|camera|shot", base, re.IGNORECASE):
        additions.append(_CAMERA_SUGGESTIONS[len(base) % len(_CAMERA_SUGGESTIONS)])
    if not re.search(r"إضاءة|ضوء|light", base, re.IGNORECASE):
        additions.append("إضاءة ناعمة متدرّجة، ظلال واقعية")
    additions.append("جودة عالية، تفاصيل حادّة، حركة سلسة 24 إطاراً")

    enhanced = base
    if additions:
        enhanced = f"{base} — " + "، ".join(additions)

    tips: list[str] = []
    if len(base.split()) < 5:
        tips.append("أضف تفاصيل عن المكان والزمن والمزاج لنتيجة أدق.")
    if not _has_arabic(base):
        tips.append("الوصف بالإنجليزية غالباً يعطي التزاماً أفضل بالنموذج.")
    if re.search(r"شخص|رجل|امرأة|طفل|face|person", base) and "ملامح" not in base:
        tips.append("لثبات الملامح، استخدم صورة مرجعية (صورة → فيديو) بدل النص وحده.")
    if "نص" in base or "text" in base.lower():
        tips.append("كتابة النص داخل الفيديو ضعيفة في النماذج المفتوحة؛ أضفه كطبقة في المونتاج.")

    return {
        "prompt": enhanced[:3500],
        "negative_prompt": _NEGATIVE_BASE,
        "tips": tips,
    }
