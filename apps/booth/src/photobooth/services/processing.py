"""Lightweight image processing for the photobooth.

All functions are pure: JPEG bytes in → JPEG bytes out.
Uses only Pillow — no heavy ML dependencies — so it runs
comfortably on a Raspberry Pi 4.

Available effects:
- **auto_retouch**: Subtle smoothing + auto-contrast.  Flatters skin
  without looking fake.
- **brightness_boost**: Simple brightness increase via an
  ``ImageEnhance.Brightness`` multiplier.
- **apply_filter_to_jpeg**: Apply B&W or sepia filter to JPEG bytes.
- **apply_filter_to_frame**: Apply filter to raw JPEG frame bytes
  (fast path for live preview).
- **3D LUT support**: Drop `.cube` files into ``assets/luts/`` and
  they appear as selectable filters automatically.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

# Default JPEG quality for processed output (matches capture quality)
_OUTPUT_QUALITY = 92


# ---------------------------------------------------------------------------
# 3D LUT Engine — .cube file support
# ---------------------------------------------------------------------------

# Default location for LUT files
_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "luts"


def _parse_cube_file(path: str | Path) -> tuple[str, int, list[tuple[float, float, float]]]:
    """Parse a .cube LUT file.

    Returns:
        Tuple of (title, size, table) where table is a flat list of
        (r, g, b) float triples in the order expected by Pillow's
        Color3DLUT: R changes fastest, then G, then B.
    """
    filename_title = Path(path).stem.replace("_", " ").title()
    title = filename_title
    size = 0
    table: list[tuple[float, float, float]] = []

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("TITLE"):
                # TITLE "My Filter"
                parsed = line.split('"')[1] if '"' in line else line.split(None, 1)[1]
                # Only use if it's informative (not "Untitled" or similar)
                if parsed.strip().lower() not in ("", "untitled", "none"):
                    title = parsed.strip()
                continue
            if line.startswith("LUT_3D_SIZE"):
                size = int(line.split()[-1])
                continue
            if line.startswith(("DOMAIN_MIN", "DOMAIN_MAX", "LUT_1D_SIZE")):
                continue
            # Data line: R G B
            parts = line.split()
            if len(parts) >= 3:
                try:
                    r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
                    table.append((r, g, b))
                except ValueError:
                    continue

    if size == 0:
        # Infer size from table length (size^3 entries)
        size = round(len(table) ** (1 / 3))

    return title, size, table


class LutRegistry:
    """Auto-discovers and caches 3D LUTs from the assets/luts/ folder.

    Usage::

        registry = LutRegistry()
        names = registry.available_luts()       # ['Film Noir', 'Rosé', ...]
        img = registry.apply_pil(img, 'rose')   # Apply to PIL Image
        bgr = registry.apply_cv2(bgr, 'rose')   # Apply to OpenCV BGR frame
    """

    def __init__(self, lut_dir: str | Path | None = None) -> None:
        self._lut_dir = Path(lut_dir) if lut_dir else _ASSETS_DIR
        # Cache: filter_id -> (title, pil_lut, cv2_lut_table)
        self._cache: dict[str, tuple[str, ImageFilter.Color3DLUT | None, np.ndarray | None]] = {}
        self._scanned = False

    def _scan(self) -> None:
        """Scan the LUT directory for .cube files."""
        if self._scanned:
            return
        self._scanned = True

        if not self._lut_dir.exists():
            logger.debug("LUT directory does not exist: %s", self._lut_dir)
            return

        # Case-insensitive: match .cube, .CUBE, .Cube, etc.
        cube_files = sorted(
            set(self._lut_dir.glob("*.cube")) | set(self._lut_dir.glob("*.CUBE")),
            key=lambda p: p.stem.lower(),
        )
        for cube_file in cube_files:
            filter_id = cube_file.stem  # e.g. "film_noir"
            try:
                title, size, table = _parse_cube_file(cube_file)
                # Build Pillow Color3DLUT
                pil_lut = ImageFilter.Color3DLUT(
                    size=size,
                    table=table,
                )
                # Pre-compute OpenCV LUT (256-entry 1D approximation per channel)
                cv2_lut = self._build_cv2_lut(size, table)
                self._cache[filter_id] = (title, pil_lut, cv2_lut)
                logger.info("[LUT loaded] %s (%s, %dx%dx%d)", filter_id, title, size, size, size)
            except Exception as e:
                logger.warning("Failed to load LUT %s: %s", cube_file.name, e)

    @staticmethod
    def _build_cv2_lut(size: int, table: list[tuple[float, float, float]]) -> np.ndarray:
        """Build a 256-entry per-channel LUT from 3D LUT for fast preview.

        This is an approximation: we sample the 3D LUT along the neutral
        axis (R=G=B) and use per-channel 1D LUTs. It won't capture
        cross-channel effects perfectly, but it's fast enough for 15fps
        preview on a Raspberry Pi.
        """
        # Sample along the neutral axis (gray line)
        lut_1d = np.zeros((256, 3), dtype=np.uint8)
        for i in range(256):
            t = i / 255.0
            # Find the nearest 3D LUT entry for (t, t, t)
            ri = int(t * (size - 1) + 0.5)
            gi = int(t * (size - 1) + 0.5)
            bi = int(t * (size - 1) + 0.5)
            idx = ri + gi * size + bi * size * size
            if idx < len(table):
                r, g, b = table[idx]
                # Compute offset from identity
                lut_1d[i] = [
                    int(np.clip(r * 255, 0, 255)),
                    int(np.clip(g * 255, 0, 255)),
                    int(np.clip(b * 255, 0, 255)),
                ]
            else:
                lut_1d[i] = [i, i, i]

        # Build a 1x256x3 array for cv2.LUT (BGR order)
        # Input is BGR, so swap R and B
        bgr_lut = np.zeros((1, 256, 3), dtype=np.uint8)
        bgr_lut[0, :, 0] = lut_1d[:, 2]  # B channel
        bgr_lut[0, :, 1] = lut_1d[:, 1]  # G channel
        bgr_lut[0, :, 2] = lut_1d[:, 0]  # R channel
        return bgr_lut

    def available_luts(self) -> list[tuple[str, str]]:
        """Return list of (filter_id, display_title) for all discovered LUTs."""
        self._scan()
        return [(fid, data[0]) for fid, data in self._cache.items()]

    def has_lut(self, filter_id: str) -> bool:
        """Check if a LUT filter exists."""
        self._scan()
        return filter_id in self._cache

    def get_title(self, filter_id: str) -> str:
        """Get the display title for a LUT filter."""
        self._scan()
        if filter_id in self._cache:
            return self._cache[filter_id][0]
        return filter_id.replace("_", " ").title()

    def apply_pil(self, img: Image.Image, filter_id: str) -> Image.Image:
        """Apply a 3D LUT to a PIL Image (high quality, for final captures)."""
        self._scan()
        if filter_id not in self._cache:
            return img
        _, pil_lut, _ = self._cache[filter_id]
        if pil_lut is None:
            return img
        return img.filter(pil_lut)

    def apply_cv2(self, frame: np.ndarray, filter_id: str) -> np.ndarray:
        """Apply full 3D LUT to an OpenCV BGR frame via Pillow.

        Uses Pillow's C-implemented Color3DLUT with proper trilinear
        interpolation for accurate, smooth color grading in the live preview.
        """
        import cv2
        self._scan()
        if filter_id not in self._cache:
            return frame
        _, pil_lut, _ = self._cache[filter_id]
        if pil_lut is None:
            return frame
        # BGR → RGB → PIL → apply LUT → numpy → BGR
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        pil_img = pil_img.filter(pil_lut)
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    def apply_jpeg(self, jpeg_data: bytes, filter_id: str, *, quality: int = _OUTPUT_QUALITY) -> bytes:
        """Apply a 3D LUT to JPEG bytes (convenience wrapper)."""
        img = Image.open(io.BytesIO(jpeg_data)).convert("RGB")
        img = self.apply_pil(img, filter_id)
        return _to_jpeg(img, quality)


# Global singleton — initialized lazily
_lut_registry: LutRegistry | None = None


def get_lut_registry() -> LutRegistry:
    """Get or create the global LUT registry singleton."""
    global _lut_registry
    if _lut_registry is None:
        _lut_registry = LutRegistry()
    return _lut_registry


def auto_retouch(jpeg_data: bytes, *, quality: int = _OUTPUT_QUALITY) -> bytes:
    """Apply a subtle retouch: light blur + auto-contrast.

    The effect chain:
    1. Slight Gaussian blur (radius=1) — softens skin imperfections.
    2. ``ImageOps.autocontrast`` — stretches the histogram for
       punchier colours.

    Args:
        jpeg_data: Raw JPEG bytes of the input image.
        quality: JPEG quality for the output (default 92).

    Returns:
        Processed JPEG bytes.
    """
    img = Image.open(io.BytesIO(jpeg_data)).convert("RGB")

    # 1. Gentle smoothing — radius=1 is barely perceptible but flatters
    img = img.filter(ImageFilter.GaussianBlur(radius=1))

    # 2. Auto-contrast — stretches histogram, gives a "pop"
    img = ImageOps.autocontrast(img, cutoff=1)

    return _to_jpeg(img, quality)


def brightness_boost(
    jpeg_data: bytes,
    factor: float = 1.15,
    *,
    quality: int = _OUTPUT_QUALITY,
) -> bytes:
    """Increase perceived brightness.

    Args:
        jpeg_data: Raw JPEG bytes of the input image.
        factor: Brightness multiplier.  1.0 = no change, 1.15 = +15%.
        quality: JPEG quality for the output (default 92).

    Returns:
        Processed JPEG bytes.
    """
    img = Image.open(io.BytesIO(jpeg_data)).convert("RGB")
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(factor)

    return _to_jpeg(img, quality)


def apply_filter_to_jpeg(
    jpeg_data: bytes,
    filter_name: str,
    *,
    quality: int = _OUTPUT_QUALITY,
) -> bytes:
    """Apply a named LUT filter to JPEG bytes (high-quality).

    All filters are defined as .cube files in ``assets/luts/``.
    'none' (or legacy 'classic') means no filter — passthrough.

    Args:
        jpeg_data: Raw JPEG bytes.
        filter_name: LUT file stem (e.g. 'film_noir') or 'none'.
        quality: Output JPEG quality.

    Returns:
        Filtered JPEG bytes, or passthrough if no filter.
    """
    if filter_name in ("none", "classic", ""):
        return jpeg_data

    registry = get_lut_registry()
    if registry.has_lut(filter_name):
        return registry.apply_jpeg(jpeg_data, filter_name, quality=quality)

    logger.warning("[Filter not found] %s — passthrough", filter_name)
    return jpeg_data



# ---------------------------------------------------------------------------
# Glamour pipeline — modular stages
# ---------------------------------------------------------------------------

@dataclass
class GlamourParams:
    """Tuneable parameters for the glamour pipeline.

    All values are 0.0–1.0 intensity floats.
    A value of 0.0 disables that stage entirely.
    """

    skin_smooth: float = 0.7
    warmth: float = 0.5
    vignette: float = 0.5
    eye_enhance: float = 0.5
    makeup: float = 0.5
    sparkles: float = 0.3
    soft_glow: float = 0.4


def glamour_enhance(
    jpeg_data: bytes,
    params: GlamourParams | None = None,
    *,
    quality: int = _OUTPUT_QUALITY,
    preview: bool = False,
) -> bytes:
    """Modular glamour enhancement pipeline.

    Stages (each skipped if intensity == 0):
    1. Skin smoothing — bilateral filter with HSV skin-color mask
    2. Color grading — warmth shift + saturation boost + vignette
    3. Eye enhancement — local contrast/sharpness on detected eyes
    4. Makeup — lip tint + cheek blush
    5. Sparkles — subtle light particles overlay

    Args:
        jpeg_data: Raw JPEG bytes.
        params: Tuneable intensity values. Uses defaults if None.
        quality: Output JPEG quality.
        preview: If True, process at half resolution for speed.

    Returns:
        Enhanced JPEG bytes.
    """
    import cv2

    if params is None:
        params = GlamourParams()

    img = Image.open(io.BytesIO(jpeg_data)).convert("RGB")

    # Preview mode: scale down to half resolution for speed
    original_size = img.size
    if preview:
        img = img.resize(
            (img.width // 2, img.height // 2), Image.LANCZOS,
        )

    arr = np.array(img)
    h, w = arr.shape[:2]
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Detect faces once — shared by skin + eye + makeup stages
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
    )
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60),
    )

    # Stage 1: Skin smoothing
    if params.skin_smooth > 0:
        bgr = _glamour_skin_smooth(bgr, faces, h, w, params.skin_smooth)

    # Stage 2: Color grading (warmth + vignette)
    if params.warmth > 0 or params.vignette > 0:
        bgr = _glamour_color_grade(bgr, params.warmth, params.vignette)

    # Stage 3: Eye enhancement
    if params.eye_enhance > 0 and len(faces) > 0:
        bgr = _glamour_eye_enhance(bgr, faces, gray, params.eye_enhance)

    # Stage 4: Makeup (lip tint + blush)
    if params.makeup > 0 and len(faces) > 0:
        bgr = _glamour_makeup(bgr, faces, gray, params.makeup)

    # Stage 5: Orton soft glow (the classic glamour look)
    if params.soft_glow > 0:
        bgr = _glamour_soft_glow(bgr, params.soft_glow)

    # Stage 6: Sparkles overlay (last — on top of everything)
    if params.sparkles > 0:
        bgr = _glamour_sparkles(bgr, h, w, params.sparkles)

    logger.debug(
        "[Glamour pipeline] %d face(s), skin=%.1f warm=%.1f vig=%.1f eye=%.1f makeup=%.1f glow=%.1f sparkle=%.1f",
        len(faces), params.skin_smooth, params.warmth,
        params.vignette, params.eye_enhance, params.makeup,
        params.soft_glow, params.sparkles,
    )

    result = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result_img = Image.fromarray(result)

    # Scale back up to original size for preview mode
    if preview and result_img.size != original_size:
        result_img = result_img.resize(original_size, Image.LANCZOS)

    return _to_jpeg(result_img, quality)


def _glamour_skin_smooth(
    bgr: np.ndarray,
    faces,
    h: int,
    w: int,
    intensity: float,
) -> np.ndarray:
    """Smooth skin using bilateral filter with HSV skin-color mask.

    Only smooths pixels that match typical skin tones (HSV range),
    preventing the background and clothing from becoming blurry.

    Uses aggressive smoothing for a real glamour/magazine look.
    """
    import cv2

    if len(faces) == 0:
        # No face — apply subtle global smooth as fallback
        d = max(5, int(9 * intensity))
        sigma = int(50 * intensity)
        return cv2.bilateralFilter(bgr, d=d, sigmaColor=sigma, sigmaSpace=sigma)

    # Build skin-color mask in HSV — wider range for diverse skin tones
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # Extended skin range: H=0-28, S=30-180, V=60-255
    skin_mask = cv2.inRange(hsv, (0, 30, 60), (28, 180, 255))
    skin_mask = cv2.GaussianBlur(skin_mask, (9, 9), 4)

    for (fx, fy, fw, fh) in faces:
        # Expand ROI generously for forehead/neck
        pad_x, pad_y = int(fw * 0.20), int(fh * 0.30)
        x1, y1 = max(0, fx - pad_x), max(0, fy - pad_y)
        x2, y2 = min(w, fx + fw + pad_x), min(h, fy + fh + pad_y)

        face_roi = bgr[y1:y2, x1:x2].copy()
        roi_mask = skin_mask[y1:y2, x1:x2]

        # Stronger bilateral filter for glamour look
        d = max(7, int(12 * intensity))
        sigma = int(40 + 60 * intensity)
        smooth = cv2.bilateralFilter(face_roi, d=d, sigmaColor=sigma, sigmaSpace=sigma)

        # Apply bilateral a second time for extra-smooth skin at high intensity
        if intensity > 0.5:
            smooth = cv2.bilateralFilter(smooth, d=d, sigmaColor=sigma, sigmaSpace=int(sigma * 0.7))

        # Blend ratio — up to 90% smooth for that magazine look
        blend = min(0.92, intensity * 0.92)
        blended = cv2.addWeighted(smooth, blend, face_roi, 1 - blend, 0)

        # Apply only to skin pixels via feathered mask
        mask_f = (roi_mask / 255.0).astype(np.float32)
        mask_f = cv2.GaussianBlur(mask_f, (21, 21), 7)
        mask_3ch = mask_f[:, :, np.newaxis]

        bgr[y1:y2, x1:x2] = (
            blended * mask_3ch + face_roi * (1 - mask_3ch)
        ).astype(np.uint8)

    return bgr


def _glamour_color_grade(
    bgr: np.ndarray,
    warmth: float,
    vignette_strength: float,
) -> np.ndarray:
    """Apply warm color grading + vignette for a healthy glow.

    - Warmth: boosts red/orange tones, reduces blue — stronger than before
    - Vignette: darkens edges for focus on the center
    """
    import cv2

    h, w = bgr.shape[:2]

    # Warmth: shift R and G up, B down — more aggressive
    if warmth > 0:
        bgr_f = bgr.astype(np.float32)
        # BGR order: B=0, G=1, R=2  — stronger warm shift
        bgr_f[:, :, 2] = np.clip(bgr_f[:, :, 2] * (1.0 + 0.18 * warmth) + 6 * warmth, 0, 255)
        bgr_f[:, :, 1] = np.clip(bgr_f[:, :, 1] * (1.0 + 0.06 * warmth) + 3 * warmth, 0, 255)
        bgr_f[:, :, 0] = np.clip(bgr_f[:, :, 0] * (1.0 - 0.12 * warmth), 0, 255)

        # Stronger saturation boost in warm tones via HSV
        hsv = cv2.cvtColor(bgr_f.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
        warm_mask = (hsv[:, :, 0] < 30).astype(np.float32)
        hsv[:, :, 1] = np.clip(
            hsv[:, :, 1] * (1.0 + 0.22 * warmth * warm_mask), 0, 255,
        )
        # Slight overall brightness lift for that glowing look
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] + 4 * warmth, 0, 255)
        bgr = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # Vignette
    if vignette_strength > 0:
        bgr = _apply_vignette_cv(bgr, h, w, vignette_strength)

    return bgr


def _apply_vignette_cv(
    bgr: np.ndarray, h: int, w: int, strength: float,
) -> np.ndarray:
    """Apply a soft Gaussian vignette (OpenCV/BGR version)."""
    y = np.linspace(-1, 1, h, dtype=np.float32)
    x = np.linspace(-1, 1, w, dtype=np.float32)
    yy, xx = np.meshgrid(y, x, indexing="ij")
    dist = np.sqrt(xx ** 2 + yy ** 2)
    # Edge darkness scales with strength: 0.0 = no effect, 1.0 = max darkness
    edge_min = 1.0 - 0.6 * strength
    mask = np.clip(1.0 - dist * 0.45 * strength, edge_min, 1.0)
    return (bgr.astype(np.float32) * mask[:, :, np.newaxis]).astype(np.uint8)


def _glamour_eye_enhance(
    bgr: np.ndarray,
    faces,
    gray: np.ndarray,
    intensity: float,
) -> np.ndarray:
    """Enhance eyes: increase local contrast + sharpness around irises.

    Tries MediaPipe Face Mesh for precise eye landmarks (468 pts).
    Falls back to OpenCV Haar cascade if MediaPipe is unavailable.
    """
    import cv2

    # Try MediaPipe first (available on RPi4 with Python 3.11)
    try:
        return _eye_enhance_mediapipe(bgr, intensity)
    except ImportError:
        pass

    # Fallback: OpenCV Haar cascade eye detection
    eye_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_eye.xml",
    )

    for (fx, fy, fw, fh) in faces:
        # Search for eyes only in upper half of face
        eye_y1, eye_y2 = fy, fy + int(fh * 0.6)
        eye_x1, eye_x2 = fx, fx + fw
        face_upper = gray[eye_y1:eye_y2, eye_x1:eye_x2]

        eyes = eye_cascade.detectMultiScale(
            face_upper, scaleFactor=1.05, minNeighbors=4,
            minSize=(int(fw * 0.08), int(fh * 0.08)),
        )

        for (ex, ey, ew, eh) in eyes:
            # Map back to full image coords
            rx1 = eye_x1 + ex
            ry1 = eye_y1 + ey
            rx2 = rx1 + ew
            ry2 = ry1 + eh

            eye_roi = bgr[ry1:ry2, rx1:rx2].copy()
            if eye_roi.size == 0:
                continue

            # CLAHE for local contrast enhancement
            clahe = cv2.createCLAHE(
                clipLimit=1.5 + 2.5 * intensity, tileGridSize=(4, 4),
            )
            lab = cv2.cvtColor(eye_roi, cv2.COLOR_BGR2LAB)
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

            # Sharpen
            kernel = np.array([[0, -0.5, 0], [-0.5, 3, -0.5], [0, -0.5, 0]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)

            # Elliptical mask with soft edges (prevents square patches)
            mask = np.zeros((eh, ew), dtype=np.float32)
            cv2.ellipse(
                mask,
                center=(ew // 2, eh // 2),
                axes=(ew // 2 - 1, eh // 2 - 1),
                angle=0, startAngle=0, endAngle=360,
                color=1.0, thickness=-1,
            )
            mask = cv2.GaussianBlur(mask, (7, 7), 3)
            mask_3ch = mask[:, :, np.newaxis]

            # Blend with intensity using the soft mask
            alpha = mask_3ch * intensity * 0.6
            bgr[ry1:ry2, rx1:rx2] = (
                sharpened * alpha + eye_roi * (1 - alpha)
            ).astype(np.uint8)

    return bgr


def _eye_enhance_mediapipe(bgr: np.ndarray, intensity: float) -> np.ndarray:
    """Eye enhancement using MediaPipe Face Mesh (468 landmarks).

    Uses the precise eye contour landmarks for targeted enhancement.
    Only available with Python <= 3.12 (MediaPipe requirement).
    """
    import cv2
    import mediapipe as mp  # Raises ImportError on Python 3.13

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True, max_num_faces=4, min_detection_confidence=0.5,
    )

    # MediaPipe expects RGB
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)
    face_mesh.close()

    if not results.multi_face_landmarks:
        return bgr

    h, w = bgr.shape[:2]

    # MediaPipe eye landmark indices (left + right eye contours)
    LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
    RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]

    for face_landmarks in results.multi_face_landmarks:
        for eye_indices in [LEFT_EYE, RIGHT_EYE]:
            pts = np.array([
                (int(face_landmarks.landmark[i].x * w),
                 int(face_landmarks.landmark[i].y * h))
                for i in eye_indices
            ], dtype=np.int32)

            # Bounding box with padding
            ex1 = max(0, pts[:, 0].min() - 5)
            ey1 = max(0, pts[:, 1].min() - 5)
            ex2 = min(w, pts[:, 0].max() + 5)
            ey2 = min(h, pts[:, 1].max() + 5)

            eye_roi = bgr[ey1:ey2, ex1:ex2]
            if eye_roi.size == 0:
                continue

            # CLAHE + sharpen
            clahe = cv2.createCLAHE(
                clipLimit=1.5 + 2.5 * intensity, tileGridSize=(4, 4),
            )
            lab = cv2.cvtColor(eye_roi, cv2.COLOR_BGR2LAB)
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

            kernel = np.array([[0, -0.5, 0], [-0.5, 3, -0.5], [0, -0.5, 0]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)

            # Create eye-shaped mask from landmarks
            mask = np.zeros((ey2 - ey1, ex2 - ex1), dtype=np.float32)
            local_pts = pts - [ex1, ey1]
            cv2.fillPoly(mask, [local_pts], 1.0)
            mask = cv2.GaussianBlur(mask, (5, 5), 2)
            mask_3ch = mask[:, :, np.newaxis]

            bgr[ey1:ey2, ex1:ex2] = (
                sharpened * mask_3ch * intensity * 0.6
                + eye_roi * (1 - mask_3ch * intensity * 0.6)
            ).astype(np.uint8)

    return bgr


# ---------------------------------------------------------------------------
# Glamour: Makeup (lip tint + cheek blush)
# ---------------------------------------------------------------------------

def _glamour_makeup(
    bgr: np.ndarray,
    faces,
    gray: np.ndarray,
    intensity: float,
) -> np.ndarray:
    """Add subtle makeup effects: lip tint and cheek blush.

    Lip tint: Boosts red/pink in the lower third of the face.
    Blush: Adds a warm pink glow to the cheek areas.

    Uses HSV color space to target skin pixels and apply tinting
    without affecting non-skin areas (eyes, eyebrows, background).
    """
    import cv2

    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    for (fx, fy, fw, fh) in faces:
        # --- Lip tint: lower third of face ---
        lip_y1 = fy + int(fh * 0.60)
        lip_y2 = min(h, fy + fh + int(fh * 0.05))
        lip_x1 = fx + int(fw * 0.25)
        lip_x2 = fx + int(fw * 0.75)

        if lip_y2 > lip_y1 and lip_x2 > lip_x1:
            lip_roi = bgr[lip_y1:lip_y2, lip_x1:lip_x2].copy()
            lip_hsv = hsv[lip_y1:lip_y2, lip_x1:lip_x2]

            # Detect lip-like pixels: reddish skin with enough saturation
            lip_mask = cv2.inRange(lip_hsv, (0, 30, 60), (20, 200, 255))
            lip_mask = cv2.GaussianBlur(lip_mask, (7, 7), 3)
            lip_mask_f = (lip_mask / 255.0).astype(np.float32)
            lip_mask_f = cv2.GaussianBlur(lip_mask_f, (11, 11), 4)

            # Create lip tint: boost red channel, slightly reduce blue
            tinted = lip_roi.astype(np.float32)
            tint_strength = intensity * 0.45
            tinted[:, :, 2] = np.clip(tinted[:, :, 2] + 25 * tint_strength, 0, 255)  # R
            tinted[:, :, 1] = np.clip(tinted[:, :, 1] - 5 * tint_strength, 0, 255)   # G
            tinted[:, :, 0] = np.clip(tinted[:, :, 0] - 10 * tint_strength, 0, 255)  # B

            # Blend via mask — only lip-colored pixels get tinted
            mask_3ch = lip_mask_f[:, :, np.newaxis]
            bgr[lip_y1:lip_y2, lip_x1:lip_x2] = (
                tinted * mask_3ch + lip_roi.astype(np.float32) * (1 - mask_3ch)
            ).astype(np.uint8)

        # --- Cheek blush: mid-face, left and right of nose ---
        cheek_y_center = fy + int(fh * 0.55)
        cheek_radius = int(fw * 0.15)
        blush_offsets = [
            (fx + int(fw * 0.22), cheek_y_center),  # left cheek
            (fx + int(fw * 0.78), cheek_y_center),  # right cheek
        ]

        for (bx, by) in blush_offsets:
            by1 = max(0, by - cheek_radius)
            by2 = min(h, by + cheek_radius)
            bx1 = max(0, bx - cheek_radius)
            bx2 = min(w, bx + cheek_radius)

            if by2 <= by1 or bx2 <= bx1:
                continue

            blush_roi = bgr[by1:by2, bx1:bx2].copy()
            rh, rw = blush_roi.shape[:2]

            # Create soft circular mask for blush
            yy, xx = np.mgrid[:rh, :rw].astype(np.float32)
            cy, cx_local = rh / 2, rw / 2
            dist = np.sqrt((yy - cy) ** 2 + (xx - cx_local) ** 2)
            blush_mask = np.clip(1.0 - dist / max(cheek_radius, 1), 0, 1)
            blush_mask = cv2.GaussianBlur(blush_mask, (15, 15), 5)
            blush_mask *= intensity * 0.25  # Keep it subtle

            # Pink tint overlay: warm rosy color
            pink = blush_roi.astype(np.float32)
            pink[:, :, 2] = np.clip(pink[:, :, 2] + 30 * blush_mask, 0, 255)  # R
            pink[:, :, 1] = np.clip(pink[:, :, 1] + 8 * blush_mask, 0, 255)   # G slight
            pink[:, :, 0] = np.clip(pink[:, :, 0] + 12 * blush_mask, 0, 255)  # B slight

            bgr[by1:by2, bx1:bx2] = pink.astype(np.uint8)

    return bgr


# ---------------------------------------------------------------------------
# Glamour: Orton Soft Glow (classic glamour photography)
# ---------------------------------------------------------------------------

def _glamour_soft_glow(bgr: np.ndarray, intensity: float) -> np.ndarray:
    """Apply Orton soft glow — THE classic glamour photography technique.

    Creates a dreamy, ethereal look by blending the sharp original
    with a bright, heavily blurred version of itself.  This gives
    that luminous, magazine-quality appearance where highlights
    bloom softly and skin appears to glow from within.

    The technique was invented by Michael Orton for landscape
    photography but is now the hallmark of glamour portraits.
    """
    import cv2

    h, w = bgr.shape[:2]

    # Step 1: Brighten the image
    bright = cv2.convertScaleAbs(bgr, alpha=1.0 + 0.3 * intensity, beta=int(15 * intensity))

    # Step 2: Heavy Gaussian blur for the glow layer
    blur_size = max(3, int(31 * intensity)) | 1  # must be odd
    glow = cv2.GaussianBlur(bright, (blur_size, blur_size), 0)

    # Step 3: Multiply blend — original × glow for that luminous look
    # This creates the Orton effect: sharp details + soft glow
    orton = cv2.multiply(bgr.astype(np.float32) / 255.0,
                          glow.astype(np.float32) / 255.0)
    orton = np.clip(orton * 255 * 1.4, 0, 255).astype(np.uint8)

    # Step 4: Screen blend to recover brightness
    # screen(a, b) = 1 - (1-a)*(1-b)
    inv_bgr = 255 - bgr.astype(np.float32)
    inv_glow = 255 - glow.astype(np.float32)
    screen = 255 - (inv_bgr * inv_glow / 255.0)
    screen = np.clip(screen, 0, 255).astype(np.uint8)

    # Blend: mix original, Orton multiply, and screen
    # Low intensity: mostly original + slight glow
    # High intensity: dreamy, ethereal, full glamour
    alpha = intensity * 0.35  # Orton multiply contribution
    beta = intensity * 0.25   # Screen/bloom contribution
    gamma = 1.0 - alpha - beta  # Original contribution

    result = (
        bgr.astype(np.float32) * gamma
        + orton.astype(np.float32) * alpha
        + screen.astype(np.float32) * beta
    )

    return np.clip(result, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Glamour: Sparkles overlay
# ---------------------------------------------------------------------------

def _glamour_sparkles(
    bgr: np.ndarray,
    h: int,
    w: int,
    intensity: float,
) -> np.ndarray:
    """Overlay subtle light sparkles across the photo.

    Creates randomly positioned small bright dots with soft glow,
    giving a dreamy/magical look.  Uses a fixed seed per image
    size so sparkles are deterministic (no flicker on re-process).
    """
    import cv2

    # Fixed seed based on image dimensions for consistency
    rng = np.random.RandomState(seed=(h * w) % 2**31)

    # Number of sparkles scales with image size and intensity
    num_sparkles = int(15 + 45 * intensity)

    # Create sparkle overlay (additive)
    overlay = np.zeros_like(bgr, dtype=np.float32)

    for _ in range(num_sparkles):
        # Random position
        sx = rng.randint(int(w * 0.05), int(w * 0.95))
        sy = rng.randint(int(h * 0.05), int(h * 0.95))

        # Random sparkle size (small)
        radius = rng.randint(1, max(2, int(3 + 3 * intensity)))

        # Random brightness — some very bright, most subtle
        brightness = rng.uniform(0.3, 1.0) * intensity

        # Draw the sparkle as a soft glowing dot
        # Core bright dot
        cv2.circle(
            overlay, (sx, sy), radius,
            (brightness * 220, brightness * 230, brightness * 255),
            -1,
        )

    # Blur the overlay for soft glow effect
    if num_sparkles > 0:
        overlay = cv2.GaussianBlur(overlay, (7, 7), 2.5)

    # Add a few larger, very faint "star" sparkles
    num_stars = int(3 + 8 * intensity)
    for _ in range(num_stars):
        sx = rng.randint(int(w * 0.08), int(w * 0.92))
        sy = rng.randint(int(h * 0.08), int(h * 0.92))
        star_size = rng.randint(2, max(3, int(5 + 4 * intensity)))
        star_brightness = rng.uniform(0.15, 0.5) * intensity

        # Cross pattern for star shape
        half = star_size
        cv2.line(overlay, (sx - half, sy), (sx + half, sy),
                 (star_brightness * 200, star_brightness * 220, star_brightness * 255), 1)
        cv2.line(overlay, (sx, sy - half), (sx, sy + half),
                 (star_brightness * 200, star_brightness * 220, star_brightness * 255), 1)

    if num_stars > 0:
        # Second, gentler blur pass for the stars
        star_layer = cv2.GaussianBlur(overlay, (5, 5), 1.5)
        overlay = cv2.addWeighted(overlay, 0.7, star_layer, 0.3, 0)

    # Additive blend — sparkles only add light, never darken
    result = bgr.astype(np.float32) + overlay
    return np.clip(result, 0, 255).astype(np.uint8)


def _to_jpeg(img: Image.Image, quality: int) -> bytes:
    """Encode a PIL Image back to JPEG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

