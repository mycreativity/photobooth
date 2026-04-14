"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";

interface Booth {
  id: string;
  booth_id: string;
  name: string | null;
  status: string;
  last_seen: string | null;
  cpu_percent: number | null;
  camera_connected: boolean;
  uptime_seconds: number | null;
  version: string | null;
}

function formatUptime(seconds: number | null): string {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}u ${m}m` : `${m}m`;
}

function formatLastSeen(iso: string | null): string {
  if (!iso) return "Nooit";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return "Nu";
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m geleden`;
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}u geleden`;
  return d.toLocaleDateString("nl-NL");
}

export default function DashboardPage() {
  const router = useRouter();
  const [booths, setBooths] = useState<Booth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    fetchBooths();
    const interval = setInterval(fetchBooths, 10_000);
    return () => clearInterval(interval);
  }, [router]);

  async function fetchBooths() {
    try {
      const res = await authFetch("/api/api/booths");

      if (res.status === 401) {
        clearTokens();
        router.replace("/login");
        return;
      }

      if (!res.ok) throw new Error("Failed to fetch booths");

      const data = await res.json();
      setBooths(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    clearTokens();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800/50 bg-gray-900/50 backdrop-blur-xl sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📸</span>
            <h1 className="text-xl font-bold text-white">Photobooth Admin</h1>
          </div>
          <button
            onClick={handleLogout}
            className="text-gray-400 hover:text-white text-sm transition"
          >
            Uitloggen
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-white">Booths</h2>
            <p className="text-gray-400 text-sm mt-1">
              {booths.length} booth{booths.length !== 1 ? "s" : ""} geregistreerd
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-sm text-gray-400">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </span>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 border-4 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="text-center py-20">
            <p className="text-red-400">{error}</p>
          </div>
        ) : booths.length === 0 ? (
          <div className="text-center py-20">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gray-800/50 mb-4">
              <span className="text-4xl">📷</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Geen booths</h3>
            <p className="text-gray-400 text-sm max-w-sm mx-auto">
              Start een photobooth met een server-verbinding geconfigureerd om deze hier te zien.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {booths.map((booth) => (
              <div
                key={booth.id}
                className="group bg-gray-800/30 hover:bg-gray-800/50 border border-gray-700/30 hover:border-gray-600/50 rounded-2xl p-5 transition-all duration-200 cursor-pointer"
                onClick={() => router.push(`/booths/${booth.booth_id}`)}
              >
                {/* Status header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2.5 h-2.5 rounded-full ${
                        booth.status === "online"
                          ? "bg-emerald-500 shadow-lg shadow-emerald-500/50"
                          : "bg-gray-600"
                      }`}
                    />
                    <span className="text-sm font-medium text-gray-300">
                      {booth.status === "online" ? "Online" : "Offline"}
                    </span>
                  </div>
                  {booth.version && (
                    <span className="text-xs text-gray-500 bg-gray-700/50 px-2 py-0.5 rounded-full">
                      v{booth.version}
                    </span>
                  )}
                </div>

                {/* Name */}
                <h3 className="text-lg font-semibold text-white mb-1 group-hover:text-violet-300 transition">
                  {booth.name || booth.booth_id}
                </h3>
                <p className="text-xs text-gray-500 font-mono mb-4">{booth.booth_id}</p>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <p className="text-xs text-gray-500 mb-0.5">CPU</p>
                    <p className="text-sm font-medium text-gray-300">
                      {booth.cpu_percent != null ? `${booth.cpu_percent}%` : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-0.5">Camera</p>
                    <p className="text-sm font-medium">
                      {booth.camera_connected ? (
                        <span className="text-emerald-400">✓</span>
                      ) : (
                        <span className="text-gray-500">✗</span>
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-0.5">Uptime</p>
                    <p className="text-sm font-medium text-gray-300">
                      {formatUptime(booth.uptime_seconds)}
                    </p>
                  </div>
                </div>

                {/* Last seen */}
                <div className="mt-4 pt-3 border-t border-gray-700/30">
                  <p className="text-xs text-gray-500">
                    Laatst gezien: {formatLastSeen(booth.last_seen)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
