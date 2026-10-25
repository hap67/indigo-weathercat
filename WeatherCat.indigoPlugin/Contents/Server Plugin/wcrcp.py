# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 hap67 and contributors. Part of indigo-weathercat; see LICENSE.
"""WeatherCat Rich Client Protocol (RCP) client, unit handling and formatting.

Plain Python (no Indigo imports), so it can be tested on its own and reused by tools.

RCP is HTTP on port 49255 that answers with an XML plist:
    {result, error (0 = OK, negative = failure), errorDescription, serverTime, processTime}
Channel values (/data/getChannelValue/N) come back in metric units. Web tags (/webtag/TAG$)
come back as strings already in the units chosen in WeatherCat's preferences.

Written against WeatherCat 3.33 (RCP version 100). WeatherCat 4 keeps the same protocol on
port 49255 and adds channels, so nothing here hard-codes the channel list.
"""
import plistlib
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_PORT = 49255

# Characters WeatherCat needs to see as-is in a web tag (it doesn't decode %24 etc.).
TAG_SAFE_CHARS = "$:()"

# channelBasicType values (manual, appendix 7).
BASIC_NONE = 0
BASIC_TEMPERATURE = 1
BASIC_PRESSURE = 2
BASIC_WINDSPEED = 3
BASIC_WINDDIRECTION = 4
BASIC_PRECIPITATION = 5
BASIC_RH = 6
BASIC_CLOUDBASE = 7
BASIC_SOLAR = 8
BASIC_UV = 9
BASIC_LEAF_WETNESS = 10
BASIC_SOIL_MOISTURE = 11
BASIC_CO2 = 12
BASIC_NO_UNITS = 20
BASIC_NO_UNITS_1DP = 21
BASIC_NO_UNITS_2DP = 22
BASIC_NO_UNITS_3DP = 23

# channelType values seen on WeatherCat 3.33 that need special handling.
TYPE_PRECIP_RATE = 9          # Precipitation Per Hour
TYPE_PRECIP_DAILY = 10        # Precipitation Daily (reports basic type 0)
TYPE_PRECIP_RAW_TOTAL = 11    # Precipitation Total (raw station counter)
FIRST_COMMS_TYPE = 1000       # Comms Count, Comms Errors, Sensor Errors (1000-1003)

# The kinds of reading the plugin knows how to show.
KIND_TEMPERATURE = "temperature"
KIND_PRESSURE = "pressure"
KIND_WIND = "wind"
KIND_DIRECTION = "direction"
KIND_RAIN = "rain"
KIND_RAIN_RATE = "rainRate"
KIND_HUMIDITY = "humidity"
KIND_HEIGHT = "height"
KIND_SOLAR = "solar"
KIND_UV = "uv"
KIND_LEAF_WETNESS = "leafWetness"
KIND_SOIL_MOISTURE = "soilMoisture"
KIND_CO2 = "co2"
KIND_COUNT = "count"
KIND_PLAIN = "plain"

# STAT$ item names for channel types whose daily high/low WeatherCat can report.
STAT_ITEMS = {
    1: "TEMPERATURE",
    2: "DEWPOINT",
    3: "WINDCHILL",
    4: "PRESSURE",
    5: "WINDSPEED",
    6: "AVERAGEWINDSPEED",
    12: "EXTHUMIDITY",
    13: "INTHUMIDITY",
    14: "INTTEMPERATURE",
    15: "WINDGUST",
    23: "SOLAR",
    24: "UV",
    501: "HEATINDEX",
}

COMPASS_POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

# The unit tags WeatherCat answers, and what we expect back.
UNIT_TAGS = {
    "temperature": "TEMPUNITS$",      # °C or °F
    "pressure": "PRESSUREUNITS$",     # mb, hPa or inHg (the manual's PRESSUREUNIT$ fails)
    "wind": "WINDSPEEDUNITS$",        # km/h, MPH, Knots or m/s
    "rain": "RAINUNITS$",             # mm or in
    "height": "HEIGHTUNITS$",         # Metres or Feet
}


class RCPError(Exception):
    """WeatherCat couldn't be reached, or answered with an error."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class Channel:
    """One entry from /discovery/channelList."""

    def __init__(self, number, channel_type, basic_type, name, valid):
        self.number = number
        self.type = channel_type
        self.basic_type = basic_type
        self.name = name
        self.valid = valid

    @classmethod
    def from_dict(cls, d):
        return cls(int(d.get("channelNumber", -1)), int(d.get("channelType", -1)),
                   int(d.get("channelBasicType", 0)), str(d.get("channelName", "")),
                   bool(d.get("channelValid", 0)))

    @property
    def key(self):
        """How a device remembers its channel: type plus name. Numbers can change between
        launches (and do when a second station is added in WeatherCat 4)."""
        return channel_key(self.type, self.name)

    @property
    def is_comms(self):
        return self.type >= FIRST_COMMS_TYPE and self.type < FIRST_COMMS_TYPE + 100

    @property
    def kind(self):
        return kind_for(self.type, self.basic_type)

    @property
    def stat_item(self):
        return STAT_ITEMS.get(self.type)

    def __repr__(self):
        return "Channel(%d, type=%d, basic=%d, %r, valid=%s)" % (
            self.number, self.type, self.basic_type, self.name, self.valid)


def channel_key(channel_type, name):
    """Indigo menu values can't contain commas or semicolons, so those become '_'."""
    return "%d|%s" % (int(channel_type), str(name).replace(",", "_").replace(";", "_"))


def split_channel_key(key):
    """'1|Ext. Temperature' -> (1, 'Ext. Temperature'). Returns (None, '') if malformed."""
    try:
        t, _, name = str(key).partition("|")
        return int(t), name
    except ValueError:
        return None, ""


def find_channel(channels, key):
    """Find a device's channel: exact type and name first, then the only channel of that type."""
    wanted_type, wanted_name = split_channel_key(key)
    if wanted_type is None:
        return None
    for c in channels:
        if c.key == key:
            return c
    same_type = [c for c in channels if c.type == wanted_type]
    if len(same_type) == 1:
        return same_type[0]
    return None


def kind_for(channel_type, basic_type):
    if channel_type >= FIRST_COMMS_TYPE and channel_type < FIRST_COMMS_TYPE + 100:
        return KIND_COUNT
    if channel_type == TYPE_PRECIP_RATE:
        return KIND_RAIN_RATE
    if channel_type == TYPE_PRECIP_DAILY:
        return KIND_RAIN
    return {
        BASIC_TEMPERATURE: KIND_TEMPERATURE,
        BASIC_PRESSURE: KIND_PRESSURE,
        BASIC_WINDSPEED: KIND_WIND,
        BASIC_WINDDIRECTION: KIND_DIRECTION,
        BASIC_PRECIPITATION: KIND_RAIN,
        BASIC_RH: KIND_HUMIDITY,
        BASIC_CLOUDBASE: KIND_HEIGHT,
        BASIC_SOLAR: KIND_SOLAR,
        BASIC_UV: KIND_UV,
        BASIC_LEAF_WETNESS: KIND_LEAF_WETNESS,
        BASIC_SOIL_MOISTURE: KIND_SOIL_MOISTURE,
        BASIC_CO2: KIND_CO2,
    }.get(basic_type, KIND_PLAIN)


class Units:
    """The units chosen in WeatherCat's preferences, as WeatherCat spells them."""

    def __init__(self, temperature="°C", pressure="hPa", wind="km/h", rain="mm", height="Metres"):
        self.temperature = temperature
        self.pressure = pressure
        self.wind = wind
        self.rain = rain
        self.height = height

    @property
    def fahrenheit(self):
        return "F" in self.temperature.upper()

    @property
    def inhg(self):
        return "INHG" in self.pressure.upper()

    @property
    def inches(self):
        return self.rain.strip().lower() == "in"

    @property
    def feet(self):
        return self.height.strip().lower().startswith("f")

    def as_dict(self):
        return {"temperature": self.temperature, "pressure": self.pressure, "wind": self.wind,
                "rain": self.rain, "height": self.height}

    def __eq__(self, other):
        return isinstance(other, Units) and self.as_dict() == other.as_dict()

    def __repr__(self):
        return "Units(%r)" % self.as_dict()


def convert(value, kind, units):
    """Metric channel value -> (value in WeatherCat's units, unit label, decimal places)."""
    if value is None:
        return None, "", 0
    v = float(value)
    if kind == KIND_TEMPERATURE:
        if units.fahrenheit:
            return v * 9.0 / 5.0 + 32.0, "°F", 1
        return v, "°C", 1
    if kind == KIND_PRESSURE:
        if units.inhg:
            return v * 0.0295299830714, "inHg", 2
        return v, (units.pressure or "hPa"), 1
    if kind == KIND_WIND:
        w = units.wind.strip().lower()
        if w == "mph":
            return v / 1.609344, "mph", 1
        if w.startswith("knot"):
            return v / 1.852, "kn", 1
        if w == "m/s":
            return v / 3.6, "m/s", 1
        return v, "km/h", 1
    if kind == KIND_DIRECTION:
        return v, "°", 0
    if kind == KIND_RAIN:
        if units.inches:
            return v / 25.4, "in", 2
        return v, "mm", 1
    if kind == KIND_RAIN_RATE:
        if units.inches:
            return v / 25.4, "in/h", 2
        return v, "mm/h", 1
    if kind == KIND_HUMIDITY:
        return v, "%", 0
    if kind == KIND_HEIGHT:
        if units.feet:
            return v * 3.28084, "ft", 0
        return v, "m", 0
    if kind == KIND_SOLAR:
        return v, "W/m²", 0
    if kind == KIND_UV:
        return v, "", 1
    if kind == KIND_LEAF_WETNESS:
        return v, "", 0
    if kind == KIND_SOIL_MOISTURE:
        return v, "cb", 0
    if kind == KIND_CO2:
        return v, "ppm", 0
    if kind == KIND_COUNT:
        return v, "", 0
    return v, "", 1


# "Feels like": a reading the plugin works out from WeatherCat's channels.
FEELS_LIKE_KEY = "feelsLike|Feels Like"
FEELS_LIKE_NAME = "Feels Like (heat index, wind chill or temperature)"
TYPE_TEMPERATURE = 1
TYPE_WIND_CHILL = 3
TYPE_WIND_SPEED = 5
TYPE_HEAT_INDEX = 501

HEAT_INDEX_FROM_C = (80.0 - 32.0) * 5.0 / 9.0    # 80 °F
WIND_CHILL_BELOW_C = (50.0 - 32.0) * 5.0 / 9.0   # 50 °F
WIND_CHILL_WIND_KMH = 3.0 * 1.609344             # 3 mph


def is_virtual_key(key):
    return str(key) == FEELS_LIKE_KEY


def feels_like(temp_c, heat_index_c=None, wind_chill_c=None, wind_kmh=None):
    """US National Weather Service rule: heat index from 80 °F, wind chill at 50 °F and below
    with wind of at least 3 mph, otherwise the air temperature. All metric, as RCP sends them.
    Returns (value °C, 'Heat index' | 'Wind chill' | 'Temperature')."""
    if heat_index_c is not None and temp_c >= HEAT_INDEX_FROM_C:
        return heat_index_c, "Heat index"
    if wind_chill_c is not None and wind_kmh is not None and temp_c <= WIND_CHILL_BELOW_C \
            and wind_kmh >= WIND_CHILL_WIND_KMH:
        return wind_chill_c, "Wind chill"
    return temp_c, "Temperature"


def first_of_type(channels, channel_type):
    """The first valid channel of a type (the primary station's, if there are two)."""
    for c in channels:
        if c.type == channel_type and c.valid:
            return c
    return None


def compass(degrees):
    """231 -> 'SW'."""
    try:
        d = float(degrees) % 360.0
    except (TypeError, ValueError):
        return ""
    return COMPASS_POINTS[int((d + 11.25) // 22.5) % 16]


def format_value(value, unit, decimals, kind=None):
    """Text Indigo shows in its device list, e.g. '53.2 °F', '231° SW', '82%'."""
    if value is None:
        return ""
    text = "%.*f" % (decimals, value)
    if kind == KIND_DIRECTION:
        return "%s° %s" % (text, compass(value))
    if not unit:
        return text
    if unit in ("%", "°"):
        return text + unit
    return "%s %s" % (text, unit)


def parse_number(text):
    """Turn a web tag answer like '53.7' into a float; None if it isn't a number."""
    try:
        return float(str(text).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


class RCPClient:
    """Talks to one WeatherCat. `fetch` can be swapped out in tests: fetch(path) -> bytes."""

    def __init__(self, host="127.0.0.1", port=DEFAULT_PORT, timeout=5.0, fetch=None):
        self.host = host or "127.0.0.1"
        self.port = int(port or DEFAULT_PORT)
        self.timeout = float(timeout)
        self._fetch = fetch or self._http_fetch

    @property
    def base_url(self):
        return "http://%s:%d" % (self.host, self.port)

    def _http_fetch(self, path):
        url = self.base_url + path
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as reply:
                return reply.read()
        except urllib.error.URLError as e:
            raise RCPError("Can't reach WeatherCat at %s (%s)" % (self.base_url, getattr(e, "reason", e)))
        except OSError as e:  # timeouts, connection resets
            raise RCPError("Can't reach WeatherCat at %s (%s)" % (self.base_url, e))

    def request(self, path):
        """GET a path and return the reply's `result`, raising RCPError on any failure."""
        raw = self._fetch(path)
        try:
            reply = plistlib.loads(raw)
        except Exception as e:
            raise RCPError("WeatherCat sent a reply that isn't a plist (%s)" % e)
        if not isinstance(reply, dict):
            raise RCPError("WeatherCat sent an unexpected reply")
        code = int(reply.get("error", 0) or 0)
        if code != 0:
            raise RCPError("WeatherCat error %d: %s (%s)" % (code, reply.get("errorDescription", ""), path), code)
        return reply.get("result")

    # discovery domain
    def system_data(self):
        result = self.request("/discovery/systemData")
        return result if isinstance(result, dict) else {}

    def channels(self):
        result = self.request("/discovery/channelList") or []
        return [Channel.from_dict(d) for d in result if isinstance(d, dict)]

    def alerts(self):
        """[(name, triggered)] for WeatherCat's custom alerts."""
        result = self.request("/discovery/alertsList") or []
        return [(str(d.get("name", "")), bool(d.get("triggered", False))) for d in result if isinstance(d, dict)]

    # data domain
    def channel_value(self, number):
        result = self.request("/data/getChannelValue/%d" % int(number))
        try:
            return float(result)
        except (TypeError, ValueError):
            raise RCPError("WeatherCat sent a non-numeric value for channel %d: %r" % (int(number), result))

    # webtag domain
    def webtag(self, tag):
        """Process one web tag, e.g. 'STAT$TEMPERATURE:MAX:TODAY$'. WeatherCat reports a bad
        STAT$ tag as text starting '***' with error 0, so that's treated as an error too."""
        tag = str(tag).strip()
        result = self.request("/webtag/" + urllib.parse.quote(tag, safe=TAG_SAFE_CHARS))
        text = "" if result is None else str(result)
        if text.startswith("***"):
            raise RCPError("WeatherCat couldn't process %s: %s" % (tag, text.strip("* ")))
        return text

    def units(self):
        values = {}
        for field, tag in UNIT_TAGS.items():
            try:
                values[field] = self.webtag(tag)
            except RCPError:
                pass
        return Units(**{k: v for k, v in values.items() if v})

    def daily_stats(self, stat_item):
        """Today's high/low (with times) and the 1-hour change for one STAT$ item, all in
        WeatherCat's units. Missing pieces come back as None."""
        out = {}
        for key, tag in (("todayHigh", "STAT$%s:MAX:TODAY$"), ("todayHighTime", "STAT$%s:MAX:TODAY:TIME$"),
                         ("todayLow", "STAT$%s:MIN:TODAY$"), ("todayLowTime", "STAT$%s:MIN:TODAY:TIME$"),
                         ("change1h", "STAT$%s:DELTA1$")):
            try:
                text = self.webtag(tag % stat_item)
            except RCPError:
                out[key] = None
                continue
            out[key] = text if key.endswith("Time") else parse_number(text)
        return out
