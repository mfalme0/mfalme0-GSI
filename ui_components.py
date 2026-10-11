"""Reusable, compact dashboard controls and readouts."""

import time
import tkinter as tk

import customtkinter as ctk

from theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_BUTTON,
    COLOR_ACCENT_BUTTON_TEXT,
    COLOR_ACCENT_SOFT,
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_FIELD,
    COLOR_FIELD_HOVER,
    COLOR_GAUGE_REDLINE,
    COLOR_GAUGE_TRACK,
    COLOR_PANEL,
    COLOR_PANEL_HOVER,
    COLOR_PANEL_RAISED,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_TEXT_LOG,
    COLOR_TEXT_MUTED,
    FONT_BODY,
    FONT_MONO,
    FONT_SIZE_BODY,
    FONT_SIZE_HERO_READOUT,
    FONT_SIZE_MICRO,
    FONT_SIZE_READOUT,
    FONT_SIZE_SMALL,
    RADIUS_CONTROL,
    RADIUS_PANEL,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
)


class StatusBadge(ctk.CTkFrame):
    """Small status indicator with explicit running, stopped, and error states."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_PANEL,
            corner_radius=RADIUS_CONTROL,
            border_width=1,
            border_color=COLOR_BORDER,
            **kwargs,
        )
        self.label = ctk.CTkLabel(
            self,
            text="STOPPED",
            font=(FONT_BODY, FONT_SIZE_SMALL, "bold"),
            text_color=COLOR_TEXT_MUTED,
        )
        self.label.pack(padx=SPACE_3, pady=SPACE_2)
        self.set_state("Stopped")

    def set_state(self, state):
        normalized = state.casefold()
        if normalized == "running":
            text, color, fill = "RUNNING", COLOR_SUCCESS, COLOR_ACCENT_SOFT
        elif normalized.startswith("starting"):
            text, color, fill = "STARTING", COLOR_ACCENT, COLOR_ACCENT_SOFT
        elif normalized == "error":
            text, color, fill = "ERROR", COLOR_ERROR, COLOR_PANEL
        else:
            text, color, fill = "STOPPED", COLOR_TEXT_MUTED, COLOR_PANEL
        self.label.configure(text=text, text_color=color)
        self.configure(fg_color=fill, border_color=color if normalized == "error" else COLOR_BORDER)


class SettingsCard(ctk.CTkFrame):
    """Panel that builds labeled connection fields and refreshable COM ports."""

    def __init__(self, master, title, description, fields, port_provider, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_PANEL,
            corner_radius=RADIUS_PANEL,
            border_width=1,
            border_color=COLOR_BORDER,
            **kwargs,
        )
        self.port_provider = port_provider
        self.fields = {}
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=title.upper(),
            font=(FONT_BODY, FONT_SIZE_SMALL, "bold"),
            text_color=COLOR_TEXT,
        ).grid(row=0, column=0, sticky="w", padx=SPACE_4, pady=(SPACE_2, 0))
        ctk.CTkLabel(
            self,
            text=description,
            font=(FONT_BODY, FONT_SIZE_SMALL),
            text_color=COLOR_TEXT_MUTED,
            height=18,
            anchor="w",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=SPACE_4, pady=(SPACE_1, SPACE_2))

        field_row = ctk.CTkFrame(self, fg_color="transparent")
        field_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=SPACE_4)
        field_row.grid_columnconfigure(tuple(range(len(fields))), weight=1, uniform="settings")
        for column, spec in enumerate(fields):
            key, label, value, kind = spec
            field = ctk.CTkFrame(field_row, fg_color="transparent")
            field.grid(row=0, column=column, sticky="ew", padx=(0, SPACE_2))
            ctk.CTkLabel(
                field,
                text=label.upper(),
                font=(FONT_BODY, FONT_SIZE_MICRO, "bold"),
                text_color=COLOR_TEXT_MUTED,
                height=18,
                anchor="w",
            ).pack(anchor="w", pady=(0, SPACE_1))
            if kind == "port":
                ports = self.port_provider()
                widget = ctk.CTkComboBox(
                    field,
                    values=ports or [value],
                    height=34,
                    font=(FONT_MONO, FONT_SIZE_SMALL),
                    fg_color=COLOR_FIELD,
                    border_color=COLOR_BORDER,
                    button_color=COLOR_PANEL_RAISED,
                    button_hover_color=COLOR_FIELD_HOVER,
                    dropdown_fg_color=COLOR_PANEL,
                    dropdown_hover_color=COLOR_PANEL_RAISED,
                    corner_radius=RADIUS_CONTROL,
                )
                widget.set(value)
            else:
                widget = ctk.CTkEntry(
                    field,
                    height=34,
                    font=(FONT_MONO, FONT_SIZE_SMALL),
                    fg_color=COLOR_FIELD,
                    border_color=COLOR_BORDER,
                    text_color=COLOR_TEXT,
                    corner_radius=RADIUS_CONTROL,
                    show="*" if kind == "secret" else "",
                )
                widget.insert(0, value)
            widget.pack(fill="x")
            self.fields[key] = widget

        self.refresh_button = ctk.CTkButton(
            self,
            text="↻  REFRESH COM PORTS",
            width=172,
            height=28,
            fg_color=COLOR_PANEL_RAISED,
            hover_color=COLOR_PANEL_HOVER,
            text_color=COLOR_ACCENT,
            font=(FONT_BODY, FONT_SIZE_MICRO, "bold"),
            corner_radius=RADIUS_CONTROL,
            command=self.refresh_ports,
        )
        self.refresh_button.grid(
            row=0, column=1, sticky="e", padx=SPACE_4, pady=(SPACE_2, 0)
        )
        self._port_field = next(
            (widget for key, widget in self.fields.items() if key.endswith("_serial")),
            None,
        )
        if self._port_field is None:
            self.refresh_button.configure(state="disabled")

    def refresh_ports(self):
        if self._port_field is None:
            return
        ports = self.port_provider()
        current = self._port_field.get()
        values = ports or ["No ports found"]
        if current and current not in values:
            values.append(current)
        self._port_field.configure(values=values)


class ReadoutTile(ctk.CTkFrame):
    """Fixed-width, monospace telemetry tile for glanceable live values."""

    def __init__(self, master, label, value="—", unit="", hero=False, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_FIELD,
            corner_radius=RADIUS_CONTROL,
            border_width=1,
            border_color=COLOR_BORDER,
            **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=label.upper(),
            font=(FONT_BODY, FONT_SIZE_MICRO, "bold"),
            text_color=COLOR_TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w", padx=SPACE_3, pady=(SPACE_3, 0))
        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=(FONT_MONO, FONT_SIZE_HERO_READOUT if hero else FONT_SIZE_READOUT, "bold"),
            text_color=COLOR_ACCENT,
            anchor="w",
        )
        self.value_label.grid(row=1, column=0, sticky="ew", padx=SPACE_3, pady=(SPACE_1, 0))
        if unit:
            ctk.CTkLabel(
                self,
                text=unit.upper(),
                font=(FONT_BODY, FONT_SIZE_MICRO, "bold"),
                text_color=COLOR_TEXT_MUTED,
            ).grid(row=2, column=0, sticky="w", padx=SPACE_3, pady=(0, SPACE_2))
        else:
            self.grid_rowconfigure(1, weight=1)
            self.value_label.grid_configure(rowspan=2, sticky="w")

    def set_value(self, value):
        self.value_label.configure(text=str(value))


class ColorSwatch(ctk.CTkFrame):
    """Canvas-backed, resizable color preview for OpenRGB integrations."""

    def __init__(self, master, width=180, height=140, color=COLOR_PANEL_RAISED, **kwargs):
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=COLOR_PANEL,
            corner_radius=RADIUS_CONTROL,
            **kwargs,
        )
        self._color = color
        self.grid_propagate(False)
        self.canvas = tk.Canvas(
            self,
            background=COLOR_PANEL,
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill="both", expand=True, padx=SPACE_2, pady=SPACE_2)
        self.canvas.bind("<Configure>", lambda _event: self._draw_swatch())
        self._draw_swatch()

    def set_color(self, color):
        self._color = color
        self._draw_swatch()

    def _draw_swatch(self):
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.canvas.create_rectangle(
            1,
            1,
            width - 1,
            height - 1,
            fill=self._color,
            outline=COLOR_BORDER,
            width=1,
        )


class RpmGauge(tk.Canvas):
    """Canvas-drawn RPM arc with a subdued track and clear redline."""

    def __init__(self, master, max_rpm=9000, **kwargs):
        super().__init__(
            master,
            background=COLOR_PANEL,
            highlightthickness=0,
            height=120,
            **kwargs,
        )
        self.max_rpm = max_rpm
        self.rpm = 0
        self.bind("<Configure>", lambda _event: self._draw())
        self._draw()

    def set_rpm(self, rpm):
        self.rpm = max(0, min(self.max_rpm, int(rpm)))
        self._draw()

    def _draw(self):
        self.delete("all")
        width, height = max(self.winfo_width(), 220), max(self.winfo_height(), 120)
        inset = 18
        diameter = min(width - 2 * inset, height - 12)
        left = (width - diameter) / 2
        top = (height - diameter) / 2
        bounds = (left, top, left + diameter, top + diameter)
        self.create_arc(
            *bounds,
            start=135,
            extent=-270,
            style="arc",
            outline=COLOR_GAUGE_TRACK,
            width=14,
        )
        progress = self.rpm / self.max_rpm
        if progress:
            self.create_arc(
                *bounds,
                start=135,
                extent=-270 * progress,
                style="arc",
                outline=COLOR_ACCENT if progress < 0.88 else COLOR_GAUGE_REDLINE,
                width=14,
            )
        self.create_text(
            width / 2,
            height * 0.46,
            text=f"{self.rpm:,}",
            fill=COLOR_TEXT,
            font=(FONT_MONO, FONT_SIZE_READOUT, "bold"),
        )
        self.create_text(
            width / 2,
            height * 0.68,
            text=f"RPM  /  {self.max_rpm // 1000}K",
            fill=COLOR_TEXT_MUTED,
            font=(FONT_BODY, FONT_SIZE_MICRO, "bold"),
        )


class ActivityLog(ctk.CTkFrame):
    """Timestamped, bounded scrolling log with a monospace typeface."""

    def __init__(self, master, title="ACTIVITY", max_lines=250, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_PANEL,
            corner_radius=RADIUS_PANEL,
            border_width=1,
            border_color=COLOR_BORDER,
            **kwargs,
        )
        self.max_lines = max_lines
        self.textbox = ctk.CTkTextbox(
            self,
            height=70,
            fg_color=COLOR_FIELD,
            text_color=COLOR_TEXT_LOG,
            font=(FONT_MONO, FONT_SIZE_SMALL),
            corner_radius=RADIUS_CONTROL,
            border_width=1,
            border_color=COLOR_BORDER,
            scrollbar_button_color=COLOR_GAUGE_TRACK,
            scrollbar_button_hover_color=COLOR_ACCENT,
        )
        ctk.CTkLabel(
            self,
            text=title,
            font=(FONT_BODY, FONT_SIZE_SMALL, "bold"),
            text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_3, pady=(SPACE_2, SPACE_1))
        self.textbox.pack(fill="both", expand=True, padx=SPACE_2, pady=(0, SPACE_2))
        self.textbox.configure(state="disabled")

    def append(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.textbox.configure(state="normal")
        self.textbox.insert("end", f"{timestamp}  {message}\n")
        line_count = int(self.textbox.index("end-1c").split(".")[0])
        excess = line_count - self.max_lines
        if excess > 0:
            self.textbox.delete("1.0", f"{excess + 1}.0")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")


class BridgeControls(ctk.CTkFrame):
    """Status badge and start/stop controls with state-aware button gating."""

    def __init__(self, master, on_start, on_stop, description="", **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_PANEL,
            corner_radius=RADIUS_PANEL,
            border_width=1,
            border_color=COLOR_BORDER,
            **kwargs,
        )
        self.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(
            self,
            text="BRIDGE CONTROL",
            font=(FONT_BODY, FONT_SIZE_SMALL, "bold"),
            text_color=COLOR_TEXT,
            height=20,
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=SPACE_3, pady=(SPACE_2, 0))
        if description:
            ctk.CTkLabel(
                self,
                text=description,
                font=(FONT_BODY, FONT_SIZE_SMALL),
                text_color=COLOR_TEXT_MUTED,
                height=18,
                anchor="w",
            ).grid(row=1, column=0, columnspan=2, sticky="w", padx=SPACE_3, pady=(SPACE_1, 0))
        self.badge = StatusBadge(self)
        badge_row = 2 if description else 1
        self.badge.grid(row=badge_row, column=0, columnspan=2, sticky="w", padx=SPACE_3, pady=SPACE_2)
        self.start_button = ctk.CTkButton(
            self,
            text="START BRIDGE",
            command=on_start,
            height=36,
            fg_color=COLOR_ACCENT_BUTTON,
            hover_color=COLOR_ACCENT,
            text_color=COLOR_ACCENT_BUTTON_TEXT,
            font=(FONT_BODY, FONT_SIZE_SMALL, "bold"),
            corner_radius=RADIUS_CONTROL,
        )
        self.start_button.grid(
            row=badge_row + 1, column=0, sticky="ew", padx=(SPACE_3, SPACE_1), pady=(0, SPACE_2)
        )
        self.stop_button = ctk.CTkButton(
            self,
            text="STOP",
            command=on_stop,
            height=36,
            fg_color=COLOR_PANEL_RAISED,
            hover_color=COLOR_PANEL_HOVER,
            text_color=COLOR_TEXT,
            font=(FONT_BODY, FONT_SIZE_SMALL, "bold"),
            corner_radius=RADIUS_CONTROL,
            state="disabled",
        )
        self.stop_button.grid(
            row=badge_row + 1, column=1, sticky="ew", padx=(SPACE_1, SPACE_3), pady=(0, SPACE_2)
        )

    def set_state(self, state):
        normalized = state.casefold()
        active = normalized not in ("stopped", "error")
        self.badge.set_state(state)
        self.start_button.configure(state="disabled" if active else "normal")
        self.stop_button.configure(state="normal" if active else "disabled")


class PersistentStatusStrip(ctk.CTkFrame):
    """Bottom-of-window bridge identity, state, and glanceable key readout."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=COLOR_PANEL,
            corner_radius=RADIUS_CONTROL,
            border_width=1,
            border_color=COLOR_BORDER,
            **kwargs,
        )
        self.grid_columnconfigure(1, weight=1)
        self.source = ctk.CTkLabel(
            self,
            text="NO ACTIVE BRIDGE",
            font=(FONT_BODY, FONT_SIZE_SMALL, "bold"),
            text_color=COLOR_TEXT_MUTED,
        )
        self.source.grid(row=0, column=0, sticky="w", padx=SPACE_3, pady=SPACE_2)
        self.state = ctk.CTkLabel(
            self,
            text="STOPPED",
            font=(FONT_BODY, FONT_SIZE_SMALL, "bold"),
            text_color=COLOR_TEXT_MUTED,
        )
        self.state.grid(row=0, column=1, sticky="w", padx=SPACE_2, pady=SPACE_2)
        self.readout = ctk.CTkLabel(
            self,
            text="Waiting for a bridge",
            font=(FONT_MONO, FONT_SIZE_SMALL),
            text_color=COLOR_TEXT,
            anchor="e",
        )
        self.readout.grid(row=0, column=2, sticky="e", padx=SPACE_3, pady=SPACE_2)

    def set_bridge(self, name, state, readout):
        color = (
            COLOR_SUCCESS
            if state.casefold() == "running"
            else COLOR_ERROR
            if state.casefold() == "error"
            else COLOR_TEXT_MUTED
        )
        self.source.configure(text=name.upper(), text_color=color)
        self.state.configure(text=state.upper(), text_color=color)
        self.readout.configure(text=readout)

    def clear(self):
        self.source.configure(text="NO ACTIVE BRIDGE", text_color=COLOR_TEXT_MUTED)
        self.state.configure(text="STOPPED", text_color=COLOR_TEXT_MUTED)
        self.readout.configure(text="Waiting for a bridge")
