import math
import queue
import socket
import sys
import threading
import time
from http.server import HTTPServer
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
import serial
from serial.tools import list_ports
from openrgb.utils import RGBColor

from beamng import parse_outgauge_packet
from cs2rgb import (
    DEFAULT_GSI_HOST,
    DEFAULT_GSI_PORT,
    DEFAULT_OPENRGB_HOST,
    DEFAULT_OPENRGB_PORT,
    OpenRGBGameController,
    create_handler,
)
from dota2 import health_color as dota_health_color
from leagueoflegends import HTTPError, URLError, fetch_live_data, health_color as lol_health_color
from lcdfh5 import parse_fh5_telemetry
from rocketleague import color_for_event, decode_event, extract_json_messages


APP_NAME = "FH Sensor Studio"
BG = "#080E19"
SIDEBAR = "#0B1321"
PANEL = "#101A2A"
PANEL_LIGHT = "#172438"
FIELD = "#0B1422"
BORDER = "#1C2B40"
TEXT = "#EFF5FA"
MUTED = "#8799AC"
ACCENT = "#52E0C0"
ACCENT_SOFT = "#12332F"
GREEN = "#52E0A0"
RED = "#FF687D"
ORANGE = "#FFC46B"
FONT = "Segoe UI"
FONT_DISPLAY = "Segoe UI Variable Display"


class BridgeApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1220x820")
        self.minsize(1040, 720)
        self.configure(fg_color=BG)
        icon_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        icon_path = icon_dir / "assets" / "fhsensor.ico"
        if icon_path.is_file():
            self.iconbitmap(str(icon_path))

        self.events = queue.Queue()
        self.workers = {}
        self.active_page = "fh5"
        self.settings = self._load_settings()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._process_events)

    def _load_settings(self):
        defaults = {
            "fh5_serial": "COM9",
            "fh5_baud": "9600",
            "udp_port": "5300",
            "rgb_serial": "COM10",
            "rgb_baud": "115200",
            "openrgb_host": "localhost",
            "openrgb_port": "6745",
            "rgb_interval": "0.1",
            "cs2_gsi_port": str(DEFAULT_GSI_PORT),
            "cs2_openrgb_host": DEFAULT_OPENRGB_HOST,
            "cs2_openrgb_port": str(DEFAULT_OPENRGB_PORT),
            "beamng_serial": "COM11",
            "beamng_baud": "9600",
            "beamng_udp_port": "4444",
            "rocket_serial": "COM12",
            "rocket_baud": "115200",
            "rocket_port": "49123",
            "rocket_player": "",
            "dota_gsi_port": "53001",
            "dota_openrgb_host": DEFAULT_OPENRGB_HOST,
            "dota_openrgb_port": str(DEFAULT_OPENRGB_PORT),
            "lol_openrgb_host": DEFAULT_OPENRGB_HOST,
            "lol_openrgb_port": str(DEFAULT_OPENRGB_PORT),
            "lol_poll_interval": "0.5",
        }
        try:
            from pathlib import Path
            import json
            import os

            path = Path(os.environ.get("APPDATA", Path.home())) / "FHSensorStudio" / "settings.json"
            if path.exists():
                saved = json.loads(path.read_text(encoding="utf-8"))
                defaults.update({key: str(value) for key, value in saved.items() if key in defaults})
            self.settings_path = path
        except (OSError, ValueError) as exc:
            self.settings_path = None
            print(f"Could not load settings: {exc}")
        return defaults

    def _save_settings(self):
        if self.settings_path is None:
            return
        try:
            import json

            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(self._current_settings(), indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Settings not saved", f"Could not save settings:\n{exc}")

    def _current_settings(self):
        return {
            "fh5_serial": self.fh5_serial.get(),
            "fh5_baud": self.fh5_baud.get(),
            "udp_port": self.udp_port.get(),
            "rgb_serial": self.rgb_serial.get(),
            "rgb_baud": self.rgb_baud.get(),
            "openrgb_host": self.openrgb_host.get(),
            "openrgb_port": self.openrgb_port.get(),
            "rgb_interval": self.rgb_interval.get(),
            "cs2_gsi_port": self.cs2_gsi_port.get(),
            "cs2_openrgb_host": self.cs2_openrgb_host.get(),
            "cs2_openrgb_port": self.cs2_openrgb_port.get(),
            "beamng_serial": self.beamng_serial.get(),
            "beamng_baud": self.beamng_baud.get(),
            "beamng_udp_port": self.beamng_udp_port.get(),
            "rocket_serial": self.rocket_serial.get(),
            "rocket_baud": self.rocket_baud.get(),
            "rocket_port": self.rocket_port.get(),
            "rocket_player": self.rocket_player.get(),
            "dota_gsi_port": self.dota_gsi_port.get(),
            "dota_openrgb_host": self.dota_openrgb_host.get(),
            "dota_openrgb_port": self.dota_openrgb_port.get(),
            "lol_openrgb_host": self.lol_openrgb_host.get(),
            "lol_openrgb_port": self.lol_openrgb_port.get(),
            "lol_poll_interval": self.lol_poll_interval.get(),
        }

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=256, corner_radius=0, fg_color=SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(24, 20))
        mark = ctk.CTkFrame(brand, width=42, height=42, corner_radius=13, fg_color=ACCENT_SOFT)
        mark.pack(side="left", padx=(0, 11))
        mark.pack_propagate(False)
        ctk.CTkLabel(mark, text="F", font=(FONT_DISPLAY, 24, "bold"), text_color=ACCENT).pack(expand=True)
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(brand_text, text="FH SENSOR", font=(FONT_DISPLAY, 16, "bold"), text_color=TEXT).pack(
            anchor="w", pady=(2, 0)
        )
        ctk.CTkLabel(brand_text, text="GAME SYNC STUDIO", font=(FONT, 9, "bold"), text_color=MUTED).pack(
            anchor="w", pady=(1, 0)
        )
        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).pack(fill="x", padx=20, pady=(0, 16))

        nav = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#26364A",
            scrollbar_button_hover_color=ACCENT,
        )
        nav.pack(fill="both", expand=True, padx=(8, 4), pady=(0, 10))
        self.nav_fh5 = self._nav_button(nav, "◈    FORZA HORIZON 5 / 6", self._show_fh5)
        self.nav_beamng = self._nav_button(nav, "◈    BEAMNG.DRIVE", lambda: self._show_game("beamng"))
        self.nav_rocket = self._nav_button(nav, "◈    ROCKET LEAGUE", lambda: self._show_game("rocket"))
        self.nav_cs2 = self._nav_button(nav, "◈    COUNTER-STRIKE 2", self._show_cs2)
        self.nav_dota = self._nav_button(nav, "◈    DOTA 2", lambda: self._show_game("dota"))
        self.nav_lol = self._nav_button(nav, "◈    LEAGUE OF LEGENDS", lambda: self._show_game("lol"))
        self.nav_rgb = self._nav_button(nav, "◈    OPENRGB STREAM", self._show_rgb)
        for text in ("RACING", "ARENA", "LIGHTING"):
            ctk.CTkLabel(nav, text=text, font=(FONT, 9, "bold"), text_color="#60738B").pack(
                anchor="w", padx=15, pady=(12, 5)
            )
            group = {
                "RACING": (self.nav_fh5, self.nav_beamng, self.nav_rocket),
                "ARENA": (self.nav_cs2, self.nav_dota, self.nav_lol),
                "LIGHTING": (self.nav_rgb,),
            }[text]
            for button in group:
                button.pack(fill="x", padx=4, pady=2)

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(4, 17))
        ctk.CTkFrame(footer, height=1, fg_color=BORDER).pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            footer,
            text="LOCAL GAME DATA  ·  v1.0",
            font=(FONT, 9, "bold"),
            text_color="#60738B",
        ).pack(anchor="w")
        ctk.CTkLabel(
            footer,
            text="Telemetry stays on this PC",
            font=(FONT, 10),
            text_color=MUTED,
        ).pack(anchor="w", pady=(5, 0))

        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=(30, 34), pady=(26, 28))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 23))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="YOUR WORKSPACE  /  GAME LIGHTING", font=(FONT, 9, "bold"), text_color=ACCENT
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.heading = ctk.CTkLabel(
            header, text="Forza Horizon 5 / 6", font=(FONT_DISPLAY, 29, "bold"), text_color=TEXT
        )
        self.heading.grid(row=1, column=0, sticky="w")
        self.subtitle = ctk.CTkLabel(
            header, text="Live game telemetry to your Arduino", font=(FONT, 12), text_color=MUTED
        )
        self.subtitle.grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.status_pill = ctk.CTkFrame(
            header, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER
        )
        self.status_pill.grid(row=1, column=1, rowspan=2, sticky="e", padx=(12, 0))
        self.header_status = ctk.CTkLabel(
            self.status_pill, text="●  BRIDGE STOPPED", font=(FONT, 10, "bold"), text_color=MUTED
        )
        self.header_status.pack(padx=13, pady=9)
        ctk.CTkFrame(main, height=1, fg_color=BORDER).grid(row=1, column=0, sticky="ew", pady=(0, 20))

        self.pages = ctk.CTkFrame(main, fg_color="transparent")
        self.pages.grid(row=2, column=0, sticky="nsew")
        self.pages.grid_columnconfigure(0, weight=1)
        self.pages.grid_rowconfigure(0, weight=1)
        self.fh5_page = self._build_fh5_page(self.pages)
        self.rgb_page = self._build_rgb_page(self.pages)
        self.cs2_page = self._build_cs2_page(self.pages)
        self.game_ui = {}
        self.beamng_page = self._build_integration_page(
            self.pages,
            "beamng",
            "BeamNG.drive",
            "OutGauge UDP telemetry to your Arduino",
            [
                ("beamng_serial", "ARDUINO PORT", True, None),
                ("beamng_baud", "BAUD RATE", False, None),
                ("beamng_udp_port", "OUTGAUGE UDP PORT", False, None),
            ],
            "LIVE OUTGAUGE",
            "Vehicle speed, RPM, and gear from BeamNG.drive",
            "Stream vehicle telemetry to the Arduino",
            telemetry=True,
        )
        self.rocket_page = self._build_integration_page(
            self.pages,
            "rocket",
            "Rocket League",
            "Match events and boost color to your Arduino",
            [
                ("rocket_serial", "ARDUINO PORT", True, None),
                ("rocket_baud", "BAUD RATE", False, None),
                ("rocket_port", "LOCAL TCP PORT", False, None),
                ("rocket_player", "PLAYER NAME (OPTIONAL)", False, None),
            ],
            "LIVE MATCH COLOR",
            "Match goals and player boost level",
            "Send Rocket League colors to the Arduino",
        )
        self.dota_page = self._build_integration_page(
            self.pages,
            "dota",
            "Dota 2",
            "Game State Integration to OpenRGB",
            [
                ("dota_gsi_port", "LOCAL GSI HTTP PORT", False, None),
                ("dota_openrgb_host", "OPENRGB HOST", False, None),
                ("dota_openrgb_port", "OPENRGB SDK PORT", False, None),
                ("dota_secret", "GSI TOKEN (NOT SAVED)", False, "*"),
            ],
            "LIVE HERO STATE",
            "OpenRGB color reacts to your hero's health",
            "Receive authenticated Dota 2 game state",
        )
        self.lol_page = self._build_integration_page(
            self.pages,
            "lol",
            "League of Legends",
            "Local Live Client Data API to OpenRGB",
            [
                ("lol_openrgb_host", "OPENRGB HOST", False, None),
                ("lol_openrgb_port", "OPENRGB SDK PORT", False, None),
                ("lol_poll_interval", "POLL INTERVAL (SEC)", False, None),
            ],
            "LIVE CHAMPION STATE",
            "OpenRGB color reacts to your champion's health",
            "Poll the local LoL Live Client Data API",
        )
        self.fh5_page.grid(row=0, column=0, sticky="nsew")
        self.rgb_page.grid(row=0, column=0, sticky="nsew")
        self.cs2_page.grid(row=0, column=0, sticky="nsew")
        self.beamng_page.grid(row=0, column=0, sticky="nsew")
        self.rocket_page.grid(row=0, column=0, sticky="nsew")
        self.dota_page.grid(row=0, column=0, sticky="nsew")
        self.lol_page.grid(row=0, column=0, sticky="nsew")
        self._show_fh5()

    def _nav_button(self, parent, text, command):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            anchor="w",
            height=40,
            corner_radius=9,
            fg_color="transparent",
            hover_color="#152337",
            text_color=MUTED,
            font=(FONT, 10, "bold"),
        )

    def _build_fh5_page(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)

        settings_card = self._card(page)
        settings_card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self._card_title(
            settings_card, "CONNECTION SETTINGS", "Configure FH5 / FH6 UDP telemetry and the Arduino serial link"
        )
        fields = ctk.CTkFrame(settings_card, fg_color="transparent")
        fields.pack(fill="x", padx=20, pady=(12, 18))
        fields.grid_columnconfigure((0, 1, 2), weight=1)
        self.fh5_serial = self._field(fields, "ARDUINO PORT", self.settings["fh5_serial"], 0, 0, combo=True)
        self.fh5_baud = self._field(fields, "BAUD RATE", self.settings["fh5_baud"], 0, 1)
        self.udp_port = self._field(fields, "TELEMETRY UDP PORT", self.settings["udp_port"], 0, 2)
        self._refresh_ports_button(settings_card, 0)

        content = ctk.CTkFrame(page, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)
        metrics = self._card(content)
        metrics.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._card_title(metrics, "LIVE TELEMETRY", "Values update when FH5 sends a valid Sled packet")
        metric_grid = ctk.CTkFrame(metrics, fg_color="transparent")
        metric_grid.pack(fill="both", expand=True, padx=18, pady=(12, 16))
        metric_grid.grid_columnconfigure((0, 1, 2), weight=1)
        self.speed_value = self._metric(metric_grid, "SPEED", "—", "km/h", 0)
        self.rpm_value = self._metric(metric_grid, "ENGINE", "—", "RPM", 1)
        self.gear_value = self._metric(metric_grid, "GEAR", "—", "GEAR", 2)
        self.packet_value = ctk.CTkLabel(metrics, text="Packets received: 0", font=("Segoe UI", 11), text_color=MUTED)
        self.packet_value.pack(anchor="w", padx=22, pady=(0, 18))

        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        control = self._card(right)
        control.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self._card_title(control, "BRIDGE CONTROL", "Start listening and stream values to the board")
        self.fh5_state = ctk.CTkLabel(control, text="●  Stopped", text_color=MUTED, font=("Segoe UI", 12, "bold"))
        self.fh5_state.pack(anchor="w", padx=20, pady=(14, 12))
        actions = ctk.CTkFrame(control, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 18))
        self.fh5_start = self._action_button(actions, "Start bridge", lambda: self._start("fh5"), primary=True)
        self.fh5_start.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.fh5_stop = self._action_button(actions, "Stop", lambda: self._stop("fh5"), state="disabled")
        self.fh5_stop.pack(side="left", fill="x", expand=True, padx=(5, 0))

        log_card = self._card(right)
        log_card.grid(row=1, column=0, sticky="nsew")
        self._card_title(log_card, "ACTIVITY", "Connection and runtime messages")
        self.fh5_log = self._log(log_card)
        return page

    def _build_rgb_page(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        settings_card = self._card(page)
        settings_card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self._card_title(settings_card, "CONNECTION SETTINGS", "OpenRGB SDK server and Arduino serial link")
        fields = ctk.CTkFrame(settings_card, fg_color="transparent")
        fields.pack(fill="x", padx=20, pady=(12, 18))
        fields.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.rgb_serial = self._field(fields, "ARDUINO PORT", self.settings["rgb_serial"], 0, 0, combo=True)
        self.rgb_baud = self._field(fields, "BAUD RATE", self.settings["rgb_baud"], 0, 1)
        self.openrgb_host = self._field(fields, "OPENRGB HOST", self.settings["openrgb_host"], 0, 2)
        self.openrgb_port = self._field(fields, "SDK PORT", self.settings["openrgb_port"], 0, 3)
        self.rgb_interval = self._field(fields, "UPDATE INTERVAL (SEC)", self.settings["rgb_interval"], 1, 0)
        self._refresh_ports_button(settings_card, 1)

        content = ctk.CTkFrame(page, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)
        preview = self._card(content)
        preview.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._card_title(preview, "LIVE COLOR", "Average RGB color from the first detected OpenRGB device")
        color_body = ctk.CTkFrame(preview, fg_color="transparent")
        color_body.pack(fill="both", expand=True, padx=20, pady=(8, 18))
        color_body.grid_columnconfigure(0, weight=1)
        color_body.grid_rowconfigure(0, weight=1)
        self.color_swatch = ctk.CTkFrame(color_body, width=180, height=140, corner_radius=18, fg_color="#263149")
        self.color_swatch.grid(row=0, column=0, sticky="nsew", pady=(0, 14))
        self.color_swatch.grid_propagate(False)
        self.color_value = ctk.CTkLabel(color_body, text="R  —     G  —     B  —", font=("Segoe UI", 18, "bold"), text_color=TEXT)
        self.color_value.grid(row=1, column=0, pady=(0, 6))
        self.device_value = ctk.CTkLabel(color_body, text="No device connected", font=("Segoe UI", 11), text_color=MUTED)
        self.device_value.grid(row=2, column=0)

        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        control = self._card(right)
        control.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self._card_title(control, "BRIDGE CONTROL", "Stream average device color to the board")
        self.rgb_state = ctk.CTkLabel(control, text="●  Stopped", text_color=MUTED, font=("Segoe UI", 12, "bold"))
        self.rgb_state.pack(anchor="w", padx=20, pady=(14, 12))
        actions = ctk.CTkFrame(control, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 18))
        self.rgb_start = self._action_button(actions, "Start bridge", lambda: self._start("rgb"), primary=True)
        self.rgb_start.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.rgb_stop = self._action_button(actions, "Stop", lambda: self._stop("rgb"), state="disabled")
        self.rgb_stop.pack(side="left", fill="x", expand=True, padx=(5, 0))
        log_card = self._card(right)
        log_card.grid(row=1, column=0, sticky="nsew")
        self._card_title(log_card, "ACTIVITY", "Connection and runtime messages")
        self.rgb_log = self._log(log_card)
        return page

    def _build_cs2_page(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        settings_card = self._card(page)
        settings_card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self._card_title(
            settings_card,
            "CS2 GAME STATE INTEGRATION",
            "Local-only GSI listener and OpenRGB connection",
        )
        fields = ctk.CTkFrame(settings_card, fg_color="transparent")
        fields.pack(fill="x", padx=20, pady=(12, 8))
        fields.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.cs2_gsi_port = self._field(
            fields, "GSI HTTP PORT", self.settings["cs2_gsi_port"], 0, 0
        )
        self.cs2_openrgb_host = self._field(
            fields, "OPENRGB HOST", self.settings["cs2_openrgb_host"], 0, 1
        )
        self.cs2_openrgb_port = self._field(
            fields, "OPENRGB SDK PORT", self.settings["cs2_openrgb_port"], 0, 2
        )
        self.cs2_secret = self._field(
            fields, "GSI AUTH KEY (NOT SAVED)", "", 0, 3, show="*"
        )
        ctk.CTkLabel(
            settings_card,
            text="Bind address is restricted to 127.0.0.1. The auth key is required and stays in memory only.",
            font=("Segoe UI", 10),
            text_color=ORANGE,
        ).pack(anchor="w", padx=20, pady=(0, 15))

        content = ctk.CTkFrame(page, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)
        preview = self._card(content)
        preview.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._card_title(
            preview,
            "CS2 LIGHTING",
            "Health, round events, bomb state, kills, and flash effects",
        )
        color_body = ctk.CTkFrame(preview, fg_color="transparent")
        color_body.pack(fill="both", expand=True, padx=20, pady=(8, 18))
        color_body.grid_columnconfigure(0, weight=1)
        color_body.grid_rowconfigure(0, weight=1)
        self.cs2_color_swatch = ctk.CTkFrame(
            color_body, width=180, height=140, corner_radius=18, fg_color="#263149"
        )
        self.cs2_color_swatch.grid(row=0, column=0, sticky="nsew", pady=(0, 14))
        self.cs2_color_swatch.grid_propagate(False)
        self.cs2_color_value = ctk.CTkLabel(
            color_body, text="Waiting for CS2", font=("Segoe UI", 18, "bold"), text_color=TEXT
        )
        self.cs2_color_value.grid(row=1, column=0, pady=(0, 6))
        self.cs2_event_value = ctk.CTkLabel(
            color_body, text="No game state received", font=("Segoe UI", 11), text_color=MUTED
        )
        self.cs2_event_value.grid(row=2, column=0)

        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        control = self._card(right)
        control.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self._card_title(control, "BRIDGE CONTROL", "Receive authenticated CS2 game events")
        self.cs2_state = ctk.CTkLabel(
            control, text="●  Stopped", text_color=MUTED, font=("Segoe UI", 12, "bold")
        )
        self.cs2_state.pack(anchor="w", padx=20, pady=(14, 12))
        actions = ctk.CTkFrame(control, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 18))
        self.cs2_start = self._action_button(
            actions, "Start bridge", lambda: self._start("cs2"), primary=True
        )
        self.cs2_start.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.cs2_stop = self._action_button(actions, "Stop", lambda: self._stop("cs2"), state="disabled")
        self.cs2_stop.pack(side="left", fill="x", expand=True, padx=(5, 0))
        log_card = self._card(right)
        log_card.grid(row=1, column=0, sticky="nsew")
        self._card_title(log_card, "ACTIVITY", "GSI and OpenRGB connection status")
        self.cs2_log = self._log(log_card)
        return page

    def _build_integration_page(
        self,
        parent,
        mode,
        title,
        description,
        fields_spec,
        preview_title,
        preview_description,
        control_description,
        telemetry=False,
    ):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        settings_card = self._card(page)
        settings_card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self._card_title(settings_card, "CONNECTION SETTINGS", description)
        fields = ctk.CTkFrame(settings_card, fg_color="transparent")
        fields.pack(fill="x", padx=20, pady=(12, 14))
        field_count = min(len(fields_spec), 4)
        fields.grid_columnconfigure(tuple(range(field_count)), weight=1)
        for index, (key, label, combo, show) in enumerate(fields_spec):
            row, column = divmod(index, 4)
            initial = "" if key.endswith("_secret") else self.settings.get(key, "")
            widget = self._field(fields, label, initial, row, column, combo=combo, show=show)
            setattr(self, key, widget)
        if any(combo for _, _, combo, _ in fields_spec):
            self._refresh_ports_button(settings_card, 0)

        content = ctk.CTkFrame(page, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)
        preview = self._card(content)
        preview.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._card_title(preview, preview_title, preview_description)
        ui = {}
        if telemetry:
            metric_grid = ctk.CTkFrame(preview, fg_color="transparent")
            metric_grid.pack(fill="both", expand=True, padx=18, pady=(12, 16))
            metric_grid.grid_columnconfigure((0, 1, 2), weight=1)
            ui["speed"] = self._metric(metric_grid, "SPEED", "—", "km/h", 0)
            ui["rpm"] = self._metric(metric_grid, "ENGINE", "—", "RPM", 1)
            ui["gear"] = self._metric(metric_grid, "GEAR", "—", "GEAR", 2)
        else:
            color_body = ctk.CTkFrame(preview, fg_color="transparent")
            color_body.pack(fill="both", expand=True, padx=20, pady=(8, 18))
            color_body.grid_columnconfigure(0, weight=1)
            color_body.grid_rowconfigure(0, weight=1)
            ui["swatch"] = ctk.CTkFrame(
                color_body, width=180, height=140, corner_radius=18, fg_color="#263149"
            )
            ui["swatch"].grid(row=0, column=0, sticky="nsew", pady=(0, 14))
            ui["swatch"].grid_propagate(False)
            ui["value"] = ctk.CTkLabel(
                color_body, text="Waiting for game", font=("Segoe UI", 18, "bold"), text_color=TEXT
            )
            ui["value"].grid(row=1, column=0, pady=(0, 6))
        ui["detail"] = ctk.CTkLabel(
            preview, text="No game data received", font=("Segoe UI", 11), text_color=MUTED
        )
        ui["detail"].pack(anchor="w", padx=22, pady=(0, 16))

        right = ctk.CTkFrame(content, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        control = self._card(right)
        control.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self._card_title(control, "BRIDGE CONTROL", control_description)
        ui["state"] = ctk.CTkLabel(
            control, text="●  Stopped", text_color=MUTED, font=("Segoe UI", 12, "bold")
        )
        ui["state"].pack(anchor="w", padx=20, pady=(14, 12))
        actions = ctk.CTkFrame(control, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 18))
        ui["start"] = self._action_button(
            actions, "Start bridge", lambda selected=mode: self._start(selected), primary=True
        )
        ui["start"].pack(side="left", fill="x", expand=True, padx=(0, 5))
        ui["stop"] = self._action_button(
            actions, "Stop", lambda selected=mode: self._stop(selected), state="disabled"
        )
        ui["stop"].pack(side="left", fill="x", expand=True, padx=(5, 0))
        log_card = self._card(right)
        log_card.grid(row=1, column=0, sticky="nsew")
        self._card_title(log_card, "ACTIVITY", "Connection and game event messages")
        ui["log"] = self._log(log_card)
        self.game_ui[mode] = ui
        return page

    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=18, border_width=1, border_color=BORDER)

    @staticmethod
    def _action_button(parent, text, command, primary=False, state="normal"):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=42,
            corner_radius=10,
            fg_color="#39C8A6" if primary else PANEL_LIGHT,
            hover_color="#52E0C0" if primary else "#22344B",
            text_color="#071711" if primary else TEXT,
            font=(FONT, 11, "bold"),
            state=state,
        )

    def _card_title(self, parent, title, description):
        ctk.CTkLabel(parent, text=title, font=(FONT, 10, "bold"), text_color=TEXT).pack(
            anchor="w", padx=22, pady=(20, 0)
        )
        ctk.CTkLabel(parent, text=description, font=(FONT, 10), text_color=MUTED).pack(
            anchor="w", padx=22, pady=(4, 0)
        )

    def _field(self, parent, label, value, row, column, combo=False, show=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=column, sticky="ew", padx=(0, 10), pady=(0, 8))
        ctk.CTkLabel(frame, text=label, font=(FONT, 9, "bold"), text_color=MUTED).pack(anchor="w", pady=(0, 6))
        if combo:
            ports = self._port_names()
            widget = ctk.CTkComboBox(
                frame,
                values=ports or [value],
                height=38,
                font=(FONT, 11),
                fg_color=FIELD,
                border_color=BORDER,
                button_color=PANEL_LIGHT,
                button_hover_color="#263B51",
                dropdown_fg_color=PANEL,
                dropdown_hover_color=PANEL_LIGHT,
                corner_radius=9,
            )
            widget.set(value)
        else:
            widget = ctk.CTkEntry(
                frame,
                height=38,
                font=(FONT, 11),
                show=show or "",
                fg_color=FIELD,
                border_color=BORDER,
                text_color=TEXT,
                placeholder_text_color=MUTED,
                corner_radius=9,
            )
            widget.insert(0, value)
        widget.pack(fill="x")
        return widget

    def _refresh_ports_button(self, parent, row):
        button = ctk.CTkButton(
            parent, text="↻  Refresh ports", width=124, height=30, fg_color=ACCENT_SOFT,
            hover_color="#1A4540", text_color=ACCENT, font=(FONT, 10, "bold"),
            command=self._refresh_ports,
        )
        button.pack(anchor="e", padx=20, pady=(0, 13))

    def _port_names(self):
        try:
            return [port.device for port in list_ports.comports()]
        except serial.SerialException:
            return []

    def _refresh_ports(self):
        ports = self._port_names()
        values = ports or ["No ports found"]
        for widget in (
            self.fh5_serial,
            self.rgb_serial,
            self.beamng_serial,
            self.rocket_serial,
        ):
            current = widget.get()
            widget.configure(values=values if current in values else values + [current])
        message = f"Detected {len(ports)} serial port(s)."
        for mode in ("fh5", "rgb", *self.game_ui):
            self._log_message(mode, message)

    def _metric(self, parent, title, value, unit, column):
        box = ctk.CTkFrame(parent, fg_color=FIELD, corner_radius=14, border_width=1, border_color=BORDER)
        box.grid(row=0, column=column, sticky="nsew", padx=5, pady=3)
        ctk.CTkLabel(box, text=title, font=(FONT, 9, "bold"), text_color=MUTED).pack(pady=(20, 10))
        label = ctk.CTkLabel(box, text=value, font=(FONT_DISPLAY, 32, "bold"), text_color=ACCENT)
        label.pack()
        ctk.CTkLabel(box, text=unit, font=(FONT, 9, "bold"), text_color=MUTED).pack(pady=(3, 19))
        return label

    def _log(self, parent):
        widget = ctk.CTkTextbox(
            parent,
            height=100,
            fg_color=FIELD,
            text_color="#B9C7DC",
            font=("Cascadia Code", 10),
            corner_radius=12,
            border_width=1,
            border_color=BORDER,
            scrollbar_button_color="#25364A",
            scrollbar_button_hover_color=ACCENT,
        )
        widget.pack(fill="both", expand=True, padx=18, pady=(14, 18))
        widget.configure(state="disabled")
        return widget

    def _show_fh5(self):
        self.active_page = "fh5"
        self.fh5_page.tkraise()
        self.heading.configure(text="Forza Horizon 5 / 6")
        self.subtitle.configure(text="Sled UDP telemetry, streamed live to your Arduino")
        self._select_nav(self.nav_fh5)
        self._set_header_status("fh5")

    def _show_rgb(self):
        self.active_page = "rgb"
        self.rgb_page.tkraise()
        self.heading.configure(text="OpenRGB Color")
        self.subtitle.configure(text="Share your lighting setup with an Arduino")
        self._select_nav(self.nav_rgb)
        self._set_header_status("rgb")

    def _show_cs2(self):
        self.active_page = "cs2"
        self.cs2_page.tkraise()
        self.heading.configure(text="Counter-Strike 2")
        self.subtitle.configure(text="React to CS2 game state with OpenRGB")
        self._select_nav(self.nav_cs2)
        self._set_header_status("cs2")

    def _show_game(self, mode):
        pages = {
            "beamng": (self.beamng_page, "BeamNG.drive", "OutGauge UDP telemetry to your Arduino"),
            "rocket": (self.rocket_page, "Rocket League", "Match events and boost color to your Arduino"),
            "dota": (self.dota_page, "Dota 2", "Game State Integration to OpenRGB"),
            "lol": (self.lol_page, "League of Legends", "Local Live Client Data API to OpenRGB"),
        }
        page, heading, subtitle = pages[mode]
        self.active_page = mode
        page.tkraise()
        self.heading.configure(text=heading)
        self.subtitle.configure(text=subtitle)
        self._select_nav(
            {
                "beamng": self.nav_beamng,
                "rocket": self.nav_rocket,
                "dota": self.nav_dota,
                "lol": self.nav_lol,
            }[mode]
        )
        self._set_header_status(mode)

    def _select_nav(self, selected):
        for button in (
            self.nav_fh5,
            self.nav_rgb,
            self.nav_cs2,
            self.nav_beamng,
            self.nav_rocket,
            self.nav_dota,
            self.nav_lol,
        ):
            button.configure(
                fg_color=PANEL_LIGHT if button is selected else "transparent",
                text_color=TEXT if button is selected else MUTED,
            )

    def _set_header_status(self, mode):
        count = len(self.workers)
        running = count > 0
        self.header_status.configure(
            text=f"●  {count} BRIDGE{'S' if count != 1 else ''} ACTIVE" if running else "●  ALL BRIDGES IDLE",
            text_color=GREEN if running else MUTED,
        )
        self.status_pill.configure(
            fg_color=ACCENT_SOFT if running else PANEL,
            border_color="#24554A" if running else BORDER,
        )

    def _start(self, mode):
        if mode in self.workers:
            return
        settings = self._current_settings()
        try:
            if mode == "fh5":
                config = {
                    "serial_port": settings["fh5_serial"].strip(),
                    "baud": self._integer(settings["fh5_baud"], "Baud rate", 1, 4_000_000),
                    "udp_port": self._integer(settings["udp_port"], "UDP port", 1, 65535),
                }
            elif mode == "rgb":
                config = {
                    "serial_port": settings["rgb_serial"].strip(),
                    "baud": self._integer(settings["rgb_baud"], "Baud rate", 1, 4_000_000),
                    "host": settings["openrgb_host"].strip(),
                    "openrgb_port": self._integer(settings["openrgb_port"], "OpenRGB SDK port", 1, 65535),
                    "interval": float(settings["rgb_interval"]),
                }
                if not math.isfinite(config["interval"]) or not 0.02 <= config["interval"] <= 10:
                    raise ValueError("Update interval must be between 0.02 and 10 seconds.")
                if not config["host"]:
                    raise ValueError("OpenRGB host cannot be empty.")
            elif mode == "cs2":
                config = {
                    "gsi_port": self._integer(
                        settings["cs2_gsi_port"], "CS2 GSI port", 1, 65535
                    ),
                    "openrgb_host": settings["cs2_openrgb_host"].strip(),
                    "openrgb_port": self._integer(
                        settings["cs2_openrgb_port"], "OpenRGB SDK port", 1, 65535
                    ),
                    "secret_key": self.cs2_secret.get(),
                }
                if not config["openrgb_host"]:
                    raise ValueError("OpenRGB host cannot be empty.")
                if not config["secret_key"] or len(config["secret_key"]) > 128:
                    raise ValueError("Enter a CS2 GSI auth key (1–128 characters).")
            elif mode == "beamng":
                config = {
                    "serial_port": settings["beamng_serial"].strip(),
                    "baud": self._integer(settings["beamng_baud"], "Baud rate", 1, 4_000_000),
                    "udp_port": self._integer(settings["beamng_udp_port"], "OutGauge UDP port", 1, 65535),
                }
            elif mode == "rocket":
                config = {
                    "serial_port": settings["rocket_serial"].strip(),
                    "baud": self._integer(settings["rocket_baud"], "Baud rate", 1, 4_000_000),
                    "port": self._integer(settings["rocket_port"], "Rocket League TCP port", 1, 65535),
                    "player_name": settings["rocket_player"].strip(),
                }
            elif mode == "dota":
                config = {
                    "gsi_port": self._integer(settings["dota_gsi_port"], "Dota 2 GSI port", 1, 65535),
                    "openrgb_host": settings["dota_openrgb_host"].strip(),
                    "openrgb_port": self._integer(
                        settings["dota_openrgb_port"], "OpenRGB SDK port", 1, 65535
                    ),
                    "secret_key": self.dota_secret.get(),
                }
                if not config["openrgb_host"]:
                    raise ValueError("OpenRGB host cannot be empty.")
                if not config["secret_key"] or len(config["secret_key"]) > 128:
                    raise ValueError("Enter a Dota 2 GSI token (1–128 characters).")
            else:
                config = {
                    "openrgb_host": settings["lol_openrgb_host"].strip(),
                    "openrgb_port": self._integer(
                        settings["lol_openrgb_port"], "OpenRGB SDK port", 1, 65535
                    ),
                    "interval": float(settings["lol_poll_interval"]),
                }
                if not math.isfinite(config["interval"]) or not 0.1 <= config["interval"] <= 10:
                    raise ValueError("Poll interval must be between 0.1 and 10 seconds.")
                if not config["openrgb_host"]:
                    raise ValueError("OpenRGB host cannot be empty.")
            if "serial_port" in config and (
                not config["serial_port"] or config["serial_port"] == "No ports found"
            ):
                raise ValueError("Select or enter an Arduino serial port.")
        except ValueError as exc:
            messagebox.showerror("Check your settings", str(exc))
            return

        direct_modes = {"cs2", "dota", "lol"}
        if mode in direct_modes and any(
            running_mode in direct_modes for running_mode in self.workers
        ):
            messagebox.showerror(
                "OpenRGB already in use",
                "Only one direct OpenRGB game integration can run at a time. Stop the active game integration first.",
            )
            return

        if "serial_port" in config:
            for other_mode, worker in self.workers.items():
                other_port = worker[2].get("serial_port")
                if other_port and other_port.casefold() == config["serial_port"].casefold():
                    messagebox.showerror(
                        "Serial port already in use",
                        f"{other_mode} is already using {other_port}. Select a different port or stop that bridge.",
                    )
                    return

        self._save_settings()
        stop_event = threading.Event()
        thread = threading.Thread(target=self._run_bridge, args=(mode, config, stop_event), daemon=True)
        self.workers[mode] = (thread, stop_event, config)
        thread.start()
        self._set_mode_state(mode, True, "Starting…")
        self._set_header_status(mode)

    @staticmethod
    def _integer(value, label, minimum, maximum):
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a whole number.") from exc
        if not minimum <= number <= maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum}.")
        return number

    def _stop(self, mode):
        worker = self.workers.get(mode)
        if worker:
            worker[1].set()
            self._set_mode_state(mode, True, "Stopping…")

    def _run_bridge(self, mode, config, stop_event):
        ser = None
        sock = None
        client = None
        server = None
        controller = None
        try:
            if mode in ("fh5", "beamng"):
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.bind(("0.0.0.0", config["udp_port"]))
                sock.settimeout(0.5)
                ser = serial.Serial(config["serial_port"], config["baud"], timeout=0.5)
                self.events.put(
                    ("log", mode, f"Listening on UDP :{config['udp_port']}; connected to {config['serial_port']}.")
                )
                self.events.put(
                    ("status", mode, "Waiting for FH5 telemetry…" if mode == "fh5" else "Waiting for OutGauge data…")
                )
                stop_event.wait(2)
                count = 0
                last_update = 0.0
                while not stop_event.is_set():
                    try:
                        data, _ = sock.recvfrom(2048)
                    except socket.timeout:
                        continue
                    count += 1
                    if mode == "fh5":
                        speed, rpm, gear = parse_fh5_telemetry(data)
                    else:
                        speed, rpm, gear = parse_outgauge_packet(data)
                    if speed is None:
                        continue
                    ser.write(f"{speed},{rpm},{gear}\n".encode("ascii"))
                    now = time.monotonic()
                    if now - last_update >= 0.1:
                        self.events.put(
                            ("telemetry_data", mode, {"speed": speed, "rpm": rpm, "gear": gear, "packets": count})
                        )
                        last_update = now
            elif mode == "rgb":
                from openrgb import OpenRGBClient

                ser = serial.Serial(config["serial_port"], config["baud"], timeout=1)
                stop_event.wait(2)
                if stop_event.is_set():
                    return
                client = OpenRGBClient(
                    address=config["host"],
                    port=config["openrgb_port"],
                    name="FHSensorStudio",
                )
                devices = client.devices
                device_summary = ", ".join(f"{device.name} ({len(device.colors)} LEDs)" for device in devices)
                self.events.put(("log", mode, f"OpenRGB connected; found {len(devices)} device(s)."))
                if device_summary:
                    self.events.put(("rgb_device", device_summary))
                while not stop_event.is_set():
                    if not devices:
                        self.events.put(("status", mode, "Waiting for an OpenRGB device…"))
                        stop_event.wait(1)
                        continue
                    device = devices[0]
                    colors = device.colors
                    if colors:
                        red = sum(color.red for color in colors) // len(colors)
                        green = sum(color.green for color in colors) // len(colors)
                        blue = sum(color.blue for color in colors) // len(colors)
                        ser.write(f"{red},{green},{blue}\n".encode("ascii"))
                        self.events.put(("rgb_data", {"red": red, "green": green, "blue": blue}))
                    stop_event.wait(config["interval"])
            elif mode == "rocket":
                import codecs

                ser = serial.Serial(config["serial_port"], config["baud"], timeout=1)
                stop_event.wait(2)
                if stop_event.is_set():
                    return
                sock = socket.create_connection(("127.0.0.1", config["port"]), timeout=3)
                sock.settimeout(0.5)
                self.events.put(
                    ("log", mode, f"Connected to Rocket League Stats API at 127.0.0.1:{config['port']}.")
                )
                self.events.put(("status", mode, "Waiting for a match update…"))
                utf8_decoder = codecs.getincrementaldecoder("utf-8")()
                text_buffer = ""
                while not stop_event.is_set():
                    try:
                        chunk = sock.recv(65536)
                    except socket.timeout:
                        continue
                    if not chunk:
                        raise ConnectionError("Rocket League closed the Stats API connection.")
                    text_buffer += utf8_decoder.decode(chunk)
                    envelopes, text_buffer = extract_json_messages(text_buffer)
                    for envelope in envelopes:
                        event_name, data = decode_event(envelope)
                        color, label = color_for_event(event_name, data, config["player_name"])
                        ser.write(f"{color[0]},{color[1]},{color[2]}\n".encode("ascii"))
                        self.events.put(("game_color", mode, color, label))
            elif mode == "cs2":
                from openrgb import OpenRGBClient

                client = OpenRGBClient(
                    address=config["openrgb_host"],
                    port=config["openrgb_port"],
                    name="FHSensorStudio CS2",
                )
                controller = OpenRGBGameController(client)
                devices = controller.devices
                summary = ", ".join(f"{device.name} ({len(device.colors)} LEDs)" for device in devices)
                self.events.put(("log", mode, f"Connected to OpenRGB; found {len(devices)} device(s)."))
                if summary:
                    self.events.put(("cs2_device", summary))

                def on_update(gsi_data):
                    color, _ = controller.update(gsi_data)
                    player = gsi_data.get("player", {})
                    state = player.get("state", {})
                    round_data = gsi_data.get("round", {})
                    event_parts = []
                    if "health" in state:
                        event_parts.append(f'HP {state["health"]}')
                    if round_data.get("bomb"):
                        event_parts.append(f'Bomb {round_data["bomb"]}')
                    self.events.put(
                        (
                            "cs2_data",
                            {
                                "hex": f"#{color.red:02x}{color.green:02x}{color.blue:02x}",
                                "rgb": f"R {color.red}  G {color.green}  B {color.blue}",
                                "event": "  ·  ".join(event_parts) or player.get("activity", "Game state received"),
                            },
                        )
                    )

                server = HTTPServer(
                    (DEFAULT_GSI_HOST, config["gsi_port"]),
                    create_handler(config["secret_key"], on_update),
                )
                server.timeout = 0.5
                self.events.put(
                    ("log", mode, f"CS2 GSI listening on {DEFAULT_GSI_HOST}:{config['gsi_port']}.")
                )
                self.events.put(("status", mode, "Waiting for CS2 game state…"))
                while not stop_event.is_set():
                    server.handle_request()
            elif mode == "dota":
                from openrgb import OpenRGBClient

                client = OpenRGBClient(
                    address=config["openrgb_host"],
                    port=config["openrgb_port"],
                    name="FHSensorStudio Dota 2",
                )
                devices = client.devices
                self.events.put(("log", mode, f"Connected to OpenRGB; found {len(devices)} device(s)."))

                def on_dota_update(gsi_data):
                    color, label = dota_health_color(gsi_data)
                    self._set_openrgb_devices(client, color)
                    self.events.put(("game_color", mode, color, label))

                server = HTTPServer(
                    ("127.0.0.1", config["gsi_port"]),
                    create_handler(config["secret_key"], on_dota_update, token_field="token"),
                )
                server.timeout = 0.5
                self.events.put(("log", mode, f"Dota 2 GSI listening on 127.0.0.1:{config['gsi_port']}."))
                self.events.put(("status", mode, "Waiting for Dota 2 game state…"))
                while not stop_event.is_set():
                    server.handle_request()
            else:
                from openrgb import OpenRGBClient

                client = OpenRGBClient(
                    address=config["openrgb_host"],
                    port=config["openrgb_port"],
                    name="FHSensorStudio League of Legends",
                )
                devices = client.devices
                self.events.put(("log", mode, f"Connected to OpenRGB; found {len(devices)} device(s)."))
                last_error = None
                self.events.put(("status", mode, "Waiting for a League of Legends match…"))
                while not stop_event.is_set():
                    try:
                        game_data = fetch_live_data()
                        color, label = lol_health_color(game_data)
                        self._set_openrgb_devices(client, color)
                        self.events.put(("game_color", mode, color, label))
                        last_error = None
                    except (HTTPError, URLError, TimeoutError, OSError) as exc:
                        error = str(exc)
                        if error != last_error:
                            self.events.put(("log", mode, f"Live Client API unavailable: {error}"))
                            last_error = error
                        self.events.put(("status", mode, "Waiting for a League of Legends match…"))
                    stop_event.wait(config["interval"])
        except Exception as exc:
            if not stop_event.is_set():
                self.events.put(("error", mode, str(exc)))
        finally:
            if controller is not None:
                try:
                    controller.close()
                except Exception as exc:
                    self.events.put(("log", mode, f"OpenRGB cleanup warning: {exc}"))
            if server is not None:
                server.server_close()
            resources = []
            if sock is not None:
                resources.append(("UDP socket", sock.close))
            if ser is not None and ser.is_open:
                resources.append(("serial connection", ser.close))
            if client is not None:
                resources.append(("OpenRGB connection", client.disconnect))
            for name, close in resources:
                try:
                    close()
                except Exception as exc:
                    self.events.put(("log", mode, f"{name} cleanup warning: {exc}"))
            self.events.put(("stopped", mode, None))

    @staticmethod
    def _set_openrgb_devices(client, color):
        rgb_color = RGBColor(*color)
        for device in client.devices:
            if any(mode.name.casefold() == "direct" for mode in device.modes):
                device.set_mode("Direct")
            device.set_color(rgb_color)

    def _process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "telemetry_data":
                    mode, data = event[1], event[2]
                    if mode == "fh5":
                        speed_value, rpm_value, gear_value = self.speed_value, self.rpm_value, self.gear_value
                        speed_value.configure(text=str(data["speed"]))
                        rpm_value.configure(text=f'{data["rpm"]:,}')
                        gear = data["gear"]
                        gear_value.configure(text="R" if gear < 0 else ("N" if gear == 0 else str(gear)))
                        self.packet_value.configure(text=f'Packets received: {data["packets"]:,}')
                        self._set_mode_state(mode, True, "Receiving telemetry")
                        continue
                    ui = self.game_ui[mode]
                    ui["speed"].configure(text=str(data["speed"]))
                    ui["rpm"].configure(text=f'{data["rpm"]:,}')
                    gear = data["gear"]
                    ui["gear"].configure(text="R" if gear == 0 else ("N" if gear == 1 else str(gear - 1)))
                    ui["detail"].configure(text=f'Valid packets received: {data["packets"]:,}')
                    self._set_mode_state(mode, True, "Receiving OutGauge telemetry")
                elif kind == "rgb_data":
                    data = event[1]
                    self.color_value.configure(text=f'R  {data["red"]:3d}     G  {data["green"]:3d}     B  {data["blue"]:3d}')
                    self.color_swatch.configure(fg_color=f'#{data["red"]:02x}{data["green"]:02x}{data["blue"]:02x}')
                    self._set_mode_state("rgb", True, "Streaming color")
                elif kind == "cs2_data":
                    data = event[1]
                    self.cs2_color_value.configure(text=data["rgb"])
                    self.cs2_color_swatch.configure(fg_color=data["hex"])
                    self.cs2_event_value.configure(text=data["event"])
                    self._set_mode_state("cs2", True, "Receiving game state")
                elif kind == "cs2_device":
                    self.cs2_event_value.configure(text=event[1])
                elif kind == "game_color":
                    mode, color, label = event[1], event[2], event[3]
                    ui = self.game_ui[mode]
                    ui["swatch"].configure(
                        fg_color=f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
                    )
                    ui["value"].configure(
                        text=f"R {color[0]}  G {color[1]}  B {color[2]}"
                    )
                    ui["detail"].configure(text=label)
                    self._set_mode_state(mode, True, "Receiving game state")
                elif kind == "rgb_device":
                    self.device_value.configure(text=event[1])
                elif kind == "status":
                    self._set_mode_state(event[1], True, event[2])
                elif kind == "log":
                    self._log_message(event[1], event[2])
                elif kind == "error":
                    mode, error = event[1], event[2]
                    self._log_message(mode, f"ERROR: {error}")
                    self._set_mode_state(mode, True, "Connection error")
                    messagebox.showerror("Bridge error", error)
                elif kind == "stopped":
                    mode = event[1]
                    self.workers.pop(mode, None)
                    self._set_mode_state(mode, False, "Stopped")
                    self._set_header_status(self.active_page)
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _set_mode_state(self, mode, running, text):
        if mode == "fh5":
            label, start, stop = self.fh5_state, self.fh5_start, self.fh5_stop
        elif mode == "rgb":
            label, start, stop = self.rgb_state, self.rgb_start, self.rgb_stop
        elif mode == "cs2":
            label, start, stop = self.cs2_state, self.cs2_start, self.cs2_stop
        else:
            ui = self.game_ui[mode]
            label, start, stop = ui["state"], ui["start"], ui["stop"]
        color = RED if "error" in text.casefold() else (GREEN if running else MUTED)
        label.configure(text=f"●  {text}", text_color=color)
        start.configure(state="disabled" if running else "normal")
        stop.configure(state="normal" if running else "disabled")
        self._set_header_status(self.active_page)

    def _log_message(self, mode, message):
        widgets = {
            "fh5": self.fh5_log,
            "rgb": self.rgb_log,
            "cs2": self.cs2_log,
        }
        widget = widgets[mode] if mode in widgets else self.game_ui[mode]["log"]
        timestamp = time.strftime("%H:%M:%S")
        widget.configure(state="normal")
        widget.insert("end", f"{timestamp}  {message}\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _on_close(self):
        for _, stop_event, _ in self.workers.values():
            stop_event.set()
        self.destroy()


if __name__ == "__main__":
    app = BridgeApp()
    app.mainloop()
