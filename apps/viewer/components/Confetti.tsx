"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import styles from "./Confetti.module.css";

interface Particle {
  id: number;
  x: number;
  color: string;
  size: number;
  delay: number;
  rotation: number;
  peakHeight: number;
  drift: number;
}

const COLORS = [
  "#ff9f6a", // party-warm
  "#4dd9c0", // teal
  "#e8607a", // rose
  "#c8956c", // wood
  "#d4a97a", // wood-light
  "#f5f0eb", // white
];

function createParticles(count: number): Particle[] {
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    x: 30 + Math.random() * 40, // cluster around center
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
    size: Math.random() * 8 + 4,
    delay: Math.random() * 0.3,
    rotation: Math.random() * 360,
    peakHeight: 30 + Math.random() * 50, // how high it shoots (vh)
    drift: (Math.random() - 0.5) * 40, // horizontal drift (vw)
  }));
}

export function Confetti() {
  const [particles] = useState(() => createParticles(60));

  return (
    <div className={styles.container}>
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className={styles.particle}
          style={{
            left: `${p.x}%`,
            bottom: 0,
            width: p.size,
            height: p.size * (Math.random() > 0.5 ? 1 : 0.6),
            backgroundColor: p.color,
            borderRadius: Math.random() > 0.5 ? "50%" : "2px",
          }}
          initial={{
            y: 0,
            x: 0,
            opacity: 1,
            rotate: p.rotation,
          }}
          animate={{
            y: [0, `-${p.peakHeight}vh`, `20vh`],
            x: [0, `${p.drift * 0.5}vw`, `${p.drift}vw`],
            opacity: [1, 1, 0],
            rotate: p.rotation + (Math.random() > 0.5 ? 540 : -540),
          }}
          transition={{
            duration: 3,
            delay: p.delay,
            times: [0, 0.35, 1],
            ease: ["easeOut", "easeIn"],
          }}
        />
      ))}
    </div>
  );
}
