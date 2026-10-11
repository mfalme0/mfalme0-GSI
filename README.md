# FH Sensor Studio

FH Sensor Studio is a Windows desktop app for streaming telemetry to an
Arduino and reacting to game state with OpenRGB. It brings the supported game
bridges together in one dark-themed interface with editable connection
settings, live readouts, status messages, and start/stop controls. Its
racing-inspired charcoal-and-mint skin groups game sources by category and
keeps the active bridge state visible across pages.

The bridges remain independent and use different serial formats:

| Bridge | Input | Arduino serial message | Default baud |
| --- | --- | --- | --- |
| FH5 Telemetry | Forza Horizon 5 Sled-format UDP packets | `speed_kmh,rpm,gear\n` | 9600 |
| BeamNG.drive | OutGauge UDP packets | `speed_kmh,rpm,gear\n` | 9600 |
| Rocket League | Local Stats API TCP stream | `red,green,blue\n` | 115200 |
| OpenRGB Color | Average color of the first OpenRGB device | `red,green,blue\n` | 115200 |
| CS2 Game State | Counter-Strike 2 Game State Integration (GSI) events | None; controls OpenRGB devices directly | — |
| Dota 2 | Authenticated Game State Integration (GSI) events | None; controls OpenRGB devices directly | — |
| League of Legends | Local HTTPS Live Client Data API | None; controls OpenRGB devices directly | — |

The Arduino firmware must understand the selected bridge's message format and
baud rate. This project does not include Arduino firmware.

## Run the Windows app

Download or build `FHSensorStudio.exe`, then double-click it. Select a bridge
in the left sidebar, check its connection settings, and click **Start bridge**.
Use **Stop** to end a bridge. Serial bridges can run concurrently when they
use different COM ports. CS2, Dota 2, and League of Legends each control
OpenRGB directly and are mutually exclusive; stop one before starting another.

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
python -m PyInstaller --noconfirm --clean --windowed --onefile --name FHSensorStudio --icon assets\fhsensor.ico --add-data "assets\fhsensor.ico;assets" --collect-all customtkinter --hidden-import serial.tools.list_ports app.py
```

The executable is built for Windows and does not include Arduino firmware or
the OpenRGB application. Windows may display a security prompt for an
unsigned, locally built executable. The app uses its custom mint-on-charcoal
icon and matching in-app branding.

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
Forza Horizon 6 can use this same bridge when configured to emit the compatible
Sled UDP packet format.

## Configure OpenRGB

1. Run OpenRGB and enable its SDK server.
2. Select the Arduino COM port and matching baud rate (defaults `COM10`,
   `115200`).
3. Enter the OpenRGB host and SDK port (defaults `localhost`, `6745`), then
   click **Start bridge**.
4. The app shows a color preview and RGB values. Update interval defaults to
   0.1 seconds.

The bridge averages the red, green, and blue channels of all LEDs on the first
device reported by OpenRGB. It sends those values to the selected Arduino
serial port. If OpenRGB has no devices when connected, connect the device and
restart the bridge.

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

## Configure BeamNG.drive

1. In BeamNG.drive, open **Options > Other > Protocols** and enable
   **OutGauge UDP**.
2. Set its destination to `127.0.0.1` and its UDP port to the value in the
   BeamNG page (default `4444`). OutGauge uses the LFS packet layout.
3. Select the Arduino COM port and matching baud rate (default `COM11`,
   `9600`), then start the bridge.

The app reads speed, RPM, and gear from OutGauge and sends
`speed_kmh,rpm,gear\n` to the Arduino. The BeamNG parser follows the official
OutGauge packet layout documented in the
[BeamNG protocols guide](https://docs.beamng.com/modding/protocols/).

## Configure Rocket League

1. Enable the local Stats API by setting `PacketSendRate` to a non-zero value
   in Rocket League's `TAGame\Config\TAStatsAPI.ini` (some installs use
   `DefaultStatsAPI.ini`):

   ```ini
   [TAGame.MatchStatsExporter_TA]
   Port=49123
   PacketSendRate=10
   ```

2. Restart Rocket League after changing the file.
3. In the app, use the same local TCP port (default `49123`), select an
   Arduino COM port and baud rate, and optionally enter your in-game player
   name. Start the bridge while Rocket League is running.

The app connects to `127.0.0.1` as a TCP client, parses the concatenated JSON
event stream, and sends RGB color values to the Arduino. Goal events briefly
show the scoring team's color; match updates use the selected player's boost
level. The default port and setup follow Rocket League's
[Stats API documentation](https://www.rocketleague.com/developer/stats-api);
the stream framing is based on community-tested clients because the official
page does not specify it in detail.

## Configure Dota 2

1. In the app's **Dota 2** page, set the GSI port (default `53001`), OpenRGB
   host/SDK port, and an auth token. The token is masked and not saved.
2. Create
   `<Dota 2 install>\game\dota\cfg\gamestate_integration\gamestate_integration_fhsensor.cfg`
   with the following configuration. Use the same port and token entered in
   the app:

   ```text
   "FHSensorStudio"
   {
       "uri" "http://127.0.0.1:53001/"
       "timeout" "5.0"
       "buffer" "0.1"
       "throttle" "0.1"
       "heartbeat" "30.0"
       "auth"
       {
           "token" "REPLACE_WITH_THE_TOKEN_ENTERED_IN_THE_APP"
       }
       "data"
       {
           "provider" "1"
           "map" "1"
           "player" "1"
           "hero" "1"
           "abilities" "1"
           "items" "1"
       }
   }
   ```

3. Add `-gamestateintegration` to Dota 2's launch options, start the app
   bridge, then launch or restart Dota 2.

The GSI listener binds only to `127.0.0.1`, verifies the configured token on
every request, and colors connected OpenRGB devices according to the current
hero's health.

## Configure League of Legends

1. Run League of Legends and enter an active game. The Live Client Data API is
   only available while a game is running.
2. Start OpenRGB with its SDK server enabled.
3. In the app's **League of Legends** page, set the OpenRGB host/SDK port and
   polling interval (default `0.5` seconds), then start the bridge.

The bridge polls
`https://127.0.0.1:2999/liveclientdata/allgamedata`. Riot's local endpoint uses
a self-signed certificate, so certificate verification is disabled only for
this fixed loopback URL. OpenRGB color reflects the active player's champion
health. The app retries while the game API is unavailable.

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
- **BeamNG shows no telemetry:** Confirm OutGauge UDP is enabled, the
  destination is `127.0.0.1`, and the game's configured port matches the app.
- **Rocket League shows no events:** Confirm Stats API is enabled with
  `PacketSendRate` greater than zero, the port matches, and Rocket League was
  restarted after changing its configuration.
- **Dota 2 shows no game state:** Confirm the config file location, GSI launch
  option, URI port, and token match the app settings.
- **League of Legends shows no game state:** Enter an active game and confirm
  the Live Client Data API is available at its local endpoint.
- **Build fails:** Confirm Python is on PATH and retry `build.bat`; the script
  installs the packages listed in `requirements.txt`.

`lcdfh5.py`, `pyrgb.py`, and `cs2rgb.py` are also available as standalone
scripts. The desktop app reuses packet parsing and game-state adapters from
the corresponding Python modules.
