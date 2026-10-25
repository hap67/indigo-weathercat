# WeatherCat's Rich Client Protocol (RCP): notes

Notes for anyone working on this plugin, or reading WeatherCat from their own code. They come from WeatherCat's manual (appendix 7, *WeatherCat Rich Client Protocol*), its built-in help page (`http://<host>:49255/help`), and testing against **WeatherCat 3.33 build 20** with a Davis Vantage station. `fixtures/rcp/` holds real replies.

## Basics

- Plain **HTTP on port 49255**, on all network interfaces. WeatherCat advertises it on Bonjour as `_wcrcps._tcp`. In WeatherCat 3 it's always on.
- Every reply is an **XML property list** dictionary:

| Key | Meaning |
|---|---|
| `result` | The answer: string, number, array or dictionary, depending on the request |
| `error` | `0` = OK, negative = failure: `-1` bad web tag, `-3` channel not found, `-4` wrong number of parameters, `-5` too much data / not found |
| `errorDescription` | `OK`, or English text |
| `serverTime` | UTC, e.g. `2026-10-25 09:28:38 +0000` |
| `processTime` | Seconds, as a string |

Python reads these with `plistlib.loads()`. In other languages, parse the XML: a `<dict>` alternates `<key>` and value elements (`<string>`, `<integer>`, `<real>`, `<true/>`, `<false/>`, `<array>`, `<dict>`).

## Requests

| Request | Returns |
|---|---|
| `/discovery/channelList` | Array of `{channelName, channelNumber, channelType, channelBasicType, channelValid}`, one per channel WeatherCat knows for the station (70 on a Davis Vantage) |
| `/discovery/getChannelOfType/<type>` | The channel number for a channel type, or `-1` with error `-3` |
| `/discovery/systemData` | `{stationCommsStatus, samplePeriod, versString, version, build, RCPVersion, uptime, stationName, stationGoodCommsCount, stationBadCommsCount, stationSensorErrorCount, camera1CapturePeriod}` |
| `/discovery/alertsList` | Array of `{name, triggered}` for WeatherCat's custom alerts |
| `/discovery/customGraphList`, `/discovery/customTextWindowsList` | Arrays of `{name, UID}` |
| `/data/getChannelValue/<number>` | A channel's live value, **always metric** |
| `/data/getData/<type>/<count>/<minutes>` | History: `count` values, newest first, `minutes` apart (max 10 000) |
| `/webtag/<TAG$>` | Any web tag's result, as a string, **in the user's units** |
| `/image/getBasicGraph/<id>[/<w>/<h>]`, `/image/getCustomGraph/<UID>`, `/image/getWebCam` | Images, as a string of hex characters |
| `/help` | An HTML help page (a quick way to check RCP is reachable) |

## Channels

`channelBasicType` says what kind of value a channel holds:

| Basic type | Kind | Metric unit (RCP) |
|---|---|---|
| 0 | None / not known | |
| 1 | Temperature (also dew point, wind chill, heat index, soil, leaf, extra sensors) | °C |
| 2 | Pressure | hPa |
| 3 | Wind speed / gust | km/h |
| 4 | Wind direction | degrees |
| 5 | Precipitation | mm (rate: mm/h) |
| 6 | Relative humidity | % |
| 7 | Cloud base | m |
| 8 | Solar radiation | W/m² |
| 9 | UV index | |
| 10 | Leaf wetness | |
| 11 | Soil moisture | cb |
| 12 | CO₂ | ppm |
| 20–23 | Synthetic channels without units (0–3 decimals) | |

`channelType` identifies the exact channel. Types seen on WeatherCat 3.33:

| Type | Channel | | Type | Channel |
|---|---|---|---|---|
| 1 | Ext. Temperature | | 15–18 | Wind Gust (1 / 5 / 10 / 15 Mins) |
| 2 | Dew Point | | 19–22 | Wind Gust Direction (1 / 5 / 10 / 15 Mins) |
| 3 | Wind Chill | | 23 | Solar Radiation |
| 4 | Pressure | | 24 | UV Index |
| 5 | Wind Speed | | 25–31 | Aux. Temp 1–7 |
| 6 | Wind Speed (10 Min. Average) | | 33–39 | Aux. Humidity 1–7 |
| 7 | Wind Direction | | 41–44 | Leaf Wetness 1–4 |
| 8 | Average Wind Direction | | 45–48 | Soil Moisture 1–4 |
| 9 | Precipitation Per Hour | | 49–52 | Leaf Temperature 1–4 |
| 10 | Precipitation Daily | | 53–56 | Soil Temperature 1–4 |
| 11 | Precipitation Total (raw counter) | | 57, 58 | Monthly Rain, Annual Rain (station console) |
| 12 | Ext. Humidity | | 59–61 | Daily / Monthly / Annual E.T. |
| 13 | Int. Humidity | | 500, 501 | Calculated Cloud Base, Calculated Heat Index |
| 14 | Int. Temperature | | 503–507 | Synthetic Channel 1–5 |
| | | | 1000–1003 | Comms Count, Comms Errors (Timeout), Comms Errors (CRC), Sensor Errors |

`channelValid` is `1` when the station is reporting that channel.

## Web tags worth knowing

| Tag | Example | Notes |
|---|---|---|
| `STAT$<ITEM>:<TYPE>[:<PERIOD>][:TIME]$` | `STAT$TEMPERATURE:MAX:TODAY$` → `53.7`; add `:TIME` → `3:48 AM` | Statistics. Items: `TEMPERATURE, DEWPOINT, WINDCHILL, HEATINDEX, PRESSURE, WINDSPEED, AVERAGEWINDSPEED, WINDGUST, WINDDIRECTION, EXTHUMIDITY, INTHUMIDITY, INTTEMPERATURE, UV, SOLAR, RAIN, DAILYRAIN, WINDRUN…` Types: `CURRENT, MIN, MAX, AVERAGE, TOTAL, DELTA1, DELTA24, 24HRSAGO`. Periods: `TODAY, YESTERDAY, THISWEEK, THISMONTH, THISYEAR, ALLTIME, HRS(n)…` |
| `CC$`, `CF$`, `CSF$` | `Overcast` | Current conditions; forecast, long and short |
| `BTTEXT$` | `Steady` | Pressure trend |
| `DOMWDTEXT$` | `SW` | Dominant wind direction today |
| `CU$` | `25 Oct 2026 4:34 AM` | Time of the last sample |
| `SUNRISELOCAL$`, `SUNSETLOCAL$`, `DAYLIGHTTIME$` | `6:59 AM` | Add `1` before the `$` for tomorrow |
| `COMMSFAILFLAG$` | `0` | `1` if WeatherCat has lost the station |
| `TEMPUNITS$`, `PRESSUREUNITS$`, `WINDSPEEDUNITS$`, `RAINUNITS$`, `HEIGHTUNITS$` | `°F`, `inHg`, `MPH`, `in`, `Feet` | The user's units |
| `AT_US$`, `AT_Aus$`, `HUMIDEX$` | | Apparent temperatures and humidex |

## Quirks found by testing

1. **Don't percent-encode `$ : ( )` in web tags.** WeatherCat doesn't decode `%24` and answers error `-1`. Encode other characters as usual.
2. **The manual's `PRESSUREUNIT$` doesn't work**; `PRESSUREUNITS$` does.
3. **A bad `STAT$` tag still reports error `0`**, with a result starting `***Syntax Error…`. Treat any result starting `***` as an error.
4. **Channel numbers aren't stable.** WeatherCat's manual says not to cache them. Look channels up by type (and name) each time.
5. **`getChannelValue` only takes integers.** `getChannelValue/abc` quietly answers with channel 0. An unknown number gives error `-3`.
6. **"Precipitation Daily" (type 10) reports basic type 0**, not 5.
7. **Station console totals and WeatherCat's own totals differ.** *Monthly Rain* and *Annual Rain* (types 57, 58) are the console's counters. `STAT$RAIN:TOTAL:THISMONTH$` only counts what WeatherCat has recorded.
8. **`STAT$PRESSURE:DELTACHAR$` came back empty**; `BTTEXT$` gives the trend.
9. **Degree signs** arrive as `&#176;` in the XML (`°` once parsed). Older builds could send `Â°`, so test for `F` rather than comparing whole strings.
10. **An empty `alertsList`** is an empty array, not an error.

## Unit conversion used by the plugin

Live channel values are metric whatever WeatherCat displays. The plugin converts them to the units the units tags report:

| Kind | Conversion | Usual decimals |
|---|---|---|
| Temperature | °F = °C × 9/5 + 32 | 1 |
| Pressure | inHg = hPa × 0.0295299830714; mb/hPa unchanged | 2 (inHg), 1 (hPa) |
| Wind | mph = km/h ÷ 1.609344; knots = ÷ 1.852; m/s = ÷ 3.6 | 1 |
| Rain | in = mm ÷ 25.4 | 2 (in), 1 (mm) |
| Height (cloud base) | ft = m × 3.28084 | 0 |
| Humidity, direction, solar, CO₂, soil moisture | unchanged | 0 |
| UV | unchanged | 1 |

Checked against WeatherCat's own `STAT$…:CURRENT$` answers: 11.5 °C → 52.7 °F, 1029.93 hPa → 30.41 inHg, 1.6093 km/h → 1.0 mph.

## WeatherCat 4

From WeatherCat 4's published development notes (development releases 1–19):

- RCP stays on port 49255 and stays compatible. `systemData.RCPVersion` goes from 100 to 101 and 102.
- **HTTPS** on port 49256, with a self-signed certificate WeatherCat creates.
- Images can be base64 instead of hex (add `/1` after width and height).
- A `registration` domain for push notifications to Trixology's WeatherKitten app.
- New channels: lightning (distance, time, count today), voltages, particulates (PM1, PM2.5, PM4, PM10), depth, conductivity, and a **secondary station** whose comms channels are named with `(1)` / `(2)`. New `STAT$` items for these, and an `LLI$` tag for the last lightning event.
- Soil moisture can be % (Ecowitt) as well as cb (Davis).
- A preference can stop individual channels being served over RCP.
- There's still no single "all readings" request, JSON, or push for third-party clients.
