import math
import queue
import socket
import threading
import time
from tkinter import messagebox

import customtkinter as ctk
import serial
from serial.tools import list_ports

from lcdfh5 import parse_fh5_telemetry


APP_NAME = "FH Sensor Studio"
BG = "#0B1020"
PANEL = "#121A2B"
PANEL_LIGHT = "#19243A"
TEXT = "#F3F6FC"
MUTED = "#91A0B8"
ACCENT = "#6D7CFF"
GREEN = "#35D39A"
RED = "#FF647C"
ORANGE = "#F5B95F"


class BridgeApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1100x760")
        self.minsize(900, 660)
        self.configure(fg_color=BG)

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
        }

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#0E1526")
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        ctk.CTkLabel(sidebar, text="◈", font=("Segoe UI Symbol", 36), text_color=ACCENT).pack(
            anchor="w", padx=24, pady=(28, 0)
        )
        ctk.CTkLabel(sidebar, text="FH SENSOR", font=("Segoe UI", 20, "bold"), text_color=TEXT).pack(
            anchor="w", padx=24, pady=(0, 2)
        )
        ctk.CTkLabel(sidebar, text="ARDUINO BRIDGE", font=("Segoe UI", 10, "bold"), text_color=MUTED).pack(
            anchor="w", padx=25
        )
        ctk.CTkFrame(sidebar, height=1, fg_color="#263149").pack(fill="x", padx=20, pady=24)
        ctk.CTkLabel(sidebar, text="YOUR BRIDGES", font=("Segoe UI", 10, "bold"), text_color=MUTED).pack(
            anchor="w", padx=24, pady=(0, 10)
        )
        self.nav_fh5 = self._nav_button(sidebar, "  ◉  FH5 TELEMETRY", self._show_fh5)
        self.nav_rgb = self._nav_button(sidebar, "  ◉  OPENRGB COLOR", self._show_rgb)
        self.nav_fh5.pack(fill="x", padx=14, pady=4)
        self.nav_rgb.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(
            sidebar,
            text="Each bridge sends its own\nserial message format.\n\nUse separate COM ports\nwhen running both.",
            font=("Segoe UI", 11),
            text_color=MUTED,
            justify="left",
        ).pack(side="bottom", anchor="w", padx=24, pady=24)

        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=30, pady=24)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(2, 20))
        header.grid_columnconfigure(0, weight=1)
        self.heading = ctk.CTkLabel(header, text="Forza Horizon 5", font=("Segoe UI", 27, "bold"), text_color=TEXT)
        self.heading.grid(row=0, column=0, sticky="w")
        self.subtitle = ctk.CTkLabel(
            header, text="Live game telemetry to your Arduino", font=("Segoe UI", 12), text_color=MUTED
        )
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.header_status = ctk.CTkLabel(
            header, text="●  STOPPED", font=("Segoe UI", 11, "bold"), text_color=MUTED
        )
        self.header_status.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

        self.pages = ctk.CTkFrame(main, fg_color="transparent")
        self.pages.grid(row=2, column=0, sticky="nsew")
        self.pages.grid_columnconfigure(0, weight=1)
        self.pages.grid_rowconfigure(0, weight=1)
        self.fh5_page = self._build_fh5_page(self.pages)
        self.rgb_page = self._build_rgb_page(self.pages)
        self.fh5_page.grid(row=0, column=0, sticky="nsew")
        self.rgb_page.grid(row=0, column=0, sticky="nsew")
        self._show_fh5()

    def _nav_button(self, parent, text, command):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            anchor="w",
            height=42,
            corner_radius=10,
            fg_color="transparent",
            hover_color=PANEL_LIGHT,
            text_color=MUTED,
            font=("Segoe UI", 11, "bold"),
        )

    def _build_fh5_page(self, parent):
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)

        settings_card = self._card(page)
        settings_card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self._card_title(settings_card, "CONNECTION SETTINGS", "Configure the FH5 UDP listener and Arduino serial link")
        fields = ctk.CTkFrame(settings_card, fg_color="transparent")
        fields.pack(fill="x", padx=20, pady=(12, 18))
        fields.grid_columnconfigure((0, 1, 2), weight=1)
        self.fh5_serial = self._field(fields, "ARDUINO PORT", self.settings["fh5_serial"], 0, 0, combo=True)
        self.fh5_baud = self._field(fields, "BAUD RATE", self.settings["fh5_baud"], 0, 1)
        self.udp_port = self._field(fields, "FH5 UDP PORT", self.settings["udp_port"], 0, 2)
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
        self.fh5_start = ctk.CTkButton(actions, text="Start bridge", height=40, fg_color=ACCENT, command=lambda: self._start("fh5"))
        self.fh5_start.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.fh5_stop = ctk.CTkButton(actions, text="Stop", height=40, fg_color="#29354C", command=lambda: self._stop("fh5"), state="disabled")
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
        self.rgb_start = ctk.CTkButton(actions, text="Start bridge", height=40, fg_color=ACCENT, command=lambda: self._start("rgb"))
        self.rgb_start.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.rgb_stop = ctk.CTkButton(actions, text="Stop", height=40, fg_color="#29354C", command=lambda: self._stop("rgb"), state="disabled")
        self.rgb_stop.pack(side="left", fill="x", expand=True, padx=(5, 0))
        log_card = self._card(right)
        log_card.grid(row=1, column=0, sticky="nsew")
        self._card_title(log_card, "ACTIVITY", "Connection and runtime messages")
        self.rgb_log = self._log(log_card)
        return page

    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=16, border_width=1, border_color="#1D2940")

    def _card_title(self, parent, title, description):
        ctk.CTkLabel(parent, text=title, font=("Segoe UI", 11, "bold"), text_color=TEXT).pack(
            anchor="w", padx=20, pady=(17, 0)
        )
        ctk.CTkLabel(parent, text=description, font=("Segoe UI", 10), text_color=MUTED).pack(
            anchor="w", padx=20, pady=(3, 0)
        )

    def _field(self, parent, label, value, row, column, combo=False):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=column, sticky="ew", padx=(0, 12), pady=(0, 9))
        ctk.CTkLabel(frame, text=label, font=("Segoe UI", 9, "bold"), text_color=MUTED).pack(anchor="w", pady=(0, 5))
        if combo:
            ports = self._port_names()
            widget = ctk.CTkComboBox(frame, values=ports or [value], height=36, font=("Segoe UI", 11))
            widget.set(value)
        else:
            widget = ctk.CTkEntry(frame, height=36, font=("Segoe UI", 11))
            widget.insert(0, value)
        widget.pack(fill="x")
        return widget

    def _refresh_ports_button(self, parent, row):
        button = ctk.CTkButton(
            parent, text="↻ Refresh ports", width=120, height=28, fg_color="transparent",
            hover_color=PANEL_LIGHT, text_color=ACCENT, font=("Segoe UI", 10, "bold"),
            command=self._refresh_ports,
        )
        button.place(relx=1.0, rely=0.08 if row == 0 else 0.08, anchor="ne", x=-18, y=0)

    def _port_names(self):
        try:
            return [port.device for port in list_ports.comports()]
        except serial.SerialException:
            return []

    def _refresh_ports(self):
        ports = self._port_names()
        values = ports or ["No ports found"]
        for widget in (self.fh5_serial, self.rgb_serial):
            current = widget.get()
            widget.configure(values=values if current in values else values + [current])
        self._log_message("fh5", f"Detected {len(ports)} serial port(s).")
        self._log_message("rgb", f"Detected {len(ports)} serial port(s).")

    def _metric(self, parent, title, value, unit, column):
        box = ctk.CTkFrame(parent, fg_color=PANEL_LIGHT, corner_radius=12)
        box.grid(row=0, column=column, sticky="nsew", padx=5)
        ctk.CTkLabel(box, text=title, font=("Segoe UI", 9, "bold"), text_color=MUTED).pack(pady=(16, 8))
        label = ctk.CTkLabel(box, text=value, font=("Segoe UI", 30, "bold"), text_color=TEXT)
        label.pack()
        ctk.CTkLabel(box, text=unit, font=("Segoe UI", 9), text_color=MUTED).pack(pady=(0, 15))
        return label

    def _log(self, parent):
        widget = ctk.CTkTextbox(parent, height=100, fg_color="#0E1526", text_color="#B9C7DC", font=("Consolas", 10), corner_radius=10)
        widget.pack(fill="both", expand=True, padx=14, pady=(12, 14))
        widget.configure(state="disabled")
        return widget

    def _show_fh5(self):
        self.active_page = "fh5"
        self.fh5_page.tkraise()
        self.heading.configure(text="Forza Horizon 5")
        self.subtitle.configure(text="Live game telemetry to your Arduino")
        self.nav_fh5.configure(fg_color=PANEL_LIGHT, text_color=TEXT)
        self.nav_rgb.configure(fg_color="transparent", text_color=MUTED)
        self._set_header_status("fh5")

    def _show_rgb(self):
        self.active_page = "rgb"
        self.rgb_page.tkraise()
        self.heading.configure(text="OpenRGB Color")
        self.subtitle.configure(text="Share your lighting setup with an Arduino")
        self.nav_rgb.configure(fg_color=PANEL_LIGHT, text_color=TEXT)
        self.nav_fh5.configure(fg_color="transparent", text_color=MUTED)
        self._set_header_status("rgb")

    def _set_header_status(self, mode):
        running = mode in self.workers
        self.header_status.configure(
            text="●  RUNNING" if running else "●  STOPPED",
            text_color=GREEN if running else MUTED,
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
            else:
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
            if not config["serial_port"] or config["serial_port"] == "No ports found":
                raise ValueError("Select or enter an Arduino serial port.")
        except ValueError as exc:
            messagebox.showerror("Check your settings", str(exc))
            return

        other_mode = "rgb" if mode == "fh5" else "fh5"
        if other_mode in self.workers:
            other_port = self.workers[other_mode][2]["serial_port"]
            if other_port.casefold() == config["serial_port"].casefold():
                messagebox.showerror(
                    "Serial port already in use",
                    "Both bridges cannot use the same serial port at once. Choose separate ports or stop the other bridge.",
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
        try:
            if mode == "fh5":
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.bind(("0.0.0.0", config["udp_port"]))
                sock.settimeout(0.5)
                ser = serial.Serial(config["serial_port"], config["baud"], timeout=0.5)
                self.events.put(("log", mode, f"Listening on UDP :{config['udp_port']}; connected to {config['serial_port']}."))
                self.events.put(("status", mode, "Waiting for FH5 telemetry…"))
                stop_event.wait(2)
                count = 0
                last_update = 0.0
                while not stop_event.is_set():
                    try:
                        data, _ = sock.recvfrom(2048)
                    except socket.timeout:
                        continue
                    count += 1
                    speed, rpm, gear = parse_fh5_telemetry(data)
                    if speed is None:
                        continue
                    ser.write(f"{speed},{rpm},{gear}\n".encode("ascii"))
                    now = time.monotonic()
                    if now - last_update >= 0.1:
                        self.events.put(("fh5_data", {"speed": speed, "rpm": rpm, "gear": gear, "packets": count}))
                        last_update = now
            else:
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
        except Exception as exc:
            if not stop_event.is_set():
                self.events.put(("error", mode, str(exc)))
        finally:
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

    def _process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "fh5_data":
                    data = event[1]
                    self.speed_value.configure(text=str(data["speed"]))
                    self.rpm_value.configure(text=f'{data["rpm"]:,}')
                    gear = data["gear"]
                    self.gear_value.configure(text="R" if gear < 0 else ("N" if gear == 0 else str(gear)))
                    self.packet_value.configure(text=f'Packets received: {data["packets"]:,}')
                    self._set_mode_state("fh5", True, "Receiving telemetry")
                elif kind == "rgb_data":
                    data = event[1]
                    self.color_value.configure(text=f'R  {data["red"]:3d}     G  {data["green"]:3d}     B  {data["blue"]:3d}')
                    self.color_swatch.configure(fg_color=f'#{data["red"]:02x}{data["green"]:02x}{data["blue"]:02x}')
                    self._set_mode_state("rgb", True, "Streaming color")
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
        else:
            label, start, stop = self.rgb_state, self.rgb_start, self.rgb_stop
        color = RED if "error" in text.casefold() else (GREEN if running else MUTED)
        label.configure(text=f"●  {text}", text_color=color)
        start.configure(state="disabled" if running else "normal")
        stop.configure(state="normal" if running else "disabled")
        self._set_header_status(self.active_page)

    def _log_message(self, mode, message):
        widget = self.fh5_log if mode == "fh5" else self.rgb_log
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
