import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "alsrory.AI — استوديو الفيديو",
  description:
    "استوديو فيديو بالذكاء الاصطناعي، مفتوح المصدر ومجاني: نص إلى فيديو، صورة إلى فيديو، أفاتار، صوت، ومونتاج.",
};

export const viewport: Viewport = {
  themeColor: "#07070c",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
