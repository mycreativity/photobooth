export default function HomePage() {
  return (
    <main style={{
      minHeight: "100dvh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      textAlign: "center",
      padding: "2rem",
    }}>
      <div style={{ fontSize: "4rem", marginBottom: "1rem" }}>📸</div>
      <h1 style={{
        fontSize: "2.5rem",
        fontWeight: 800,
        background: "linear-gradient(135deg, #8b5cf6, #d946ef)",
        WebkitBackgroundClip: "text",
        WebkitTextFillColor: "transparent",
        marginBottom: "0.5rem",
      }}>
        MyCreativity
      </h1>
      <p style={{
        fontSize: "1.1rem",
        color: "var(--text-muted)",
        maxWidth: "400px",
      }}>
        Scan de QR-code bij de photobooth om je foto&apos;s te bekijken en downloaden.
      </p>
    </main>
  );
}
