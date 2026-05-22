"use client";

import { createContext, useContext, useState } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import { Menu } from "lucide-react";

const SidebarContext = createContext({
  collapsed: false,
  setCollapsed: (_: boolean) => {},
  mobileOpen: false,
  setMobileOpen: (_: boolean) => {},
});

export function useSidebar() {
  return useContext(SidebarContext);
}

/**
 * App shell — adds sidebar for authenticated pages.
 * Login and auth pages render without the sidebar.
 * Mobile-friendly: sidebar is an overlay on small screens.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Pages that should NOT show the sidebar
  const noSidebar =
    pathname.startsWith("/login") || pathname.startsWith("/auth");

  if (noSidebar) {
    return <>{children}</>;
  }

  return (
    <SidebarContext.Provider value={{ collapsed, setCollapsed, mobileOpen, setMobileOpen }}>
      <div className="flex min-h-screen bg-[var(--background)]">
        {/* Mobile overlay */}
        {mobileOpen && (
          <div
            className="fixed inset-0 bg-black/20 z-30 lg:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}
        <Sidebar />
        <main
          className={`flex-1 min-h-screen transition-all duration-300 ${
            collapsed ? "lg:ml-[68px]" : "lg:ml-[260px]"
          }`}
        >
          {/* Mobile header */}
          <div className="lg:hidden flex items-center gap-3 px-4 h-14 border-b border-[var(--card-border)] bg-white sticky top-0 z-20">
            <button
              onClick={() => setMobileOpen(true)}
              className="p-2 -ml-2 text-[var(--muted)] hover:text-[var(--foreground)] rounded-lg transition"
            >
              <Menu className="w-5 h-5" />
            </button>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/loomo-logo-dark.png" alt="LOOMO" className="h-6" />
          </div>
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">{children}</div>
        </main>
      </div>
    </SidebarContext.Provider>
  );
}
