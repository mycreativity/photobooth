import styles from "./PhotoSlide.module.css";

interface PhotoSlideProps {
  photo: {
    id: string;
    seq: number;
    variant: string;
    url: string;
  };
}

export function PhotoSlide({ photo }: PhotoSlideProps) {
  const isLayout = photo.variant === "print";

  return (
    <div className={`${styles.slide} ${isLayout ? styles.layout : ""}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`${process.env.NEXT_PUBLIC_API_URL || "/api"}${photo.url}`}
        alt={isLayout ? "Foto strip" : `Foto ${photo.seq}`}
        className={styles.image}
        draggable={false}
      />
      {isLayout && (
        <span className={styles.badge}>Strip</span>
      )}
    </div>
  );
}
