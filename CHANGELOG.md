# Changelog

Versions follow `X.Y.Z`. The GitHub release tag for each version matches `PluginVersion` in `Info.plist`, as the Indigo Plugin Store requires.

## 0.3.0 – 2026-10-25

First public release.

- Plugin Store icon (`Contents/Resources/icon.png`).
- Support and help links point to the GitHub repository.
- Full documentation (README, `docs/weathercat-rcp.md`), changelog and GPL-3.0-or-later licence.

## 0.2.1 – 2026-10-25

- **Decimal places** is chosen from a menu (*Usual for this reading*, or 0–4) instead of typed, so the allowed range is visible. Existing settings are kept.

## 0.2.0 – 2026-10-25

- New **Feels Like** reading: heat index from 80 °F, wind chill at 50 °F and below with wind of at least 3 mph, otherwise the air temperature (US National Weather Service rule). The `feelsLikeSource` state says which. *Create Devices for All Live Readings* adds it.
- The **Reading** menu lists readings without a device first, then (after separators) readings already used, labelled with their device, station status counters, and readings with no data. A new device starts on the first reading without a device.
- Saving a reading that another device already shows is refused, with the other device's name.
- Reading keys never contain commas or semicolons (Indigo menu values can't).
- Friendlier names for created devices: *Heat Index*, *Cloud Base*.

## 0.1.0 – 2026-10-25

First version.

- **WeatherCat Reading** sensor devices: any WeatherCat reading, in WeatherCat's units, with today's high and low (and times) and 1-hour change where WeatherCat keeps statistics, and a compass point for wind directions.
- **WeatherCat Station** device: status, conditions, forecast, pressure trend, dominant wind, sun times, triggered alerts, communications counters, uptime, versions and units.
- Menu items: *Create Devices for All Live Readings*, *Log WeatherCat Channels*, *Refresh Now*.
- Actions: *Refresh All WeatherCat Devices Now*, *Put a WeatherCat Tag Into a Variable*.
- Offline, *no data* and *not found* error states; automatic recovery when WeatherCat answers again.
