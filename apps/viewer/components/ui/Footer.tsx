import Image from "next/image";
import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <span className={styles.text}>Powered by</span>
      <Image
        src="/loomo-wordmark.png"
        alt="LOOMO"
        width={80}
        height={20}
        className={styles.logo}
      />
    </footer>
  );
}
