"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";

interface UserInfo {
  email: string;
  name: string | null;
  role: string;
}

const NAV_ITEMS = [
  { href: "/", label: "Booths", icon: "📸" },
  { href: "/events", label: "Events", icon: "🎉" },
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
  const [collapsed, setCollapsed] = useState(false);

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

  return (
    <aside
      className={`fixed top-0 left-0 h-screen z-20 flex flex-col bg-gray-950/80 backdrop-blur-xl border-r border-gray-800/50 transition-all duration-300 ${
        collapsed ? "w-[68px]" : "w-[240px]"
      }`}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-4 h-16 shrink-0 border-b border-gray-800/50">
        <div className="w-9 h-9 rounded-xl bg-violet-600/20 flex items-center justify-center shrink-0">
          <span className="text-lg">📸</span>
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <h1 className="text-sm font-bold text-white truncate">
              Photobooth
            </h1>
            <p className="text-[10px] text-gray-500 truncate">Admin Panel</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={`ml-auto p-1 text-gray-500 hover:text-white rounded transition ${
            collapsed ? "mx-auto ml-0" : ""
          }`}
          title={collapsed ? "Uitklappen" : "Inklappen"}
        >
          <svg
            className={`w-4 h-4 transition-transform ${
              collapsed ? "rotate-180" : ""
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
            />
          </svg>
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.href);
          return (
            <a
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group ${
                active
                  ? "bg-violet-600/15 text-violet-300 border border-violet-500/20"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50 border border-transparent"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <span className="text-base shrink-0">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </a>
          );
        })}
      </nav>

      {/* User account — bottom */}
      <div className="shrink-0 border-t border-gray-800/50 p-3">
        {user ? (
          <div
            className={`flex items-center gap-3 ${
              collapsed ? "justify-center" : ""
            }`}
          >
            {/* Avatar */}
            <div
              className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shrink-0 cursor-pointer"
              title={user.email}
            >
              <span className="text-xs font-bold text-white">
                {getInitials(user.email, user.name)}
              </span>
            </div>

            {!collapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white font-medium truncate">
                  {user.name || user.email.split("@")[0]}
                </p>
                <p className="text-[10px] text-gray-500 truncate">
                  {user.email}
                </p>
              </div>
            )}

            {!collapsed && (
              <button
                onClick={handleLogout}
                className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition shrink-0"
                title="Uitloggen"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
              </button>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center py-2">
            <div className="w-9 h-9 rounded-full bg-gray-800 animate-pulse" />
          </div>
        )}

        {collapsed && user && (
          <button
            onClick={handleLogout}
            className="w-full mt-2 p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition flex items-center justify-center"
            title="Uitloggen"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
          </button>
        )}
      </div>
    </aside>
  );
}
