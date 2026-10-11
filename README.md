# FH Sensor Studio

FH Sensor Studio is a Windows desktop app for sending Forza Horizon 5
telemetry or OpenRGB lighting colors to an Arduino. It wraps the two original
bridges in one dark-themed interface with editable connection settings, live
readouts, status messages, and start/stop controls.

The bridges remain independent and use different serial formats:

| Bridge | Input | Arduino serial message | Default baud |
| --- | --- | --- | --- |
| FH5 Telemetry | Forza Horizon 5 Sled-format UDP packets | `speed_kmh,rpm,gear\n` | 9600 |
| OpenRGB Color | Average color of the first OpenRGB device | `red,green,blue\n` | 115200 |

The Arduino firmware must understand the selected bridge's message format and
baud rate. This project does not include Arduino firmware.

## Run the Windows app

Download or build `FHSensorStudio.exe`, then double-click it. Select a bridge
in the left sidebar, check its connection settings, and click **Start bridge**.
Use **Stop** to end the stream. The app can run both bridges simultaneously
when each uses a different serial port; a single COM port cannot be shared.

Settings are saved automatically to:

```text
%APPDATA%\FHSensorStudio\settings.json
```

## Build the executable

Requirements: Windows, Python 3.10 or later, and an internet connection for
initial dependency installation.

1. Open this project folder in File Explorer.
2. Double-click `build.bat`.
3. When it completes, find the standalone executable at
   `dist\FHSensorStudio.exe`.

Alternatively, run these commands in PowerShell from the project directory:

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --windowed --onefile --name FHSensorStudio --collect-all customtkinter --hidden-import serial.tools.list_ports app.py
```

The executable is built for Windows and does not include Arduino firmware or
the OpenRGB application. Windows may display a security prompt for an
unsigned, locally built executable.

## Configure FH5 telemetry

1. In FH5, enable telemetry UDP output and select the Sled packet format.
2. Set its destination to the computer running the app and use the UDP port
   shown on the FH5 Telemetry page (default `5300`).
3. Select the Arduino COM port and set the baud rate to match the firmware
   (default `COM9`, `9600`).
4. Start the bridge. The app displays speed, RPM, gear, and received packet
   count as telemetry arrives.

The parser reads Sled velocity values at byte offsets 32, 36, and 40 to
calculate speed in km/h, RPM at offset 16, and gear at offset 319. Raw gear
values 0 and 1 are displayed/sent as reverse (-1) and neutral (0).

## Configure OpenRGB

1. Run OpenRGB and enable its SDK server.
2. Select the Arduino COM port and matching baud rate (defaults `COM10`,
   `115200`).
3. Enter the OpenRGB host and SDK port (defaults `localhost`, `6745`), then
   click **Start bridge**.
4. The app shows a color preview and RGB values. Update interval defaults to
   0.1 seconds.

The bridge averages the red, green, and blue channels of all LEDs on the first
device reported by OpenRGB. If OpenRGB has no devices when connected, connect
the device and restart the bridge.

## Troubleshooting

- **Arduino connection error:** Select the correct COM port, close any other
  application using it, and verify the configured baud matches the firmware.
- **FH5 shows no telemetry:** Check game telemetry settings, the destination
  computer/IP, UDP port, and Sled format. Allow the app through Windows
  Firewall for UDP if prompted.
- **OpenRGB connection error:** Start OpenRGB, enable the SDK server, and
  verify the host and SDK port.
- **No OpenRGB device/color:** Ensure OpenRGB detects a device before starting
  the bridge.
- **Build fails:** Confirm Python is on PATH and retry `build.bat`; the script
  installs the packages listed in `requirements.txt`.

`lcdfh5.py` and `pyrgb.py` are retained as the original command-line scripts.
The desktop app reuses the FH5 packet parser from `lcdfh5.py`.
