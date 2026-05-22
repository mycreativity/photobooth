"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";
import { useSidebar } from "./AppShell";
import { Camera, CalendarDays, ChevronsLeft, LogOut, X } from "lucide-react";

interface UserInfo {
  email: string;
  name: string | null;
  role: string;
}

const NAV_ITEMS = [
  { href: "/", label: "Booths", icon: Camera },
  { href: "/events", label: "Events", icon: CalendarDays },
];

function getInitials(email: string, name: string | null): string {
  if (name) {
    return name
      .split(" ")
      .map((w) => w[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  }
  return email.slice(0, 2).toUpperCase();
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const { collapsed, setCollapsed, mobileOpen, setMobileOpen } = useSidebar();

  useEffect(() => {
    if (!isLoggedIn()) return;
    authFetch("/api/auth/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setUser(data);
      })
      .catch(() => {});
  }, []);

  function handleLogout() {
    clearTokens();
    router.replace("/login");
  }

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  function handleNavClick(href: string) {
    setMobileOpen(false);
    router.push(href);
  }

  return (
    <aside
      className={`
        fixed top-0 left-0 h-screen z-40 flex flex-col
        bg-white border-r border-[var(--sidebar-border)]
        transition-all duration-300
        ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
        lg:translate-x-0
        ${collapsed ? "lg:w-[68px]" : "lg:w-[260px]"}
        w-[280px]
      `}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-4 h-16 shrink-0 border-b border-[var(--sidebar-border)]">
        {!collapsed && (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img src="/loomo-logo-dark.png" alt="LOOMO" className="h-7" />
        )}
        {collapsed && (
          <div className="w-9 h-9 rounded-xl bg-[var(--accent-light)] flex items-center justify-center shrink-0">
            <Camera className="w-4.5 h-4.5 text-[var(--accent-dark)]" />
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={`hidden lg:flex ml-auto p-1.5 text-[var(--muted-light)] hover:text-[var(--foreground)] hover:bg-gray-100 rounded-lg transition ${
            collapsed ? "mx-auto ml-0" : ""
          }`}
          title={collapsed ? "Uitklappen" : "Inklappen"}
        >
          <ChevronsLeft
            className={`w-4 h-4 transition-transform ${
              collapsed ? "rotate-180" : ""
            }`}
          />
        </button>
        {/* Mobile close */}
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden ml-auto p-1.5 text-[var(--muted)] hover:text-[var(--foreground)] rounded-lg transition"
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
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                active
                  ? "bg-[var(--accent-light)] text-[var(--accent-dark)] border border-[var(--accent)]/20"
                  : "text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-gray-50 border border-transparent"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="w-[18px] h-[18px] shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* User account — bottom */}
      <div className="shrink-0 border-t border-[var(--sidebar-border)] p-3">
        {user ? (
          <div
            className={`flex items-center gap-3 ${
              collapsed ? "justify-center" : ""
            }`}
          >
            {/* Avatar */}
            <div
              className="w-9 h-9 rounded-full bg-gradient-to-br from-[var(--warm)] to-[var(--accent)] flex items-center justify-center shrink-0 cursor-pointer"
              title={user.email}
            >
              <span className="text-xs font-bold text-white">
                {getInitials(user.email, user.name)}
              </span>
            </div>

            {!collapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm text-[var(--foreground)] font-medium truncate">
                  {user.name || user.email.split("@")[0]}
                </p>
                <p className="text-[10px] text-[var(--muted-light)] truncate">
                  {user.email}
                </p>
              </div>
            )}

            {!collapsed && (
              <button
                onClick={handleLogout}
                className="p-1.5 text-[var(--muted-light)] hover:text-[var(--danger)] hover:bg-[var(--danger-light)] rounded-lg transition shrink-0"
                title="Uitloggen"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center py-2">
            <div className="w-9 h-9 rounded-full bg-gray-100 animate-pulse" />
          </div>
        )}

        {collapsed && user && (
          <button
            onClick={handleLogout}
            className="w-full mt-2 p-1.5 text-[var(--muted-light)] hover:text-[var(--danger)] hover:bg-[var(--danger-light)] rounded-lg transition flex items-center justify-center"
            title="Uitloggen"
          >
            <LogOut className="w-4 h-4" />
          </button>
        )}
      </div>
    </aside>
  );
}
