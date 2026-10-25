# WeatherCat plugin for Indigo

Brings your weather station's live readings from **[WeatherCat](https://trixology.com)** (the macOS weather station app by Trixology) into **[Indigo](https://www.indigodomo.com)** home automation, as ordinary Indigo devices you can show on control pages, use in triggers and conditions, and log.

- One Indigo **sensor device per reading**: outdoor temperature, humidity, pressure, wind speed, gusts and direction, rain, dew point, wind chill, heat index, cloud base, solar, UV, soil and leaf sensors… whatever your station reports.
- **Today's high and low** (with the times they happened) and the **change over the last hour** on each reading that WeatherCat keeps statistics for.
- A **Feels Like** reading: heat index when it's hot, wind chill when it's cold and windy, otherwise the air temperature.
- A **Station** device with WeatherCat's current conditions, forecast, pressure trend, sunrise and sunset, triggered alerts and station communications status.
- Values in **the units you chose in WeatherCat** (°F/°C, inHg/hPa/mb, mph/km/h/knots/m/s, in/mm, feet/metres).
- Works entirely on your local network. No cloud service, account or API key.

*Not affiliated with or endorsed by Trixology. WeatherCat is Trixology's product; this plugin only reads the data WeatherCat already offers to other programs.*

## Requirements

| | |
|---|---|
| **Indigo** | 2023.2 or later (plugin API 3.4). Developed and tested on Indigo 2025.2 |
| **WeatherCat** | 3.0 or later, running on the Indigo Mac or another Mac on your network. Developed and tested on WeatherCat 3.33 (build 20) with a Davis Vantage station. See [WeatherCat 4](#weathercat-4) |
| **Network** | Indigo must be able to reach WeatherCat on TCP port **49255** (WeatherCat's *Rich Client Protocol*). Nothing to do if both run on the same Mac |

WeatherCat's Rich Client Protocol (RCP) server is always on in WeatherCat 3. There's nothing to enable.

## Installing

1. Download `WeatherCat.indigoPlugin` (from the Indigo Plugin Store, or the latest release on GitHub, unzipped).
2. Double-click it. Indigo installs and enables it, and opens the plugin's settings.
3. Check the settings (below) and click **Save**.

To update later, install the new version the same way. Your devices and settings are kept.

> **Tip:** Indigo *moves* a double-clicked plugin into its own Plugins folder. If you keep plugins in a folder you care about (a git checkout, say), install from a copy.

## Plugin settings

**Plugins > WeatherCat > Configure…**

| Setting | Default | Notes |
|---|---|---|
| WeatherCat address | `127.0.0.1` | `127.0.0.1` when WeatherCat runs on the same Mac as Indigo. Otherwise that Mac's IP address |
| RCP port | `49255` | WeatherCat's fixed RCP port |
| Read values every (seconds) | `30` | How often live readings are refreshed (5 or more). WeatherCat itself samples the station every 1–2 minutes by default |
| Read today's highs and lows every (minutes) | `5` | Also how often the units, forecast and sun times are refreshed |
| Debug logging | off | Logs every reading update. Useful while setting up |

## Quick start

**Plugins > WeatherCat > Create Devices for All Live Readings** creates, in a device folder called *WeatherCat*:

- a **WeatherCat Station** device,
- one **WeatherCat Reading** device for every reading your station is currently reporting (station communications counters and WeatherCat's raw rain counter are left out),
- a **WeatherCat Feels Like** device.

It's safe to run again: it only adds devices for readings that don't have one yet. Delete any you don't want.

Or create devices one at a time: **New… > Type: WeatherCat > Model: WeatherCat Reading** (or *WeatherCat Station*).

## Reading devices

A *WeatherCat Reading* is an Indigo **sensor** device. Its value (`sensorValue`) is the reading in WeatherCat's units, shown with the unit, e.g. `52.6 °F`, `30.42 inHg`, `234° SW`, `82%`.

### Device settings

| Setting | Notes |
|---|---|
| **Reading** | Which WeatherCat reading this device shows. The menu lists, in groups: readings that don't have a device yet; readings that already have one, labelled *(used by …)*; station status counters; readings your station isn't reporting, labelled *(no data)*. A new device starts on the first reading without a device. Two devices can't show the same reading. |
| **Today's high and low** | Adds high, low and 1-hour change states, for readings WeatherCat keeps statistics for (see below). On by default |
| **Decimal places** | *Usual for this reading*, or 0–4. Usual: temperature 1, pressure 2 (inHg) or 1 (hPa/mb), wind 1, rain 2 (in) or 1 (mm), humidity and wind direction 0 |

### States

| State | Type | On | Meaning |
|---|---|---|---|
| `sensorValue` | Number | all | The reading, in WeatherCat's units |
| `channelName` | String | all | WeatherCat's name for the reading, e.g. *Ext. Temperature* |
| `units` | String | all | Unit label, e.g. `°F`, `inHg`, `mph`, `in/h` |
| `hasData` | Yes/No | all | No if the station isn't reporting this reading |
| `todayHigh`, `todayLow` | Number | readings with statistics | Today's highest and lowest value |
| `todayHighTime`, `todayLowTime` | String | readings with statistics | When they happened, e.g. `3:48 AM` |
| `change1h` | Number | readings with statistics | Change over the last hour |
| `compass` | String | wind directions | Compass point, e.g. `SW` |
| `feelsLikeSource` | String | Feels Like | `Heat index`, `Wind chill` or `Temperature` |

**Readings with statistics** (WeatherCat's STAT$ items): outdoor and indoor temperature, dew point, wind chill, heat index, outdoor and indoor humidity, pressure, wind speed, 10-minute average wind speed, 1-minute wind gust, solar radiation and UV index.

### Error states

Indigo shows these in the device list instead of a value:

| Shown | Meaning |
|---|---|
| *offline* | WeatherCat isn't answering (not running, or not reachable). Devices recover by themselves when it is |
| *no data* | The station isn't reporting this reading (sensor not fitted, battery, signal) |
| *not found* | WeatherCat no longer has this reading at all, e.g. after changing station type. Pick another reading |
| *error* | WeatherCat answered, but reading this value failed. Turn on *Debug logging* to see why in the Event Log |

### Feels Like

*Feels Like (heat index, wind chill or temperature)* is a reading the plugin works out, using the US National Weather Service rule:

- **Heat index** when the air temperature is 80 °F (26.7 °C) or more;
- **Wind chill** when it's 50 °F (10 °C) or less **and** the wind is at least 3 mph (4.8 km/h);
- otherwise the **air temperature**.

It uses WeatherCat's own *Calculated Heat Index*, *Wind Chill*, *Wind Speed* and outdoor temperature readings. The `feelsLikeSource` state says which one is in use. WeatherCat's *Calculated Heat Index* and *Wind Chill* are also available as readings of their own.

## Station device

One *WeatherCat Station* device is enough. Its display shows WeatherCat's **current conditions** (e.g. *Overcast*), or *Station comms failed* / *WeatherCat not answering*.

| State | Type | Meaning |
|---|---|---|
| `status` | String | What the device list shows (see above) |
| `online` | Yes/No | WeatherCat is answering |
| `stationComms` | Yes/No | WeatherCat is talking to the weather station |
| `conditions` | String | Current conditions |
| `forecast`, `shortForecast` | String | WeatherCat's forecast, long and short |
| `pressureTrend` | String | e.g. *Steady*, *Rising Slowly* |
| `dominantWind` | String | Dominant wind direction today, e.g. `SW` |
| `sunrise`, `sunset`, `daylight` | String | Today's sun times and length of daylight |
| `lastSample` | String | When WeatherCat last stored a sample |
| `alertsTriggered`, `alertsTriggeredCount` | String, Integer | Names and number of WeatherCat custom alerts currently triggered |
| `goodPackets`, `badPackets`, `sensorErrors` | Integer | Station communications counters |
| `uptimeHours` | Number | How long WeatherCat has been running |
| `samplePeriod` | Integer | WeatherCat's sampling period, seconds |
| `stationName`, `weathercatVersion`, `rcpVersion`, `units` | String/Integer | About WeatherCat and its settings |

Its state icon is Indigo's *sensor on* icon when all is well, *sensor tripped* when station communications have failed, and *sensor off* when WeatherCat isn't answering.

## Menu items and actions

**Plugins > WeatherCat**

- **Create Devices for All Live Readings**: see [Quick start](#quick-start).
- **Log WeatherCat Channels**: lists every reading WeatherCat offers, with its current value, in the Event Log, plus WeatherCat's version and units. Handy for seeing what your station reports.
- **Refresh Now**: reads everything straight away.

**Actions** (in Action Groups, triggers and schedules: *Type: WeatherCat Actions*)

- **Refresh All WeatherCat Devices Now**.
- **Put a WeatherCat Tag Into a Variable**: runs any WeatherCat web tag and stores the result in an Indigo variable. This reaches anything WeatherCat can report that isn't a device, for example:

| Tag | Gives |
|---|---|
| `STAT$TEMPERATURE:MAX:YESTERDAY$` | Yesterday's high |
| `STAT$TEMPERATURE:MIN:THISMONTH:TIME$` | When this month's low happened |
| `STAT$RAIN:TOTAL:THISMONTH$` | Rain this month (WeatherCat's own total) |
| `STAT$WINDGUST:MAX:HRS(24)$` | Highest gust in the last 24 hours |
| `CF$` | Forecast text |
| `SUNSETLOCAL1$` | Tomorrow's sunset |

Tags are case sensitive and end in `$`. WeatherCat's manual (*Help > WeatherCat Help*, appendix 4, and the STAT$ section) lists them all.

Each Reading device also answers Indigo's **Send Status Request**, which refreshes all WeatherCat devices.

## Units

The plugin always uses **the units set in WeatherCat** (*WeatherCat > Preferences > Units*). WeatherCat sends live values in metric, and the plugin converts them. Highs, lows and 1-hour changes come from WeatherCat already in your units, so everything matches. If you change units in WeatherCat, devices follow within one highs-and-lows interval (5 minutes by default), or straight away with *Refresh Now*.

Soil moisture is shown in centibars.

## Rain readings

WeatherCat offers more than one kind of rain total, and they can differ:

- **Precipitation Daily** (*Rain Today*) and **Precipitation Per Hour** (*Rain Rate*) are WeatherCat's live values.
- **Monthly Rain** and **Annual Rain** come from some stations' consoles (e.g. Davis) and count from whenever the console was last reset.
- WeatherCat's own month and year totals are available with the tag action, e.g. `STAT$RAIN:TOTAL:THISMONTH$`. These only cover the time WeatherCat has been recording.

## Troubleshooting

| Symptom | Check |
|---|---|
| All devices *offline* | Is WeatherCat running? From the Indigo Mac, open `http://127.0.0.1:49255/help` (or WeatherCat's address) in a browser: you should see WeatherCat's *Rich Client Protocol (RCP) Help* page. If WeatherCat is on another Mac, check that Mac's firewall allows WeatherCat incoming connections |
| A device shows *no data* | The station isn't reporting that reading. *Log WeatherCat Channels* lists what it does report |
| A device shows *not found* | WeatherCat no longer has that reading (station changed). Edit the device and pick another |
| No high/low states | Only readings with statistics have them (see [States](#states)), and *Today's high and low* must be ticked. States appear after the first update |
| Values look wrong by a unit conversion | Check *WeatherCat > Preferences > Units*. The Station device's `units` state shows what the plugin read |
| Anything else | Turn on *Debug logging* in the plugin settings and look in Indigo's Event Log, or the plugin's own log in `/Library/Application Support/Perceptive Automation/Indigo <version>/Logs/com.5th-imperium.weathercat/` |

## WeatherCat 4

WeatherCat 4 is in development (beta) at the time of writing. From its published development notes, it keeps the same RCP on port 49255 and adds new readings (lightning, voltages, particulates, a second station and more), which appear in the plugin's reading menu by themselves. It also adds an HTTPS version of RCP on port 49256, which this plugin doesn't use yet. The plugin hasn't been tested with WeatherCat 4.

## How it works

The plugin polls WeatherCat's **Rich Client Protocol** (RCP), plain HTTP on port 49255 that answers with XML property lists:

- `/discovery/channelList` – the readings WeatherCat offers (asked for on every poll, because reading numbers can change);
- `/data/getChannelValue/<n>` – a reading's live value, in metric;
- `/webtag/<tag>` – WeatherCat's web tags: statistics, units, conditions, forecast, sun times;
- `/discovery/systemData` and `/discovery/alertsList` – status and alerts.

Each device remembers its reading by WeatherCat's reading *type* and *name*, not its number. That's what WeatherCat's documentation advises, since numbers can change when the station changes. [docs/weathercat-rcp.md](docs/weathercat-rcp.md) has the details and the quirks found while building this.

## Development

```
WeatherCat.indigoPlugin/Contents/
  Info.plist                     plugin id com.5th-imperium.weathercat, version, API version
  Resources/icon.png             Plugin Store icon (drawn by tools/make_icon.swift)
  Server Plugin/
    wcrcp.py                     RCP client, unit conversion, formatting, Feels Like. No Indigo imports
    plugin.py                    the Indigo plugin
    Devices.xml, PluginConfig.xml, Actions.xml, MenuItems.xml
tests/
  test_wcrcp.py                  unit tests, and the plugin run against a fake Indigo
  fake_indigo.py                 the stand-in for Indigo's `indigo` module
fixtures/rcp/                    real WeatherCat 3.33 RCP replies; index.json maps file -> request
tools/
  capture_fixtures.py            add replies from a running WeatherCat to fixtures/rcp
  live_check.py                  run the plugin once against a running WeatherCat (no Indigo) and print every device
  make_icon.swift                draws the icon
docs/weathercat-rcp.md           notes on WeatherCat's RCP
```

Run the tests (no Indigo or WeatherCat needed):

```
python3 tests/test_wcrcp.py
```

Use Indigo's own Python to be sure, e.g. `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` for Indigo 2025.2.

See what the plugin would make of a running WeatherCat, without touching Indigo:

```
python3 tools/live_check.py [host] [port]
```

Issues and pull requests are welcome.

## Licence

Copyright © 2026 hap67 and contributors. Licensed under the **GNU General Public License v3.0 or later**; see [LICENSE](LICENSE).
