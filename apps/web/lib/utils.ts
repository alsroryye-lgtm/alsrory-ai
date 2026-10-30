export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 ب";
  const units = ["ب", "ك.ب", "م.ب", "ج.ب"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)} ث`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const diff = (Date.now() - date.getTime()) / 1000;
  if (diff < 60) return "الآن";
  if (diff < 3600) return `قبل ${Math.floor(diff / 60)} د`;
  if (diff < 86400) return `قبل ${Math.floor(diff / 3600)} س`;
  if (diff < 604800) return `قبل ${Math.floor(diff / 86400)} يوم`;
  return date.toLocaleDateString("ar", { day: "numeric", month: "short" });
}

export const STATUS_LABELS: Record<string, string> = {
  queued: "في الانتظار",
  running: "قيد التوليد",
  postprocessing: "المعالجة النهائية",
  completed: "مكتمل",
  failed: "فشل",
  canceled: "ملغى",
};

export const TYPE_LABELS: Record<string, string> = {
  text2video: "نص → فيديو",
  image2video: "صورة → فيديو",
  video2video: "فيديو → فيديو",
  avatar: "أفاتار ناطق",
  upscale: "تكبير الدقة",
  interpolate: "زيادة الإطارات",
  subtitles: "ترجمة",
  audio: "صوت",
  export: "تصدير",
};

export const ASPECT_LABELS: Record<string, string> = {
  "16:9": "أفقي 16:9",
  "9:16": "عمودي 9:16",
  "1:1": "مربع 1:1",
  "4:3": "كلاسيكي 4:3",
  "3:4": "بورتريه 3:4",
};

export const ASPECT_SIZES: Record<string, [number, number]> = {
  "16:9": [832, 480],
  "9:16": [480, 832],
  "1:1": [640, 640],
  "4:3": [704, 528],
  "3:4": [528, 704],
};

export const STYLE_PRESETS: Array<{ id: string; label: string }> = [
  { id: "cinematic", label: "سينمائي" },
  { id: "realistic", label: "واقعي" },
  { id: "anime", label: "أنمي" },
  { id: "product", label: "إعلاني" },
  { id: "nature", label: "طبيعة" },
  { id: "scifi", label: "خيال علمي" },
];
