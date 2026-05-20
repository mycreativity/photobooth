"use client";

import { Download, Share2, ChevronLeft, ChevronRight } from "lucide-react";
import styles from "./ActionPanel.module.css";

interface ActionPanelProps {
  photo: {
    id: string;
    variant: string;
    url: string;
    seq: number;
  };
  onPrev?: () => void;
  onNext?: () => void;
}

export function ActionPanel({ photo, onPrev, onNext }: ActionPanelProps) {
  const isLayout = photo.variant === "print";

  async function handleShare() {
    const photoUrl = `/api${photo.url}`;

    if (navigator.share) {
      try {
        // Try to share the actual image file
        const response = await fetch(photoUrl);
        const blob = await response.blob();
        const file = new File([blob], `photo_${photo.seq}.jpg`, { type: "image/jpeg" });

        await navigator.share({
          title: isLayout ? "Mijn photobooth strip" : `Photobooth foto ${photo.seq}`,
          files: [file],
        });
      } catch (err) {
        // User cancelled or share failed — try URL share
        if (err instanceof Error && err.name !== "AbortError") {
          await navigator.share({
            title: isLayout ? "Mijn photobooth strip" : `Photobooth foto`,
            url: window.location.href,
          });
        }
      }
    } else {
      // Desktop fallback: copy link
      try {
        await navigator.clipboard.writeText(window.location.href);
        // TODO: Show toast notification
      } catch {
        // Clipboard not available
      }
    }
  }

  function handleDownload() {
    const link = document.createElement("a");
    link.href = `/api${photo.url}`;
    link.download = isLayout
      ? `photobooth_strip.jpg`
      : `photo_${photo.seq}.jpg`;
    link.click();
  }

  return (
    <div className={styles.panel}>
      <div className={styles.inner}>
        {/* Navigation */}
        <button
          className={`${styles.navBtn} ${!onPrev ? styles.disabled : ""}`}
          onClick={onPrev}
          disabled={!onPrev}
          aria-label="Vorige foto"
        >
          <ChevronLeft size={20} />
        </button>

        {/* Actions */}
        <div className={styles.actions}>
          <button className={styles.actionBtn} onClick={handleShare}>
            <Share2 size={20} />
            <span>Deel</span>
          </button>

          <button className={styles.actionBtn} onClick={handleDownload}>
            <Download size={20} />
            <span>Download</span>
          </button>
        </div>

        {/* Navigation */}
        <button
          className={`${styles.navBtn} ${!onNext ? styles.disabled : ""}`}
          onClick={onNext}
          disabled={!onNext}
          aria-label="Volgende foto"
        >
          <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
}
