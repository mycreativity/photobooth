"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";
import PageHeader from "@/app/components/PageHeader";
import { Button, Badge, EmptyState, Spinner } from "@/app/components/ui";
import {
  Plus, CalendarDays, Camera, ChevronRight,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Event {
  id: string;
  uid: string;
  name: string;
  description: string | null;
  date: string | null;
  end_date: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
  photo_count?: number;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("nl-NL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function EventsPage() {
  const router = useRouter();
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  /* ---- Fetch ---- */
  const fetchEvents = useCallback(async () => {
    try {
      const res = await authFetch("/api/api/events");
      if (res.status === 401) {
        clearTokens();
        router.replace("/login");
        return;
      }
      if (!res.ok) throw new Error("Failed to fetch events");
      setEvents(await res.json());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    fetchEvents();
  }, [router, fetchEvents]);

  /* ---- Render ---- */
  return (
    <>
      <PageHeader
        title="Events"
        subtitle={`${events.length} event${events.length !== 1 ? "s" : ""} aangemaakt`}
        actions={
          <Button
            variant="primary"
            icon={<Plus />}
            onClick={() => router.push("/events/new")}
          >
            Nieuw Event
          </Button>
        }
      />

      {loading ? (
        <div className="flex justify-center py-20">
          <Spinner size="lg" />
        </div>
      ) : error ? (
        <div className="text-center py-20">
          <p className="text-red-400">{error}</p>
        </div>
      ) : events.length === 0 ? (
        <EmptyState
          icon={<CalendarDays />}
          title="Geen events"
          description="Maak een nieuw event aan om foto's te groeperen en een QR-code te genereren."
          action={{ label: "Nieuw Event", onClick: () => router.push("/events/new") }}
        />
      ) : (
        <div className="space-y-2">
          {events.map((ev) => (
            <button
              key={ev.id}
              onClick={() => router.push(`/events/${ev.uid}`)}
              className="w-full text-left group bg-gray-800/30 hover:bg-gray-800/50 border border-gray-700/30 hover:border-gray-600/50 rounded-xl p-4 transition-all duration-200"
            >
              <div className="flex items-center justify-between">
                {/* Left: info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1.5">
                    <h3 className="text-base font-semibold text-white truncate">
                      {ev.name}
                    </h3>
                    <Badge variant={ev.is_active ? "success" : "neutral"}>
                      {ev.is_active ? "Actief" : "Inactief"}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-4 text-sm text-gray-400">
                    <span className="font-mono text-xs bg-gray-700/30 px-2 py-0.5 rounded">
                      {ev.uid}
                    </span>
                    {ev.date && (
                      <span className="flex items-center gap-1.5">
                        <CalendarDays className="w-3.5 h-3.5" />
                        {formatDate(ev.date)}
                        {ev.end_date && (
                          <> — {formatDate(ev.end_date)}</>
                        )}
                      </span>
                    )}
                    {(ev.photo_count ?? 0) > 0 && (
                      <span className="flex items-center gap-1.5 text-violet-400">
                        <Camera className="w-3.5 h-3.5" />
                        {ev.photo_count} foto
                        {ev.photo_count !== 1 ? "'s" : ""}
                      </span>
                    )}
                  </div>
                </div>

                {/* Right: arrow */}
                <ChevronRight className="w-5 h-5 text-gray-600 group-hover:text-gray-400 transition shrink-0 ml-4" />
              </div>
            </button>
          ))}
        </div>
      )}
    </>
  );
}
