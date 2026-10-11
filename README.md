# FH Sensor Studio

FH Sensor Studio is a Windows desktop app for sending Forza Horizon 5
telemetry or OpenRGB lighting colors to an Arduino, and for reacting to
Counter-Strike 2 game events with OpenRGB. It brings the bridges together in
one dark-themed interface with editable connection settings, live readouts,
status messages, and start/stop controls.

The bridges remain independent and use different serial formats:

| Bridge | Input | Arduino serial message | Default baud |
| --- | --- | --- | --- |
| FH5 Telemetry | Forza Horizon 5 Sled-format UDP packets | `speed_kmh,rpm,gear\n` | 9600 |
| OpenRGB Color | Average color of the first OpenRGB device | `red,green,blue\n` | 115200 |
| CS2 Game State | Counter-Strike 2 Game State Integration (GSI) events | None; controls OpenRGB devices directly | — |

The Arduino firmware must understand the selected bridge's message format and
baud rate. This project does not include Arduino firmware.

## Run the Windows app

Download or build `FHSensorStudio.exe`, then double-click it. Select a bridge
in the left sidebar, check its connection settings, and click **Start bridge**.
Use **Stop** to end a bridge. FH5 and the OpenRGB serial streamer can run at
the same time when they use different serial ports. The CS2 bridge controls
OpenRGB directly, so it cannot run at the same time as the OpenRGB serial
streamer.

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

## Configure Counter-Strike 2

1. Run OpenRGB with its SDK server enabled.
2. In the app's **CS2 Game State** page, choose the OpenRGB host and SDK port.
   Set the GSI port (default `5000`) and enter an auth key. The key is masked
   and is not saved to the settings file.
3. Create a Game State Integration config file in CS2's `game\csgo\cfg`
   directory, for example `gamestate_integration_fhsensor.cfg`:

   ```text
   "FHSensorStudio"
   {
       "uri" "http://127.0.0.1:5000/"
       "timeout" "5.0"
       "buffer" "0.1"
       "throttle" "0.1"
       "heartbeat" "30.0"
       "auth"
       {
           "token" "REPLACE_WITH_THE_KEY_ENTERED_IN_THE_APP"
       }
       "data"
       {
           "player_state" "1"
           "player_match_stats" "1"
           "map" "1"
           "round" "1"
       }
   }
   ```

4. Replace the placeholder token with the same key entered in the app. Start
   the CS2 bridge, then launch or restart CS2.

The listener binds only to `127.0.0.1` and checks the GSI auth token before
processing events. It changes all connected OpenRGB devices according to
player health, menu/round state, kills, bomb events, and flash, fire, or smoke
effects. Do not publish a real auth key in a config file, source file, issue, or
commit. The app does not store the key; enter it again each time you start the
CS2 bridge. The standalone `cs2rgb.py` script accepts the key through the
`CS2_GSI_SECRET` environment variable or prompts for it.

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
- **CS2 reports no game state:** Confirm the GSI config file is in CS2's
  `game\csgo\cfg` directory, its URI port matches the app, the token matches,
  and CS2 has been restarted after creating the config.
- **CS2/OpenRGB colors do not change:** Ensure OpenRGB is running and stop the
  OpenRGB serial-color bridge before starting CS2 lighting.
- **Build fails:** Confirm Python is on PATH and retry `build.bat`; the script
  installs the packages listed in `requirements.txt`.

`lcdfh5.py`, `pyrgb.py`, and `cs2rgb.py` are also available as standalone
scripts. The desktop app reuses the FH5 packet parser and CS2 game-state
handling from those modules.
