"use client";

import { useState, useCallback, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PhotoSlide } from "./PhotoSlide";
import { ProgressBar } from "./ProgressBar";
import { ActionPanel } from "./ActionPanel";
import { Footer } from "./ui/Footer";
import styles from "./SessionViewer.module.css";

interface SessionData {
  token: string;
  layout: string | null;
  photo_count: number;
  event: {
    name: string;
    description: string | null;
    date: string | null;
  } | null;
}

interface PhotoItem {
  id: string;
  seq: number;
  variant: string;
  width: number;
  height: number;
  url: string;
}

interface SessionViewerProps {
  session: SessionData;
  photos: PhotoItem[];
}

const SWIPE_THRESHOLD = 50;

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? "100%" : "-100%",
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction: number) => ({
    x: direction > 0 ? "-100%" : "100%",
    opacity: 0,
  }),
};

export function SessionViewer({ session, photos }: SessionViewerProps) {
  const [[currentIndex, direction], setPage] = useState([0, 0]);

  const paginate = useCallback(
    (newDirection: number) => {
      const newIndex = currentIndex + newDirection;
      if (newIndex >= 0 && newIndex < photos.length) {
        setPage([newIndex, newDirection]);
      }
    },
    [currentIndex, photos.length]
  );

  // Keyboard navigation
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight" || e.key === "ArrowDown") paginate(1);
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") paginate(-1);
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [paginate]);

  const currentPhoto = photos[currentIndex];

  if (!currentPhoto) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <p className={styles.emptyText}>Foto&apos;s worden verwerkt...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Event name */}
      <header className={styles.header}>
        <h1 className={styles.eventName}>{session.event?.name}</h1>
      </header>

      {/* Progress indicators */}
      <ProgressBar current={currentIndex} total={photos.length} />

      {/* Swipeable photo area */}
      <div className={styles.slideArea}>
        <AnimatePresence initial={false} custom={direction} mode="popLayout">
          <motion.div
            key={currentIndex}
            className={styles.slideWrap}
            custom={direction}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{
              x: { type: "spring", stiffness: 300, damping: 30 },
              opacity: { duration: 0.2 },
            }}
            drag="x"
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.7}
            onDragEnd={(_, info) => {
              if (info.offset.x > SWIPE_THRESHOLD) {
                paginate(-1);
              } else if (info.offset.x < -SWIPE_THRESHOLD) {
                paginate(1);
              }
            }}
          >
            <PhotoSlide photo={currentPhoto} />
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Action panel */}
      <ActionPanel
        photo={currentPhoto}
        onPrev={currentIndex > 0 ? () => paginate(-1) : undefined}
        onNext={currentIndex < photos.length - 1 ? () => paginate(1) : undefined}
      />

      <Footer />
    </div>
  );
}
