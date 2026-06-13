"use client";

import { createContext, useContext, useState } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

const SidebarContext = createContext({
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
  const [mobileOpen, setMobileOpen] = useState(false);

  // Pages that should NOT show the sidebar
  const noSidebar =
    pathname.startsWith("/login") || pathname.startsWith("/auth");

  if (noSidebar) {
    return <>{children}</>;
  }

  return (
    <SidebarContext.Provider value={{ mobileOpen, setMobileOpen }}>
      <div className="flex h-screen overflow-hidden bg-[var(--background)]">
        {/* Mobile overlay */}
        {mobileOpen && (
          <div
            className="fixed inset-0 bg-black/20 z-30 lg:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}
        <Sidebar />
        <main className="flex-1 lg:ml-[260px] flex flex-col h-screen overflow-hidden">
          <Topbar />
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">{children}</div>
          </div>
        </main>
      </div>
    </SidebarContext.Provider>
  );
}
