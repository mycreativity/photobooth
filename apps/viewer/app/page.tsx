import { Camera } from "lucide-react";
import { Footer } from "@/components/ui/Footer";
import styles from "./page.module.css";

export default function HomePage() {
  return (
    <main className={styles.container}>
      <div className={styles.content}>
        <div className={styles.iconWrap}>
          <Camera size={48} strokeWidth={1.5} />
        </div>

        <h1 className={styles.title}>LOOMO</h1>
        <p className={styles.subtitle}>WOOD &times; TECH &times; AI</p>

        <div className={styles.divider} />

        <p className={styles.instruction}>
          Scan de QR-code bij de photobooth<br />
          om je foto&apos;s te bekijken en te delen.
        </p>
      </div>

      <Footer />
    </main>
  );
}
