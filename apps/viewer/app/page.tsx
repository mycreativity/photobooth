import Image from "next/image";
import { Footer } from "@/components/ui/Footer";
import styles from "./page.module.css";

export default function HomePage() {
  return (
    <main className={styles.container}>
      <div className={styles.content}>
        <Image
          src="/loomo-logo-full.png"
          alt="LOOMO — Wood × Tech × AI"
          width={400}
          height={120}
          className={styles.logo}
          priority
        />

        <p className={styles.instruction}>
          Scan de QR-code bij de photobooth<br />
          om je foto&apos;s te bekijken en te delen.
        </p>
      </div>

      <Footer />
    </main>
  );
}
