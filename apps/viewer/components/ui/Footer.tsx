import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <span className={styles.text}>
        Powered by <span className={styles.brand}>LOOMO</span>
      </span>
    </footer>
  );
}
