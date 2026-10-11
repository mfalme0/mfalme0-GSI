"""Reference Forza Horizon telemetry page built from shared UI components."""

import customtkinter as ctk

from theme import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_PANEL,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    FONT_BODY,
    FONT_SIZE_MICRO,
    FONT_SIZE_SMALL,
    RADIUS_PANEL,
    SPACE_1,
    SPACE_2,
    SPACE_3,
)
from ui_components import ActivityLog, BridgeControls, ReadoutTile, RpmGauge, SettingsCard


class FH5TelemetryPage:
    """Standalone FH5/FH6 Sled telemetry page; bridge data enters via update()."""

    def __init__(self, master, settings, port_provider, on_start, on_stop):
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)
        self.last_readout = "Waiting for FH5 / FH6 telemetry"

        self.settings_card = SettingsCard(
            self.frame,
            "Connection settings",
            "UDP listener and Arduino serial connection",
            [
                ("fh5_host", "LISTEN ADDRESS", settings["fh5_host"], "text"),
                ("udp_port", "TELEMETRY UDP PORT", settings["udp_port"], "text"),
                ("fh5_serial", "ARDUINO COM PORT", settings["fh5_serial"], "port"),
                ("fh5_baud", "BAUD RATE", settings["fh5_baud"], "text"),
            ],
            port_provider,
        )
        self.settings_card.grid(row=0, column=0, sticky="new", pady=(0, SPACE_2))

        dashboard = ctk.CTkFrame(
            self.frame,
            fg_color=COLOR_PANEL,
            corner_radius=RADIUS_PANEL,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        dashboard.grid(row=1, column=0, sticky="nsew", pady=(0, SPACE_2))
        dashboard.grid_columnconfigure(0, weight=1, uniform="instrument")
        dashboard.grid_columnconfigure(1, weight=1, uniform="instrument")
        dashboard.grid_columnconfigure(2, weight=1, uniform="instrument")
        dashboard.grid_rowconfigure(0, weight=1)

        self.speed = ReadoutTile(dashboard, "Speed", "—", "km/h", hero=True)
        self.speed.grid(row=0, column=0, sticky="nsew", padx=(SPACE_3, SPACE_1), pady=SPACE_3)
        gauge_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        gauge_frame.grid(row=0, column=1, sticky="nsew", padx=SPACE_1, pady=SPACE_2)
        gauge_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            gauge_frame,
            text="ENGINE LOAD",
            font=(FONT_BODY, FONT_SIZE_MICRO, "bold"),
            text_color=COLOR_TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w", padx=SPACE_2)
        self.rpm_gauge = RpmGauge(gauge_frame, max_rpm=9000)
        self.rpm_gauge.grid(row=1, column=0, sticky="nsew")
        self.gear = ReadoutTile(dashboard, "Gear", "—", "")
        self.gear.grid(row=0, column=2, sticky="nsew", padx=(SPACE_1, SPACE_3), pady=SPACE_3)
        self.packet_label = ctk.CTkLabel(
            dashboard,
            text="VALID PACKETS  0",
            font=(FONT_BODY, FONT_SIZE_MICRO, "bold"),
            text_color=COLOR_TEXT_MUTED,
        )
        self.packet_label.grid(row=1, column=0, columnspan=3, sticky="e", padx=SPACE_3, pady=(0, SPACE_2))

        footer = ctk.CTkFrame(self.frame, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="nsew")
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=2)
        self.controls = BridgeControls(
            footer,
            on_start=on_start,
            on_stop=on_stop,
        )
        self.controls.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_2))
        self.activity = ActivityLog(footer)
        self.activity.grid(row=0, column=1, sticky="nsew", padx=(SPACE_2, 0))

    @property
    def fields(self):
        return self.settings_card.fields

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def tkraise(self):
        self.frame.tkraise()

    def update(self, data):
        speed = int(data["speed"])
        rpm = int(data["rpm"])
        gear = int(data["gear"])
        packets = int(data["packets"])
        gear_text = "R" if gear < 0 else "N" if gear == 0 else str(gear)
        self.speed.set_value(f"{speed:>3}")
        self.rpm_gauge.set_rpm(rpm)
        self.gear.set_value(gear_text)
        self.packet_label.configure(text=f"VALID PACKETS  {packets:,}")
        self.last_readout = f"{speed} km/h   ·   {rpm:,} RPM   ·   GEAR {gear_text}"

    def set_state(self, state):
        self.controls.set_state(state)

    def append_log(self, message):
        self.activity.append(message)

    def refresh_ports(self):
        self.settings_card.refresh_ports()
