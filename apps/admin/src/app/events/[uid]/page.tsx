"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { authFetch, clearTokens, isLoggedIn } from "@/lib/auth";
import PageHeader from "@/app/components/PageHeader";
import {
  Button, Tabs, Modal, Toast, Spinner,
} from "@/app/components/ui";
import { Save, Trash2, Settings, Palette, QrCode, MoreVertical } from "lucide-react";

import type { EventData, PresetBackground, Tab, EventForm } from "./_types";
import GeneralTab from "./GeneralTab";
import PhotoCardTab from "./PhotoCardTab";
import SharingTab from "./SharingTab";

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function EventDetailPage() {
  const router = useRouter();
  const params = useParams();
  const uid = params.uid as string;
  const isNew = uid === "new";

  const [event, setEvent] = useState<EventData | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [tab, setTab] = useState<Tab>("general");

  // Form state — general tab
  const [form, setForm] = useState<EventForm>({
    name: "",
    description: "",
    date: "",
    end_date: "",
    is_active: true,
  });
  const [saving, setSaving] = useState(false);

  // Photo card state
  const [presets, setPresets] = useState<PresetBackground[]>([]);
  const [selectedBg, setSelectedBg] = useState<string | null>(null);
  const [brandingText, setBrandingText] = useState("");
  const [displayDate, setDisplayDate] = useState("");
  const [bgVersion, setBgVersion] = useState(0);

  // Toast
  const [toast, setToast] = useState("");
  const showToast = useCallback((msg: string) => {
    setToast(msg);
  }, []);

  // Delete
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Mobile overflow menu
  const [showOverflow, setShowOverflow] = useState(false);

  /* ---- Fetch event ---- */
  const fetchEvent = useCallback(async () => {
    if (isNew) return;
    try {
      const res = await authFetch(`/api/api/events/${uid}`);
      if (res.status === 401) {
        clearTokens();
        router.replace("/login");
        return;
      }
      if (res.status === 404) {
        router.replace("/events");
        return;
      }
      if (!res.ok) throw new Error("Failed to fetch event");
      const data: EventData = await res.json();
      setEvent(data);

      // Populate form
      setForm({
        name: data.name,
        description: data.description || "",
        date: data.date ? data.date.slice(0, 16) : "",
        end_date: data.end_date ? data.end_date.slice(0, 16) : "",
        is_active: data.is_active,
      });

      // Populate photo card fields
      setSelectedBg(data.background_image);
      setBrandingText(
        data.branding_text || `**${data.name}** ✨\n_Wat een feest!_`
      );
      setDisplayDate(data.display_date || "");
    } catch {
      router.replace("/events");
    } finally {
      setLoading(false);
    }
  }, [uid, isNew, router]);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    fetchEvent();
  }, [router, fetchEvent]);

  // Fetch preset backgrounds
  useEffect(() => {
    (async () => {
      try {
        const res = await authFetch("/api/api/events/presets/backgrounds");
        if (res.ok) setPresets(await res.json());
      } catch {
        /* ignore */
      }
    })();
  }, []);

  // Auto-generate Dutch date from event date
  useEffect(() => {
    if (!displayDate && form.date) {
      const d = new Date(form.date);
      const days = [
        "Zondag", "Maandag", "Dinsdag", "Woensdag",
        "Donderdag", "Vrijdag", "Zaterdag",
      ];
      const months = [
        "Januari", "Februari", "Maart", "April", "Mei", "Juni",
        "Juli", "Augustus", "September", "Oktober", "November", "December",
      ];
      if (!isNaN(d.getTime())) {
        setDisplayDate(
          `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`
        );
      }
    }
  }, [displayDate, form.date]);

  /* ---- Save (create or update) ---- */
  async function handleSave() {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        name: form.name,
        description: form.description || null,
        is_active: form.is_active,
        branding_text: brandingText || null,
        display_date: displayDate || null,
      };
      if (form.date) body.date = new Date(form.date).toISOString();
      if (form.end_date) body.end_date = new Date(form.end_date).toISOString();

      if (isNew) {
        const res = await authFetch("/api/api/events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Aanmaken mislukt");
        }
        const created: EventData = await res.json();
        showToast("Event aangemaakt");
        router.replace(`/events/${created.uid}`);
      } else {
        const res = await authFetch(`/api/api/events/${uid}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error("Opslaan mislukt");
        showToast("Event opgeslagen");
        await fetchEvent();
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  /* ---- Delete ---- */
  async function handleDelete() {
    setDeleting(true);
    try {
      const res = await authFetch(`/api/api/events/${uid}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Verwijderen mislukt");
      showToast("Event verwijderd");
      router.replace("/events");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
      setDeleting(false);
    }
  }

  /* ---- Background functions ---- */
  async function selectPreset(presetName: string) {
    try {
      const res = await authFetch(
        `/api/api/events/${uid}/background?preset=${encodeURIComponent(presetName)}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("Failed to set background");
      const data = await res.json();
      setSelectedBg(data.background_image);
      setBgVersion((v) => v + 1);
      showToast("Achtergrond geselecteerd");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    }
  }

  async function uploadCustomBg(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await authFetch(`/api/api/events/${uid}/background`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload mislukt");
      const data = await res.json();
      setSelectedBg(data.background_image);
      setBgVersion((v) => v + 1);
      showToast("Achtergrond geüpload");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    }
  }

  async function removeBg() {
    try {
      await authFetch(`/api/api/events/${uid}/background`, {
        method: "DELETE",
      });
      setSelectedBg(null);
      setBgVersion((v) => v + 1);
      showToast("Achtergrond verwijderd");
    } catch {
      showToast("Verwijderen mislukt");
    }
  }

  /* ---- Push to booth ---- */
  async function handlePush() {
    try {
      await handleSave();
      const boothsRes = await authFetch("/api/api/booths");
      if (!boothsRes.ok) throw new Error("Kon booths niet laden");
      const booths = await boothsRes.json();

      let pushed = 0;
      for (const booth of booths) {
        if (booth.event_id) {
          try {
            const res = await authFetch(
              `/api/api/booths/${booth.booth_id}/push-event`,
              { method: "POST" }
            );
            if (res.ok) pushed++;
          } catch {
            /* skip */
          }
        }
      }
      showToast(
        pushed > 0
          ? `Gepusht naar ${pushed} booth(s)`
          : "Geen online booths gevonden"
      );
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Error");
    }
  }

  /* ---- Copy to clipboard ---- */
  function copyToClipboard(text: string, label: string) {
    navigator.clipboard.writeText(text);
    showToast(`${label} gekopieerd`);
  }

  /* ================================================================== */
  /*  Render                                                            */
  /* ================================================================== */

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  const tabItems = [
    { key: "general", label: "Info", icon: <Settings /> },
    ...(!isNew
      ? [
          { key: "photocard", label: "Kaart", icon: <Palette /> },
          { key: "sharing", label: "QR", icon: <QrCode /> },
        ]
      : []),
  ];

  return (
    <>
      {/* Header — actions visible on desktop, hidden on mobile (sticky footer instead) */}
      <PageHeader
        title={isNew ? "Nieuw Event" : form.name || "Event"}
        subtitle={
          isNew
            ? "Vul de gegevens in om een nieuw event aan te maken"
            : `UID: ${uid}`
        }
        actions={
          <div className="hidden sm:flex items-center gap-3">
            {!isNew && (
              <Button
                variant="danger"
                size="sm"
                onClick={() => setShowDelete(true)}
              >
                Verwijderen
              </Button>
            )}
            <Button
              variant="primary"
              icon={<Save />}
              onClick={handleSave}
              disabled={!form.name.trim()}
              loading={saving}
            >
              {isNew ? "Aanmaken" : "Opslaan"}
            </Button>
          </div>
        }
        backHref="/events"
      />

      {/* Tabs */}
      <Tabs
        tabs={tabItems}
        active={tab}
        onChange={(key) => setTab(key as Tab)}
        className="mb-6"
      />

      {/* Tab content — add bottom padding on mobile for sticky footer */}
      <div className="pb-20 sm:pb-0">
        {tab === "general" && (
          <GeneralTab
            form={form}
            setForm={setForm}
            event={event}
            uid={uid}
            isNew={isNew}
          />
        )}

        {tab === "photocard" && !isNew && (
          <PhotoCardTab
            uid={uid}
            presets={presets}
            selectedBg={selectedBg}
            brandingText={brandingText}
            setBrandingText={setBrandingText}
            displayDate={displayDate}
            setDisplayDate={setDisplayDate}
            bgVersion={bgVersion}
            onSelectPreset={selectPreset}
            onUploadBg={uploadCustomBg}
            onRemoveBg={removeBg}
            onPush={handlePush}
          />
        )}

        {tab === "sharing" && !isNew && event && (
          <SharingTab event={event} onCopy={copyToClipboard} />
        )}
      </div>

      {/* ---- Mobile Sticky Footer ---- */}
      <div className="fixed bottom-0 left-0 right-0 sm:hidden bg-white border-t border-[var(--card-border)] px-4 py-3 flex items-center gap-3 z-40">
        {!isNew && (
          <div className="relative">
            <Button
              variant="ghost"
              size="sm"
              icon={<MoreVertical />}
              onClick={() => setShowOverflow(!showOverflow)}
            >
              {" "}
            </Button>
            {showOverflow && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setShowOverflow(false)}
                />
                <div className="absolute bottom-full left-0 mb-2 bg-white border border-[var(--card-border)] rounded-lg shadow-lg py-1 z-50 min-w-[160px]">
                  <button
                    onClick={() => {
                      setShowOverflow(false);
                      setShowDelete(true);
                    }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-[var(--danger)] hover:bg-gray-50 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    Verwijderen
                  </button>
                </div>
              </>
            )}
          </div>
        )}
        <Button
          variant="primary"
          icon={<Save />}
          onClick={handleSave}
          disabled={!form.name.trim()}
          loading={saving}
          className="flex-1"
        >
          {isNew ? "Aanmaken" : "Opslaan"}
        </Button>
      </div>

      {/* ---- Delete Confirmation ---- */}
      <Modal
        open={showDelete}
        onClose={() => setShowDelete(false)}
        title="Event Verwijderen"
        maxWidth="sm"
        actions={
          <>
            <Button variant="ghost" onClick={() => setShowDelete(false)}>
              Annuleren
            </Button>
            <Button
              variant="danger"
              onClick={handleDelete}
              loading={deleting}
              icon={<Trash2 />}
            >
              Verwijderen
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--muted)]">
          Weet je zeker dat je{" "}
          <strong className="text-[var(--foreground)]">{form.name}</strong> wilt
          verwijderen? Dit kan niet ongedaan worden.
        </p>
      </Modal>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast}
          onDismiss={() => setToast("")}
        />
      )}
    </>
  );
}
