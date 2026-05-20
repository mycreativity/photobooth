import styles from "./ProgressBar.module.css";

interface ProgressBarProps {
  current: number;
  total: number;
}

export function ProgressBar({ current, total }: ProgressBarProps) {
  if (total <= 1) return null;

  return (
    <div className={styles.container}>
      {Array.from({ length: total }, (_, i) => (
        <div
          key={i}
          className={`${styles.segment} ${i === current ? styles.active : ""} ${i < current ? styles.done : ""}`}
        />
      ))}
    </div>
  );
}
