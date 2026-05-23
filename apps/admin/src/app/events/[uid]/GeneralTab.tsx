"use client";

import { Input, Textarea, Toggle, Button } from "@/app/components/ui";
import { Camera } from "lucide-react";
import { useRouter } from "next/navigation";
import type { EventData, EventForm } from "./_types";

interface GeneralTabProps {
  form: EventForm;
  setForm: (form: EventForm) => void;
  event: EventData | null;
  uid: string;
  isNew: boolean;
}

export default function GeneralTab({
  form,
  setForm,
  event,
  uid,
  isNew,
}: GeneralTabProps) {
  const router = useRouter();

  return (
    <div className="max-w-2xl space-y-5">
      <Input
        label="Naam *"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        placeholder="bv. Bruiloft Jan & Lisa"
        autoFocus={isNew}
      />

      <Textarea
        label="Beschrijving"
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
        rows={3}
        placeholder="Optionele beschrijving..."
      />

      {/* Start date + End date */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Startdatum"
          type="datetime-local"
          value={form.date}
          onChange={(e) => setForm({ ...form, date: e.target.value })}
          helper="Informatief — de booth werkt ook vóór deze datum"
        />
        <Input
          label="Einddatum"
          type="datetime-local"
          value={form.end_date}
          onChange={(e) => setForm({ ...form, end_date: e.target.value })}
          helper="Na deze datum + 24u stopt de booth met uploaden. De galerij blijft bereikbaar."
        />
      </div>

      {/* Active toggle */}
      {!isNew && (
        <Toggle
          checked={form.is_active}
          onChange={(checked) => setForm({ ...form, is_active: checked })}
          label="Event is actief"
          className="pt-1"
        />
      )}

      {/* Photo count */}
      {event && (event.photo_count ?? 0) > 0 && (
        <div className="pt-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<Camera />}
            onClick={() => router.push(`/events/${uid}/photos`)}
          >
            {event.photo_count} foto
            {event.photo_count !== 1 ? "'s" : ""} bekijken
          </Button>
        </div>
      )}
    </div>
  );
}
