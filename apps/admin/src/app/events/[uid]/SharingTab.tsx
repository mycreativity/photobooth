"use client";

import { Button, Card } from "@/app/components/ui";
import { Copy, ExternalLink } from "lucide-react";
import { PUBLIC_BASE } from "./_helpers";
import type { EventData } from "./_types";

interface SharingTabProps {
  event: EventData;
  onCopy: (text: string, label: string) => void;
}

export default function SharingTab({ event, onCopy }: SharingTabProps) {
  const publicUrl = `${PUBLIC_BASE}/${event.uid}`;

  return (
    <div className="max-w-2xl">
      <Card padding="lg">
        <div className="flex flex-col sm:flex-row gap-6 items-start">
          {/* QR Code */}
          <div className="w-full sm:w-auto sm:shrink-0 flex justify-center">
            <div className="p-4 bg-white rounded-xl shadow-lg">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(publicUrl)}`}
                alt={`QR code voor ${event.name}`}
                width={200}
                height={200}
              />
            </div>
          </div>

          {/* Info */}
          <div className="w-full sm:flex-1 space-y-5 min-w-0">
            <div>
              <h4 className="text-sm font-semibold text-[var(--foreground)] mb-2">
                Publieke galerij URL
              </h4>
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                <code className="flex-1 bg-gray-50 border border-[var(--card-border)] px-3 py-2 rounded-lg text-sm text-[var(--foreground)] font-mono break-all">
                  {publicUrl}
                </code>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Copy />}
                  onClick={() => onCopy(publicUrl, "URL")}
                  className="shrink-0"
                >
                  Kopieer
                </Button>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-[var(--foreground)] mb-2">
                Event UID
              </h4>
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                <code className="flex-1 bg-gray-50 border border-[var(--card-border)] px-3 py-2 rounded-lg text-sm text-[var(--foreground)] font-mono">
                  {event.uid}
                </code>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Copy />}
                  onClick={() => onCopy(event.uid, "UID")}
                  className="shrink-0"
                >
                  Kopieer
                </Button>
              </div>
            </div>

            <div>
              <Button
                variant="ghost"
                size="sm"
                icon={<ExternalLink />}
                onClick={() => window.open(publicUrl, "_blank")}
              >
                Open galerij in nieuw tabblad
              </Button>
            </div>

            <p className="text-xs text-[var(--muted-light)] pt-2">
              Gasten kunnen deze QR-code scannen om de publieke foto galerij van
              het event te bekijken.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
