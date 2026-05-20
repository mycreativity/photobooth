import { Camera } from "lucide-react";
import { Footer } from "./ui/Footer";
import styles from "./EmptyState.module.css";

interface EmptyStateProps {
  eventName?: string;
}

export function EmptyState({ eventName }: EmptyStateProps) {
  return (
    <main className={styles.container}>
      <div className={styles.content}>
        <div className={styles.pulseWrap}>
          <div className={styles.pulse} />
          <Camera size={36} strokeWidth={1.5} className={styles.icon} />
        </div>

        <h1 className={styles.title}>Even geduld...</h1>
        <p className={styles.subtitle}>
          {eventName
            ? `Je foto's van ${eventName} worden verwerkt.`
            : "Je foto's worden verwerkt."}
        </p>
        <p className={styles.hint}>Dit duurt meestal een paar seconden.</p>
      </div>

      <Footer />
    </main>
  );
}
