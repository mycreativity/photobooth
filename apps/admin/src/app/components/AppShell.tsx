"use client";

import { createContext, useContext, useState } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";

const SidebarContext = createContext({
  collapsed: false,
  setCollapsed: (_: boolean) => {},
});

export function useSidebar() {
  return useContext(SidebarContext);
}

/**
 * App shell — adds sidebar for authenticated pages.
 * Login and auth pages render without the sidebar.
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  // Pages that should NOT show the sidebar
  const noSidebar =
    pathname.startsWith("/login") || pathname.startsWith("/auth");

  if (noSidebar) {
    return <>{children}</>;
  }

  return (
    <SidebarContext.Provider value={{ collapsed, setCollapsed }}>
      <div className="flex min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950">
        <Sidebar />
        <main
          className={`flex-1 min-h-screen transition-all duration-300 ${
            collapsed ? "ml-[68px]" : "ml-[240px]"
          }`}
        >
          <div className="max-w-7xl mx-auto px-6 py-8">{children}</div>
        </main>
      </div>
    </SidebarContext.Provider>
  );
}
