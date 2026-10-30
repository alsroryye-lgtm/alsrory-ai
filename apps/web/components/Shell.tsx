"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";
import {
  FilmIcon,
  HomeIcon,
  LayersIcon,
  LibraryIcon,
  ScissorsIcon,
  SettingsIcon,
  SparklesIcon,
} from "@/components/icons";

const NAV = [
  { href: "/", label: "الرئيسية", icon: HomeIcon },
  { href: "/studio", label: "الاستوديو", icon: SparklesIcon },
  { href: "/library", label: "المكتبة", icon: LibraryIcon },
  { href: "/editor", label: "المونتاج", icon: ScissorsIcon },
  { href: "/settings", label: "الإعدادات", icon: SettingsIcon },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await api.health();
        if (alive) {
          setHealth(data);
          setDown(false);
        }
      } catch {
        if (alive) setDown(true);
      }
    };
    load();
    const timer = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <div className="brand-mark">A</div>
          <div>
            <div className="brand-name">
              alsrory<span>.AI</span>
            </div>
            <span className="brand-tag">استوديو الفيديو المفتوح</span>
          </div>
        </Link>

        <nav className="nav">
          <div className="nav-label">مساحة العمل</div>
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link${active ? " active" : ""}`}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-foot">
          <div className="engine-mini">
            <span
              className={`status-dot ${down ? "bad" : health?.pending_jobs ? "busy" : "ok"}`}
            />
            <div className="grow">
              <strong>{down ? "الخادم متوقف" : "الخادم المحلي"}</strong>
              <div className="tiny" style={{ color: "var(--muted-2)" }}>
                {down
                  ? "شغّل scripts\\run.ps1"
                  : `المحرّك: ${health?.default_engine ?? "…"} · v${health?.version ?? "0.1"}`}
              </div>
            </div>
            <LayersIcon size={15} />
          </div>
          <Link href="/studio" className="btn btn-primary" style={{ width: "100%" }}>
            <FilmIcon size={17} />
            مشهد جديد
          </Link>
        </div>
      </aside>

      <main className="main">{children}</main>
    </div>
  );
}
