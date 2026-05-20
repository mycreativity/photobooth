import { AlertCircle, Clock } from "lucide-react";
import { Footer } from "./ui/Footer";
import styles from "./ErrorState.module.css";

interface ErrorStateProps {
  code: number;
  message: string;
}

export function ErrorState({ code, message }: ErrorStateProps) {
  const Icon = code === 410 ? Clock : AlertCircle;

  return (
    <main className={styles.container}>
      <div className={styles.content}>
        <div className={styles.iconWrap}>
          <Icon size={48} strokeWidth={1.5} />
        </div>

        <h1 className={styles.title}>{message}</h1>

        <p className={styles.subtitle}>
          {code === 410
            ? "Deze foto's zijn niet meer beschikbaar."
            : "Controleer of je de juiste QR-code hebt gescand."}
        </p>
      </div>

      <Footer />
    </main>
  );
}
