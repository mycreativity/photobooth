"""Reusable UI components for the photobooth.

This is the photobooth design system — all interactive and display components
are defined here with consistent theming, sizing, and touch behaviour.

Components:
- ``BoothButton``: Rounded button with themed background, touch feedback,
  and optional toggle state.
- ``BoothCard``: Rounded card container for layout/filter selection.
- ``BoothIconButton``: Small icon-sized button (for +/- steppers, arrows).
- ``BoothSlider``: Horizontal slider for settings values (0.0–1.0).
- ``BoothKeyboard``: Full-screen on-screen keyboard for text input on
  touchscreen devices.

All components accept a ``ThemeData`` instance and draw themselves
accordingly.  They are Kivy ``FloatLayout`` subclasses that can be
placed with ``size_hint`` and ``pos_hint`` like any other widget.
"""

from __future__ import annotations

from kivy.animation import Animation
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from photobooth.ui.themes import ThemeData


# ---------------------------------------------------------------------------
# BoothButton — primary interactive button
# ---------------------------------------------------------------------------

class BoothButton(FloatLayout):
    """Themed rounded button with touch feedback and strong visual affordance.

    All graphics (glow, border, fill) are drawn on ``self.canvas.before``
    and tracked via ``self.bind(pos=..., size=...)``.  This guarantees
    correct rendering at any position — no child-widget sync issues.

    Variants:
    - ``"primary"`` — Accent-coloured background with outer glow, bold
      white text. Use for the main call-to-action (e.g. "Accept", "Done").
    - ``"secondary"`` — Surface-coloured background with a visible border
      in the primary colour. Clearly reads as a clickable button.
    - ``"ghost"`` — Transparent background with a subtle muted border.
      Use for low-priority actions (e.g. "Back").

    Usage::

        btn = BoothButton(
            text="Accept",
            theme=theme,
            variant="primary",
            on_press=lambda: print("pressed!"),
            size_hint=(0.3, 0.08),
            pos_hint={"center_x": 0.5, "center_y": 0.1},
        )
        screen.add_widget(btn)
    """

    def __init__(
        self,
        text: str,
        theme: ThemeData,
        variant: str = "secondary",
        on_press=None,
        toggled: bool = False,
        font_size: str | None = None,
        radius: int = 16,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._theme = theme
        self._variant = variant
        self._on_press = on_press
        self._toggled = toggled
        self._radius = radius

        # Resolve colours
        self._bg_color_normal = self._resolve_bg_color(variant)
        self._bg_color_toggled = theme.colors.primary
        self._border_color_normal = self._resolve_border_color(variant)
        self._border_color_toggled = theme.colors.primary
        self._text_color = self._resolve_text_color(variant)
        self._text_color_toggled = (1, 1, 1, 1)  # White on accent

        # Determine active state
        active_bg = self._bg_color_toggled if toggled else self._bg_color_normal
        active_border = self._border_color_toggled if toggled else self._border_color_normal
        active_text = self._text_color_toggled if toggled else self._text_color

        # --- Draw all layers on self.canvas.before ---
        # This ensures graphics track self.pos/self.size correctly.
        self._has_glow = (variant == "primary")
        with self.canvas.before:
            # Layer 1: Glow (primary only)
            if self._has_glow:
                glow_color = (*theme.colors.accent[:3], 0.25)
                self._glow_color_instr = Color(*glow_color)
                self._glow_rect = RoundedRectangle(
                    pos=(0, 0), size=(0, 0), radius=[radius + 6],
                )

            # Layer 2: Border ring
            self._border_color_instr = Color(*active_border)
            self._border_rect = RoundedRectangle(
                pos=(0, 0), size=(0, 0), radius=[radius],
            )

            # Layer 3: Fill (inset from border)
            self._bg_color_instr = Color(*active_bg)
            self._bg_rect = RoundedRectangle(
                pos=(0, 0), size=(0, 0), radius=[radius - 1],
            )

        # Bind to own pos/size — always correct after layout
        self.bind(pos=self._sync_graphics, size=self._sync_graphics)

        # --- Label ---
        resolved_font = font_size or theme.typography.button_size
        self._label = Label(
            text=text,
            font_size=resolved_font,
            bold=True,
            color=active_text,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self.add_widget(self._label)

    def _resolve_bg_color(self, variant: str):
        t = self._theme
        if variant == "primary":
            return t.colors.accent
        elif variant == "ghost":
            return (0, 0, 0, 0)  # Transparent
        else:  # secondary
            # Slightly lighter than pure surface to lift off the background
            s = t.colors.surface
            return (s[0] + 0.03, s[1] + 0.03, s[2] + 0.04, s[3])

    def _resolve_border_color(self, variant: str):
        t = self._theme
        if variant == "primary":
            # Slightly brighter accent for border
            a = t.colors.accent
            return (min(1.0, a[0] + 0.1), min(1.0, a[1] + 0.1), min(1.0, a[2] + 0.1), 0.9)
        elif variant == "ghost":
            # Muted, subtle border
            return (*t.colors.text_muted[:3], 0.3)
        else:  # secondary
            # Visible border in the primary/accent colour
            return (*t.colors.primary[:3], 0.55)

    def _resolve_text_color(self, variant: str):
        t = self._theme
        if variant == "primary":
            return (1, 1, 1, 1)  # Pure white on accent fill
        elif variant == "ghost":
            return t.colors.primary_light
        else:  # secondary
            return t.colors.text

    def _sync_graphics(self, *_args) -> None:
        """Reposition all canvas layers to match current widget geometry."""
        x, y, w, h = self.x, self.y, self.width, self.height

        # Glow — extends 5px beyond button on each side
        if self._has_glow:
            pad = 5
            self._glow_rect.pos = (x - pad, y - pad)
            self._glow_rect.size = (w + pad * 2, h + pad * 2)

        # Border — exact widget bounds
        self._border_rect.pos = (x, y)
        self._border_rect.size = (w, h)

        # Fill — inset 2px to reveal border ring
        inset = 2
        self._bg_rect.pos = (x + inset, y + inset)
        self._bg_rect.size = (w - inset * 2, h - inset * 2)

    @property
    def text(self) -> str:
        return self._label.text

    @text.setter
    def text(self, value: str) -> None:
        self._label.text = value

    @property
    def toggled(self) -> bool:
        return self._toggled

    @toggled.setter
    def toggled(self, value: bool) -> None:
        self._toggled = value
        if value:
            self._bg_color_instr.rgba = self._bg_color_toggled
            self._border_color_instr.rgba = self._border_color_toggled
            self._label.color = self._text_color_toggled
        else:
            self._bg_color_instr.rgba = self._bg_color_normal
            self._border_color_instr.rgba = self._border_color_normal
            self._label.color = self._text_color

    @property
    def variant(self) -> str:
        return self._variant

    @variant.setter
    def variant(self, value: str) -> None:
        self._variant = value

    def _update_colors(self) -> None:
        """Re-resolve all colours based on current variant/toggled state.

        Call this after changing ``.variant`` to update the visual appearance.
        """
        self._bg_color_normal = self._resolve_bg_color(self._variant)
        self._border_color_normal = self._resolve_border_color(self._variant)
        self._text_color = self._resolve_text_color(self._variant)

        if self._toggled:
            self._bg_color_instr.rgba = self._bg_color_toggled
            self._border_color_instr.rgba = self._border_color_toggled
            self._label.color = self._text_color_toggled
        else:
            self._bg_color_instr.rgba = self._bg_color_normal
            self._border_color_instr.rgba = self._border_color_normal
            self._label.color = self._text_color

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        # Visual press feedback — quick dim
        Animation.cancel_all(self, "opacity")
        self.opacity = 0.7
        return True

    def on_touch_up(self, touch):
        if self.opacity < 1.0:
            Animation(opacity=1.0, duration=0.15).start(self)
        if self.collide_point(*touch.pos) and self._on_press:
            self._on_press()
            return True
        return super().on_touch_up(touch)


# ---------------------------------------------------------------------------
# BoothCard — selection card (layout/filter pickers)
# ---------------------------------------------------------------------------

class BoothCard(FloatLayout):
    """Themed rounded card for selection grids.

    Used for layout and filter selection screens.  Supports an optional
    ``icon_drawer`` callback that receives the card's canvas to draw
    a custom icon.

    Usage::

        card = BoothCard(
            text="Grid",
            theme=theme,
            on_press=lambda: select_grid(),
            size_hint=(0.25, 0.5),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
    """

    def __init__(
        self,
        text: str,
        theme: ThemeData,
        on_press=None,
        icon_drawer=None,
        radius: int = 16,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._theme = theme
        self._on_press = on_press

        # Background
        self._bg_widget = Widget(size_hint=(1, 1))
        with self._bg_widget.canvas.before:
            Color(*theme.colors.surface)
            self._bg_rect = RoundedRectangle(
                pos=(0, 0), size=(0, 0), radius=[radius],
            )
        self._bg_widget.bind(
            pos=self._sync_bg, size=self._sync_bg,
        )
        self.add_widget(self._bg_widget)

        # Icon area (if icon_drawer provided, drawn after layout)
        self._icon_widget = None
        if icon_drawer:
            self._icon_widget = Widget(
                size_hint=(0.5, 0.4),
                pos_hint={"center_x": 0.5, "center_y": 0.6},
            )
            self._icon_drawer = icon_drawer
            self._icon_widget.bind(
                pos=self._draw_icon, size=self._draw_icon,
            )
            self.add_widget(self._icon_widget)

        # Label at the bottom of the card
        self._label = Label(
            text=text,
            font_size=theme.typography.body_size,
            bold=True,
            color=theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.18},
        )
        self.add_widget(self._label)

    def _sync_bg(self, *_args) -> None:
        self._bg_rect.pos = self._bg_widget.pos
        self._bg_rect.size = self._bg_widget.size

    def _draw_icon(self, *_args) -> None:
        if not self._icon_widget:
            return
        w = self._icon_widget
        w.canvas.after.clear()
        self._icon_drawer(w, w.x, w.y, w.width, w.height)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        Animation.cancel_all(self, "opacity")
        self.opacity = 0.7
        return True

    def on_touch_up(self, touch):
        if self.opacity < 1.0:
            Animation(opacity=1.0, duration=0.15).start(self)
        if self.collide_point(*touch.pos) and self._on_press:
            self._on_press()
            return True
        return super().on_touch_up(touch)


# ---------------------------------------------------------------------------
# BoothIconButton — small icon button (+/- steppers, cycle arrows)
# ---------------------------------------------------------------------------

class BoothIconButton(FloatLayout):
    """Small themed button for icons/symbols.

    Used for stepper controls (+/-) and cycle buttons (arrows).
    Draws border + fill directly on self.canvas.before for
    correct positioning.

    Usage::

        btn = BoothIconButton(
            text="+",
            theme=theme,
            on_press=lambda: increment(),
            size_hint=(0.06, 0.05),
        )
    """

    def __init__(
        self,
        text: str,
        theme: ThemeData,
        on_press=None,
        font_size: str = "22sp",
        radius: int = 10,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._on_press = on_press

        # Draw border + fill on self.canvas.before
        with self.canvas.before:
            # Border
            self._border_color_instr = Color(*theme.colors.primary[:3], 0.4)
            self._border_rect = RoundedRectangle(
                pos=(0, 0), size=(0, 0), radius=[radius],
            )
            # Fill
            Color(*theme.colors.surface)
            self._fill_rect = RoundedRectangle(
                pos=(0, 0), size=(0, 0), radius=[radius - 1],
            )

        self.bind(pos=self._sync, size=self._sync)

        self.add_widget(Label(
            text=text,
            font_size=font_size,
            bold=True,
            color=theme.colors.text,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        ))

    def _sync(self, *_args) -> None:
        self._border_rect.pos = self.pos
        self._border_rect.size = self.size
        inset = 1.5
        self._fill_rect.pos = (self.x + inset, self.y + inset)
        self._fill_rect.size = (self.width - inset * 2, self.height - inset * 2)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        Animation.cancel_all(self, "opacity")
        self.opacity = 0.7
        return True

    def on_touch_up(self, touch):
        if self.opacity < 1.0:
            Animation(opacity=1.0, duration=0.15).start(self)
        if self.collide_point(*touch.pos) and self._on_press:
            self._on_press()
            return True
        return super().on_touch_up(touch)


# ---------------------------------------------------------------------------
# BoothSlider — horizontal slider for settings values
# ---------------------------------------------------------------------------

class BoothSlider(FloatLayout):
    """Themed horizontal slider with value label.

    Provides a draggable slider that maps to a 0.0–1.0 float value.
    The track has a rounded background, an accent-colored fill bar,
    and a circular drag handle.

    Args:
        label: Text label shown to the left.
        value: Initial value (0.0–1.0).
        theme: ThemeData for consistent styling.
        on_change: Callback ``(float) -> None`` called when value changes.
    """

    def __init__(
        self,
        label: str = "",
        value: float = 0.5,
        theme: ThemeData | None = None,
        on_change=None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._value = max(0.0, min(1.0, value))
        self._on_change = on_change
        self._theme = theme
        self._dragging = False

        # Colors
        track_color = theme.colors.surface if theme else (0.2, 0.2, 0.25, 1)
        fill_color = theme.colors.primary if theme else (0.7, 0.55, 0.35, 1)
        text_color = theme.colors.text if theme else (1, 1, 1, 1)

        # Label (left side)
        self._label = Label(
            text=label,
            font_size="16sp",
            bold=True,
            color=text_color,
            halign="left",
            text_size=(None, None),
            size_hint=(0.35, 1.0),
            pos_hint={"x": 0.0, "center_y": 0.5},
        )
        self.add_widget(self._label)

        # Value label (right side)
        self._value_label = Label(
            text=f"{int(self._value * 100)}%",
            font_size="15sp",
            bold=True,
            color=fill_color,
            size_hint=(0.12, 1.0),
            pos_hint={"right": 1.0, "center_y": 0.5},
        )
        self.add_widget(self._value_label)

        # Track area (canvas-drawn)
        self._track = Widget(
            size_hint=(0.48, 0.35),
            pos_hint={"x": 0.37, "center_y": 0.5},
        )

        with self._track.canvas:
            # Track background
            self._track_color = Color(*track_color[:3], 0.6)
            self._track_rect = RoundedRectangle(
                pos=(0, 0), size=(0, 0), radius=[6],
            )
            # Fill
            self._fill_color = Color(*fill_color[:3], 0.9)
            self._fill_rect = RoundedRectangle(
                pos=(0, 0), size=(0, 0), radius=[6],
            )
            # Handle
            self._handle_color = Color(1, 1, 1, 1)
            from kivy.graphics import Ellipse
            self._handle = Ellipse()

        self._track.bind(pos=self._update_track, size=self._update_track)
        self.add_widget(self._track)

    def _update_track(self, *_args) -> None:
        """Redraw track, fill bar, and handle based on current value."""
        t = self._track
        if t.width <= 1:
            return

        # Track background — full width
        self._track_rect.pos = t.pos
        self._track_rect.size = t.size

        # Fill bar — proportional to value
        fill_w = max(6, t.width * self._value)
        self._fill_rect.pos = t.pos
        self._fill_rect.size = (fill_w, t.height)

        # Handle — circle at the fill edge
        handle_r = t.height * 0.65
        hx = t.x + fill_w - handle_r / 2
        hy = t.center_y - handle_r / 2
        self._handle.pos = (hx, hy)
        self._handle.size = (handle_r, handle_r)

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = max(0.0, min(1.0, v))
        self._value_label.text = f"{int(self._value * 100)}%"
        self._update_track()

    def on_touch_down(self, touch):
        if self._track.collide_point(*touch.pos):
            self._dragging = True
            self._update_value_from_touch(touch)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._dragging:
            self._update_value_from_touch(touch)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._dragging:
            self._dragging = False
            self._update_value_from_touch(touch)
            return True
        return super().on_touch_up(touch)

    def _update_value_from_touch(self, touch) -> None:
        """Map touch X position to 0.0–1.0 value."""
        t = self._track
        if t.width <= 1:
            return
        rel = (touch.x - t.x) / t.width
        new_val = max(0.0, min(1.0, rel))
        if abs(new_val - self._value) > 0.005:
            self._value = new_val
            self._value_label.text = f"{int(self._value * 100)}%"
            self._update_track()
            if self._on_change:
                self._on_change(self._value)


# ---------------------------------------------------------------------------
# BoothKeyboard — full-screen on-screen keyboard
# ---------------------------------------------------------------------------

# Keyboard layout: rows of keys.  Special keys use _ACTION_ prefix.
_KB_ROWS = [
    list("1234567890"),
    list("QWERTYUIOP"),
    list("ASDFGHJKL"),
    ["_SHIFT_", *list("ZXCVBNM"), "_BACK_"],
    ["_SPACE_", "_DONE_"],
]


class BoothKeyboard(FloatLayout):
    """Full-screen on-screen keyboard for touchscreen text input.

    Designed for Raspberry Pi photobooth — large touch targets, minimal
    layout, themed styling.  Overlays the entire screen when shown.

    Usage::

        def on_done(text):
            print(f"User typed: {text}")

        keyboard = BoothKeyboard(
            theme=theme,
            on_done=on_done,
            on_cancel=lambda: print("cancelled"),
            placeholder="Event name",
            initial_text="",
        )
        screen.add_widget(keyboard)

    The keyboard auto-removes itself on Done or Cancel.
    """

    def __init__(
        self,
        theme: ThemeData,
        on_done=None,
        on_cancel=None,
        placeholder: str = "",
        initial_text: str = "",
        **kwargs,
    ) -> None:
        kwargs.setdefault("size_hint", (1, 1))
        kwargs.setdefault("pos_hint", {"center_x": 0.5, "center_y": 0.5})
        super().__init__(**kwargs)
        self._theme = theme
        self._on_done = on_done
        self._on_cancel = on_cancel
        self._text = initial_text
        self._placeholder = placeholder
        self._shifted = False

        # Full-screen dark background
        with self.canvas.before:
            Color(*theme.colors.background[:3], 0.97)
            self._bg_rect = RoundedRectangle(pos=(0, 0), size=(0, 0))
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        # --- Text display area (top 20%) ---
        self._text_label = Label(
            text=self._text or self._placeholder,
            font_size="36sp",
            bold=True,
            color=theme.colors.text if self._text else theme.colors.text_muted,
            halign="center",
            valign="middle",
            size_hint=(0.9, 0.10),
            pos_hint={"center_x": 0.5, "center_y": 0.88},
        )
        self._text_label.bind(size=self._text_label.setter("text_size"))
        self.add_widget(self._text_label)

        # Underline / cursor indicator
        self._cursor = Widget(
            size_hint=(0.6, None),
            height=3,
            pos_hint={"center_x": 0.5, "center_y": 0.82},
        )
        with self._cursor.canvas:
            Color(*theme.colors.primary[:3], 0.8)
            self._cursor_rect = RoundedRectangle(
                pos=(0, 0), size=(0, 0), radius=[2],
            )
        self._cursor.bind(pos=self._sync_cursor, size=self._sync_cursor)
        self.add_widget(self._cursor)

        # --- Cancel button (top-left) ---
        self.add_widget(BoothButton(
            text="X",
            theme=theme,
            variant="ghost",
            on_press=self._cancel,
            size_hint=(0.08, 0.06),
            pos_hint={"x": 0.02, "center_y": 0.95},
        ))

        # --- Build keyboard grid (bottom 70%) ---
        self._key_widgets: list[BoothButton] = []
        self._build_keys()

    def _sync_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _sync_cursor(self, *_args) -> None:
        self._cursor_rect.pos = self._cursor.pos
        self._cursor_rect.size = self._cursor.size

    def _build_keys(self) -> None:
        """Create all keyboard key buttons."""
        theme = self._theme

        # 5 rows from y=0.65 down to y=0.08
        row_positions = [0.68, 0.56, 0.44, 0.32, 0.16]
        row_height = 0.09

        for row_idx, row_keys in enumerate(_KB_ROWS):
            cy = row_positions[row_idx]
            n_keys = len(row_keys)

            # Calculate key widths
            if row_idx == 4:  # Bottom row: space + done
                # Space takes most of the width
                self._build_special_row(cy, row_height, theme)
                continue

            key_w = min(0.085, 0.90 / n_keys)
            gap = 0.006
            total_w = n_keys * key_w + (n_keys - 1) * gap
            start_x = (1.0 - total_w) / 2

            for i, key in enumerate(row_keys):
                kx = start_x + i * (key_w + gap) + key_w / 2

                if key == "_SHIFT_":
                    btn = BoothButton(
                        text="^",
                        theme=theme, variant="ghost",
                        on_press=self._toggle_shift,
                        size_hint=(key_w, row_height),
                        pos_hint={"center_x": kx, "center_y": cy},
                        font_size="18sp",
                    )
                elif key == "_BACK_":
                    btn = BoothButton(
                        text="<",
                        theme=theme, variant="ghost",
                        on_press=self._backspace,
                        size_hint=(key_w, row_height),
                        pos_hint={"center_x": kx, "center_y": cy},
                        font_size="18sp",
                    )
                else:
                    display = key if self._shifted else key.lower()
                    btn = BoothButton(
                        text=display,
                        theme=theme, variant="secondary",
                        on_press=lambda k=key: self._press_key(k),
                        size_hint=(key_w, row_height),
                        pos_hint={"center_x": kx, "center_y": cy},
                        font_size="18sp",
                    )

                self._key_widgets.append(btn)
                self.add_widget(btn)

    def _build_special_row(self, cy: float, row_height: float, theme: ThemeData) -> None:
        """Build the bottom row: space bar + done button."""
        # Space bar
        space = BoothButton(
            text="SPATIE",
            theme=theme, variant="secondary",
            on_press=lambda: self._press_key(" "),
            size_hint=(0.55, row_height),
            pos_hint={"center_x": 0.35, "center_y": cy},
            font_size="16sp",
        )
        self._key_widgets.append(space)
        self.add_widget(space)

        # Done button
        done = BoothButton(
            text="DONE",
            theme=theme, variant="primary",
            on_press=self._done,
            size_hint=(0.25, row_height),
            pos_hint={"center_x": 0.75, "center_y": cy},
            font_size="18sp",
        )
        self._key_widgets.append(done)
        self.add_widget(done)

    def _press_key(self, key: str) -> None:
        """Handle a regular key press."""
        char = key if self._shifted else key.lower()
        self._text += char
        self._update_display()

        # Auto-disable shift after one key press
        if self._shifted:
            self._shifted = False
            self._update_key_labels()

    def _backspace(self) -> None:
        """Remove the last character."""
        if self._text:
            self._text = self._text[:-1]
            self._update_display()

    def _toggle_shift(self) -> None:
        """Toggle shift (uppercase) mode."""
        self._shifted = not self._shifted
        self._update_key_labels()

    def _update_key_labels(self) -> None:
        """Update key labels to reflect shift state."""
        for btn in self._key_widgets:
            txt = btn.text
            if len(txt) == 1 and txt.isalpha():
                btn.text = txt.upper() if self._shifted else txt.lower()

    def _update_display(self) -> None:
        """Update the text display label."""
        if self._text:
            self._text_label.text = self._text
            self._text_label.color = self._theme.colors.text
        else:
            self._text_label.text = self._placeholder
            self._text_label.color = self._theme.colors.text_muted

    def _done(self) -> None:
        """Confirm and pass text back via callback."""
        text = self._text.strip()
        if self._on_done:
            self._on_done(text)
        self._remove_self()

    def _cancel(self) -> None:
        """Cancel and dismiss without passing text."""
        if self._on_cancel:
            self._on_cancel()
        self._remove_self()

    def _remove_self(self) -> None:
        """Remove the keyboard from its parent."""
        if self.parent:
            self.parent.remove_widget(self)

    @property
    def text(self) -> str:
        return self._text

