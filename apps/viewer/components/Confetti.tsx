"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import styles from "./Confetti.module.css";

const COLORS = [
  "#ff9f6a", "#4dd9c0", "#e8607a", "#c8956c",
  "#FFD700", "#f5f0eb", "#ff6b9d", "#7c5cfc",
];

interface Particle {
  id: number;
  x: number;
  color: string;
  w: number;
  h: number;
  delay: number;
  rot: number;
  peak: number;
  drift: number;
  round: boolean;
  dur: number;
}

function make(n: number): Particle[] {
  return Array.from({ length: n }, (_, i) => ({
    id: i,
    x: 5 + Math.random() * 90,
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
    w: 8 + Math.random() * 10,
    h: 6 + Math.random() * 14,
    delay: Math.random() * 0.3,
    rot: Math.random() * 360,
    peak: 40 + Math.random() * 50,
    drift: (Math.random() - 0.5) * 80,
    round: Math.random() > 0.4,
    dur: 5 + Math.random() * 3,
  }));
}

export function Confetti() {
  const [particles] = useState(() => make(80));

  return (
    <div className={styles.container}>
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className={styles.particle}
          style={{
            left: `${p.x}%`,
            bottom: 0,
            width: p.w,
            height: p.h,
            backgroundColor: p.color,
            borderRadius: p.round ? "50%" : "2px",
          }}
          initial={{ y: 0, x: 0, opacity: 0, rotate: p.rot, scale: 0.3 }}
          animate={{
            y: [0, `-${p.peak}vh`, "0vh"],
            x: [0, `${p.drift * 0.4}vw`, `${p.drift}vw`],
            opacity: [0, 1, 0],
            rotate: p.rot + (p.id % 2 === 0 ? 900 : -900),
            scale: [0.3, 1.2, 0.5],
          }}
          transition={{
            duration: p.dur,
            delay: p.delay,
            times: [0, 0.15, 1],
            y: {
              duration: p.dur,
              delay: p.delay,
              times: [0, 0.15, 1],
              ease: ["easeOut", [0.15, 0, 0.3, 1]],
            },
            x: { duration: p.dur, delay: p.delay, ease: "linear" },
            opacity: { duration: p.dur, delay: p.delay, times: [0, 0.1, 1] },
            rotate: { duration: p.dur, delay: p.delay, ease: "linear" },
          }}
        />
      ))}
    </div>
  );
}
