"use client";

import { usePathname, useRouter } from "next/navigation";
import { useSidebar } from "./AppShell";
import { Camera, CalendarDays, X } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Booths", icon: Camera },
  { href: "/events", label: "Events", icon: CalendarDays },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { mobileOpen, setMobileOpen } = useSidebar();

  function isActive(href: string) {
    if (href === "/") return pathname === "/" || pathname.startsWith("/booths");
    return pathname.startsWith(href);
  }

  function handleNavClick(href: string) {
    setMobileOpen(false);
    router.push(href);
  }

  return (
    <aside
      className={`
        fixed top-0 left-0 h-screen z-40 flex flex-col w-[280px] lg:w-[260px]
        bg-gradient-to-b from-[var(--sidebar-from)] via-[var(--sidebar-via)] to-[var(--sidebar-to)]
        border-r border-[var(--sidebar-border)]
        transition-transform duration-300
        ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
        lg:translate-x-0
      `}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-4 h-14 shrink-0 border-b border-[var(--sidebar-border)]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/loomo-wordmark.png" alt="LOOMO" className="h-5" />
        {/* Mobile close */}
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden ml-auto p-1.5 text-[var(--sidebar-text-muted)] hover:text-white rounded-lg transition"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.href);
          const Icon = item.icon;
          return (
            <button
              key={item.href}
              onClick={() => handleNavClick(item.href)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 focus:outline-none ${
                active
                  ? "bg-white/10 text-white"
                  : "text-[var(--sidebar-text)] hover:text-white hover:bg-white/5"
              }`}
            >
              <Icon
                className={`w-[18px] h-[18px] shrink-0 ${
                  active ? "text-[var(--secondary)]" : ""
                }`}
              />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
