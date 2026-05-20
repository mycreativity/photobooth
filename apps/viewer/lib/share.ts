/**
 * Share & download utilities for the viewer.
 */

/** Download a photo by fetching it and triggering a save dialog. */
export async function downloadPhoto(photoUrl: string, filename: string): Promise<void> {
  try {
    const response = await fetch(photoUrl);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  } catch {
    // Fallback: direct link
    const link = document.createElement("a");
    link.href = photoUrl;
    link.download = filename;
    link.click();
  }
}

/** Share a photo using the native Web Share API (mobile). */
export async function sharePhoto(
  photoUrl: string,
  title: string,
  fallbackUrl: string,
): Promise<"shared" | "cancelled" | "no-support" | "link-shared"> {
  if (!navigator.share) return "no-support";

  try {
    // Try sharing the actual image file
    const response = await fetch(photoUrl);
    const blob = await response.blob();
    const file = new File([blob], "photobooth.jpg", { type: "image/jpeg" });

    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({ title, files: [file] });
      return "shared";
    }

    // Fallback: share the URL instead
    await navigator.share({ title, url: fallbackUrl });
    return "link-shared";
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      return "cancelled";
    }
    // Last resort: share just the URL
    try {
      await navigator.share({ title, url: fallbackUrl });
      return "link-shared";
    } catch {
      return "cancelled";
    }
  }
}

/** Copy text to clipboard. Returns success. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Generate a mailto link for sharing. */
export function getMailtoLink(subject: string, body: string): string {
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

/** Check if native share is available. */
export function hasNativeShare(): boolean {
  return typeof navigator !== "undefined" && !!navigator.share;
}
