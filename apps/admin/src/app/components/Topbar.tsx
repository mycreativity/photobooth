"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";
import { useSidebar } from "./AppShell";
import { Menu, LogOut, ChevronDown } from "lucide-react";

interface UserInfo {
  email: string;
  name: string | null;
  role: string;
}

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

export default function Topbar() {
  const router = useRouter();
  const { setMobileOpen } = useSidebar();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoggedIn()) return;
    authFetch("/api/auth/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setUser(data);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function handleLogout() {
    clearTokens();
    router.replace("/login");
  }

  return (
    <header className="shrink-0 z-20 flex items-center gap-3 h-14 px-4 sm:px-6 bg-white border-b border-[var(--card-border)]">
      {/* Mobile: hamburger + logo (sidebar is hidden on small screens) */}
      <button
        onClick={() => setMobileOpen(true)}
        className="lg:hidden p-2 -ml-2 text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-gray-100 rounded-lg transition"
      >
        <Menu className="w-5 h-5" />
      </button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/loomo-logo-dark.png" alt="LOOMO" className="h-6 lg:hidden" />

      {/* Account — top right */}
      <div className="ml-auto flex items-center" ref={menuRef}>
        {user ? (
          <div className="relative">
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center gap-2.5 pl-1.5 pr-2 py-1.5 rounded-lg hover:bg-gray-100 transition"
            >
              <div
                className="w-8 h-8 rounded-full bg-gradient-to-br from-[var(--tertiary)] to-[var(--secondary)] flex items-center justify-center shrink-0"
                title={user.email}
              >
                <span className="text-xs font-bold text-white">
                  {getInitials(user.email, user.name)}
                </span>
              </div>
              <span className="hidden sm:block text-sm font-medium text-[var(--foreground)] max-w-[140px] truncate">
                {user.name || user.email.split("@")[0]}
              </span>
              <ChevronDown
                className={`hidden sm:block w-4 h-4 text-[var(--muted-light)] transition-transform ${
                  menuOpen ? "rotate-180" : ""
                }`}
              />
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full mt-2 w-60 bg-white border border-[var(--card-border)] rounded-lg py-1 z-50">
                <div className="px-3 py-2.5 border-b border-[var(--card-border)]">
                  <p className="text-sm font-medium text-[var(--foreground)] truncate">
                    {user.name || user.email.split("@")[0]}
                  </p>
                  <p className="text-xs text-[var(--muted-light)] truncate">
                    {user.email}
                  </p>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-[var(--muted)] hover:text-[var(--danger)] hover:bg-[var(--danger-light)] transition"
                >
                  <LogOut className="w-4 h-4 shrink-0" />
                  Uitloggen
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="w-8 h-8 rounded-full bg-gray-100 animate-pulse" />
        )}
      </div>
    </header>
  );
}
