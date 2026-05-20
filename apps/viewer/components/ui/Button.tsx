"use client";

import { type ButtonHTMLAttributes, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import styles from "./Button.module.css";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "glass";
  size?: "sm" | "md" | "lg";
  icon?: LucideIcon;
  iconPosition?: "left" | "right";
  children: ReactNode;
}

export function Button({
  variant = "primary",
  size = "md",
  icon: Icon,
  iconPosition = "left",
  children,
  className,
  ...props
}: ButtonProps) {
  const iconSize = size === "sm" ? 16 : size === "lg" ? 22 : 18;

  return (
    <button
      className={`${styles.btn} ${styles[variant]} ${styles[size]} ${className ?? ""}`}
      {...props}
    >
      {Icon && iconPosition === "left" && <Icon size={iconSize} />}
      <span>{children}</span>
      {Icon && iconPosition === "right" && <Icon size={iconSize} />}
    </button>
  );
}
