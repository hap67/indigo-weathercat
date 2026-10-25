# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 hap67 and contributors. Part of indigo-weathercat; see LICENSE.
"""WeatherCat plugin for Indigo.

Reads WeatherCat over its Rich Client Protocol (HTTP, port 49255) and shows:
  * one "WeatherCat Reading" sensor device per reading (outdoor temperature, pressure, gusts…),
    with today's high/low and 1-hour change where WeatherCat keeps them;
  * one "WeatherCat Station" device for status, conditions, forecast, sun times and alerts.

All RCP and unit handling lives in wcrcp.py, which has no Indigo dependency and is tested
on its own (tests/test_wcrcp.py).
"""
import logging
import time

import indigo  # provided by Indigo

import wcrcp
from wcrcp import RCPClient, RCPError

READING = "wcReading"
STATION = "wcStation"
FOLDER_NAME = "WeatherCat"

# Friendlier names for "Create Devices for All Live Readings".
FRIENDLY_NAMES = {
    "Ext. Temperature": "Outdoor Temperature",
    "Ext. Humidity": "Outdoor Humidity",
    "Int. Temperature": "Indoor Temperature",
    "Int. Humidity": "Indoor Humidity",
    "Precipitation Daily": "Rain Today",
    "Precipitation Per Hour": "Rain Rate",
    "Monthly Rain": "Rain This Month (console)",
    "Annual Rain": "Rain This Year (console)",
    "Calculated Heat Index": "Heat Index",
    "Calculated Cloud Base": "Cloud Base",
}

KIND_FEELS_LIKE = "feelsLike"
SEPARATOR = (-1, "%%separator%%")

# Indigo's state icons by kind of reading (looked up by name, so a missing one falls back).
IMAGE_FOR_KIND = {
    wcrcp.KIND_TEMPERATURE: "TemperatureSensor",
    wcrcp.KIND_HUMIDITY: "HumiditySensor",
    wcrcp.KIND_WIND: "WindSpeedSensor",
    wcrcp.KIND_DIRECTION: "WindDirectionSensor",
    wcrcp.KIND_SOLAR: "LightSensor",
    wcrcp.KIND_UV: "LightSensor",
}

# Channels "Create Devices for All Live Readings" leaves out (still selectable by hand).
SKIP_WHEN_CREATING = {wcrcp.TYPE_PRECIP_RAW_TOTAL}


def _device(dev_id):
    """The device with this id, or None if it has been deleted."""
    try:
        return indigo.devices[dev_id]
    except KeyError:
        return None


def _int(value, default, minimum=None):
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None and n < minimum:
        return default
    return n


class Plugin(indigo.PluginBase):

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs, **kwargs):
        super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs, **kwargs)
        self.client = None
        self.reading_ids = set()
        self.station_ids = set()
        self.channels = []
        self.units = wcrcp.Units()
        self.units_known = False
        self.online = None          # None = not tried yet
        self.next_poll = 0.0
        self.next_stats = 0.0
        self.images = {}            # device id -> last state image name
        self._apply_prefs(plugin_prefs)

    # ---------------------------------------------------------------- preferences

    def _apply_prefs(self, prefs):
        self.debug = bool(prefs.get("showDebugInfo", False))
        self.indigo_log_handler.setLevel(logging.DEBUG if self.debug else logging.INFO)
        self.poll_seconds = _int(prefs.get("pollSeconds"), 30, 5)
        self.stats_seconds = _int(prefs.get("statsMinutes"), 5, 1) * 60
        self.client = RCPClient(host=(prefs.get("host") or "127.0.0.1").strip(),
                                port=_int(prefs.get("port"), wcrcp.DEFAULT_PORT, 1))

    def validatePrefsConfigUi(self, values):
        errors = indigo.Dict()
        if not (values.get("host") or "").strip():
            errors["host"] = "Enter WeatherCat's address (127.0.0.1 if it runs on this Mac)."
        if _int(values.get("port"), None, 1) is None:
            errors["port"] = "Enter a port number (WeatherCat's RCP uses 49255)."
        if _int(values.get("pollSeconds"), None, 5) is None:
            errors["pollSeconds"] = "Enter a whole number of seconds, 5 or more."
        if _int(values.get("statsMinutes"), None, 1) is None:
            errors["statsMinutes"] = "Enter a whole number of minutes, 1 or more."
        if errors:
            return False, values, errors
        return True, values

    def closedPrefsConfigUi(self, values, user_cancelled):
        if user_cancelled:
            return
        self._apply_prefs(values)
        self.online = None
        self._refresh_soon()

    # ---------------------------------------------------------------- lifecycle

    def startup(self):
        self.logger.debug("WeatherCat plugin starting; RCP at %s", self.client.base_url)

    def deviceStartComm(self, dev):
        if dev.deviceTypeId == READING:
            self.reading_ids.add(dev.id)
        elif dev.deviceTypeId == STATION:
            self.station_ids.add(dev.id)
        dev.stateListOrDisplayStateIdChanged()
        self._refresh_soon()

    def deviceStopComm(self, dev):
        self.reading_ids.discard(dev.id)
        self.station_ids.discard(dev.id)
        self.images.pop(dev.id, None)

    def runConcurrentThread(self):
        try:
            while True:
                now = time.time()
                if now >= self.next_poll:
                    with_stats = now >= self.next_stats
                    try:
                        self.poll(with_stats)
                    except self.StopThread:
                        raise
                    except Exception:
                        self.logger.exception("Unexpected error while reading WeatherCat")
                    self.next_poll = time.time() + self.poll_seconds
                    if with_stats:
                        self.next_stats = time.time() + self.stats_seconds
                self.sleep(1)
        except self.StopThread:
            pass

    def _refresh_soon(self, with_stats=True):
        self.next_poll = 0.0
        if with_stats:
            self.next_stats = 0.0

    # ---------------------------------------------------------------- device states

    def getDeviceStateList(self, dev):
        states = super().getDeviceStateList(dev)
        if dev.deviceTypeId != READING:
            return states
        props = dev.pluginProps
        if props.get("kind") == wcrcp.KIND_DIRECTION:
            states.append(self.getDeviceStateDictForStringType("compass", "Compass point", "Compass point"))
        if props.get("kind") == KIND_FEELS_LIKE:
            states.append(self.getDeviceStateDictForStringType(
                "feelsLikeSource", "Feels like is using (Heat index, Wind chill or Temperature)",
                "Feels like is using"))
        if props.get("showStats", True) and props.get("statItem"):
            states.append(self.getDeviceStateDictForNumberType("todayHigh", "Today's high", "Today's high"))
            states.append(self.getDeviceStateDictForStringType("todayHighTime", "Time of today's high", "Time of today's high"))
            states.append(self.getDeviceStateDictForNumberType("todayLow", "Today's low", "Today's low"))
            states.append(self.getDeviceStateDictForStringType("todayLowTime", "Time of today's low", "Time of today's low"))
            states.append(self.getDeviceStateDictForNumberType("change1h", "Change in the last hour", "Change in the last hour"))
        return states

    # ---------------------------------------------------------------- polling

    def poll(self, with_stats):
        if not self.reading_ids and not self.station_ids:
            return
        try:
            self.channels = self.client.channels()
            if with_stats or not self.units_known:
                self._update_units(self.client.units())
        except RCPError as e:
            self._went_offline(e)
            return
        if self.online is not True:
            if self.online is False:
                self.logger.info("WeatherCat is answering again")
            self.online = True

        for dev_id in list(self.reading_ids):
            dev = _device(dev_id)
            if dev is not None:
                try:
                    self._update_reading(dev, with_stats)
                except RCPError as e:
                    self.logger.debug("%s: %s", dev.name, e)
                    dev.setErrorStateOnServer("error")
        for dev_id in list(self.station_ids):
            dev = _device(dev_id)
            if dev is not None:
                try:
                    self._update_station(dev, with_stats)
                except RCPError as e:
                    self.logger.debug("%s: %s", dev.name, e)

    def _update_units(self, units):
        if not self.units_known or units != self.units:
            self.logger.debug("WeatherCat units: %s", units.as_dict())
        if self.units_known and units != self.units:
            self.logger.info("WeatherCat's units changed; updating devices")
        self.units = units
        self.units_known = True

    def _went_offline(self, error):
        if self.online is not False:
            self.logger.error("%s. Devices will update when it answers again.", error)
        self.online = False
        for dev_id in list(self.reading_ids):
            dev = _device(dev_id)
            if dev is not None:
                dev.setErrorStateOnServer("offline")
        for dev_id in list(self.station_ids):
            dev = _device(dev_id)
            if dev is not None:
                dev.updateStatesOnServer([
                    {"key": "online", "value": False},
                    {"key": "status", "value": "WeatherCat not answering"},
                ])
                self._set_image(dev, "SensorOff")

    def _set_image(self, dev, name):
        if self.images.get(dev.id) == name:
            return
        image = getattr(indigo.kStateImageSel, name, None)
        if image is None:
            image = indigo.kStateImageSel.SensorOn
        dev.updateStateImageOnServer(image)
        self.images[dev.id] = name

    def _update_reading(self, dev, with_stats):
        props = dev.pluginProps
        if wcrcp.is_virtual_key(props.get("channelKey", "")):
            self._update_feels_like(dev)
            return
        channel = wcrcp.find_channel(self.channels, props.get("channelKey", ""))
        if channel is None:
            dev.updateStateOnServer("hasData", False)
            dev.setErrorStateOnServer("not found")
            return

        # Keep the device's stored kind/STAT item in step with WeatherCat (decides its states).
        stat_item = channel.stat_item or ""
        if props.get("kind") != channel.kind or props.get("statItem", "") != stat_item \
                or props.get("address") != channel.name:
            props["kind"] = channel.kind
            props["statItem"] = stat_item
            props["address"] = channel.name
            dev.replacePluginPropsOnServer(props)
            dev = indigo.devices[dev.id]
            dev.stateListOrDisplayStateIdChanged()

        if not channel.valid:
            dev.updateStatesOnServer([
                {"key": "hasData", "value": False},
                {"key": "channelName", "value": channel.name},
            ])
            dev.setErrorStateOnServer("no data")
            return

        raw = self.client.channel_value(channel.number)
        value, unit, decimals = wcrcp.convert(raw, channel.kind, self.units)
        decimals = _int(props.get("decimals"), decimals, 0)
        text = wcrcp.format_value(value, unit, decimals, channel.kind)
        updates = [
            {"key": "sensorValue", "value": round(value, decimals), "uiValue": text, "decimalPlaces": decimals},
            {"key": "channelName", "value": channel.name},
            {"key": "units", "value": unit},
            {"key": "hasData", "value": True},
        ]
        if channel.kind == wcrcp.KIND_DIRECTION:
            updates.append({"key": "compass", "value": wcrcp.compass(value)})

        if with_stats and props.get("showStats", True) and stat_item:
            stats = self.client.daily_stats(stat_item)
            for key in ("todayHigh", "todayLow", "change1h"):
                v = stats.get(key)
                if v is not None:
                    updates.append({"key": key, "value": round(v, decimals), "decimalPlaces": decimals,
                                    "uiValue": wcrcp.format_value(v, unit, decimals, channel.kind)})
            for key in ("todayHighTime", "todayLowTime"):
                updates.append({"key": key, "value": stats.get(key) or ""})

        dev.updateStatesOnServer(updates)
        dev.setErrorStateOnServer(None)
        self._set_image(dev, IMAGE_FOR_KIND.get(channel.kind, "SensorOn"))
        self.logger.debug("%s = %s", dev.name, text)

    def _update_feels_like(self, dev):
        """Heat index, wind chill or air temperature, by the US National Weather Service rule."""
        props = dev.pluginProps
        if props.get("kind") != KIND_FEELS_LIKE or props.get("address") != "Feels Like":
            props["kind"] = KIND_FEELS_LIKE
            props["statItem"] = ""
            props["address"] = "Feels Like"
            dev.replacePluginPropsOnServer(props)
            dev = indigo.devices[dev.id]
            dev.stateListOrDisplayStateIdChanged()

        def value_of(channel_type):
            c = wcrcp.first_of_type(self.channels, channel_type)
            return None if c is None else self.client.channel_value(c.number)

        temp = value_of(wcrcp.TYPE_TEMPERATURE)
        if temp is None:
            dev.updateStateOnServer("hasData", False)
            dev.setErrorStateOnServer("no data")
            return
        value_c, source = wcrcp.feels_like(temp, value_of(wcrcp.TYPE_HEAT_INDEX),
                                           value_of(wcrcp.TYPE_WIND_CHILL), value_of(wcrcp.TYPE_WIND_SPEED))
        value, unit, decimals = wcrcp.convert(value_c, wcrcp.KIND_TEMPERATURE, self.units)
        decimals = _int(props.get("decimals"), decimals, 0)
        text = wcrcp.format_value(value, unit, decimals, wcrcp.KIND_TEMPERATURE)
        dev.updateStatesOnServer([
            {"key": "sensorValue", "value": round(value, decimals), "uiValue": text, "decimalPlaces": decimals},
            {"key": "feelsLikeSource", "value": source},
            {"key": "channelName", "value": "Feels Like"},
            {"key": "units", "value": unit},
            {"key": "hasData", "value": True},
        ])
        dev.setErrorStateOnServer(None)
        self._set_image(dev, "TemperatureSensor")
        self.logger.debug("%s = %s (%s)", dev.name, text, source)

    def _tag(self, tag, default=""):
        try:
            return self.client.webtag(tag)
        except RCPError as e:
            self.logger.debug("%s: %s", tag, e)
            return default

    def _update_station(self, dev, with_stats):
        info = self.client.system_data()
        comms_ok = bool(info.get("stationCommsStatus", True)) and self._tag("COMMSFAILFLAG$", "0").strip() != "1"
        conditions = self._tag("CC$")
        updates = [
            {"key": "online", "value": True},
            {"key": "stationComms", "value": comms_ok},
            {"key": "status", "value": (conditions or "OK") if comms_ok else "Station comms failed"},
            {"key": "conditions", "value": conditions},
            {"key": "pressureTrend", "value": self._tag("BTTEXT$")},
            {"key": "lastSample", "value": self._tag("CU$")},
            {"key": "goodPackets", "value": int(info.get("stationGoodCommsCount", 0) or 0)},
            {"key": "badPackets", "value": int(info.get("stationBadCommsCount", 0) or 0)},
            {"key": "sensorErrors", "value": int(info.get("stationSensorErrorCount", 0) or 0)},
            {"key": "uptimeHours", "value": round(float(info.get("uptime", 0) or 0) / 3600.0, 1), "decimalPlaces": 1},
        ]
        try:
            alerts = self.client.alerts()
        except RCPError as e:
            self.logger.debug("alerts: %s", e)
            alerts = None
        if alerts is not None:
            triggered = [name for name, on in alerts if on]
            updates.append({"key": "alertsTriggered", "value": ", ".join(triggered)})
            updates.append({"key": "alertsTriggeredCount", "value": len(triggered)})
        if with_stats:
            updates += [
                {"key": "forecast", "value": self._tag("CF$")},
                {"key": "shortForecast", "value": self._tag("CSF$")},
                {"key": "dominantWind", "value": self._tag("DOMWDTEXT$")},
                {"key": "sunrise", "value": self._tag("SUNRISELOCAL$")},
                {"key": "sunset", "value": self._tag("SUNSETLOCAL$")},
                {"key": "daylight", "value": self._tag("DAYLIGHTTIME$")},
                {"key": "samplePeriod", "value": int(info.get("samplePeriod", 0) or 0)},
                {"key": "stationName", "value": str(info.get("stationName", ""))},
                {"key": "weathercatVersion", "value": " ".join(str(info.get("versString", "")).split())},
                {"key": "rcpVersion", "value": int(info.get("RCPVersion", 0) or 0)},
                {"key": "units", "value": ", ".join(v for v in self.units.as_dict().values())},
            ]
        dev.updateStatesOnServer(updates)
        self._set_image(dev, "SensorOn" if comms_ok else "SensorTripped")

    # ---------------------------------------------------------------- device config UI

    def _used_readings(self, except_id=0):
        """{channelKey: device name} for this plugin's reading devices, leaving one out."""
        used = {}
        for dev in indigo.devices.iter("self"):
            if dev.deviceTypeId == READING and dev.id != except_id:
                key = dev.pluginProps.get("channelKey", "")
                if key:
                    used.setdefault(key, dev.name)
        return used

    def channel_menu(self, filter="", valuesDict=None, typeId="", targetId=0):
        """Readings without a device first; then those already used, station status counters
        and readings the station doesn't report, each group after a separator."""
        current = (valuesDict or {}).get("channelKey", "")
        try:
            channels = self.client.channels()
        except RCPError as e:
            self.logger.error("%s", e)
            items = [(current, "(current choice)")] if current else []
            return items + [("", "WeatherCat isn't answering")]
        used = self._used_readings(targetId)
        live = [c for c in channels if c.valid and not c.is_comms]
        feels = (wcrcp.FEELS_LIKE_KEY, wcrcp.FEELS_LIKE_NAME)

        free = [(c.key, c.name) for c in live if c.key not in used]
        taken = [(c.key, "%s (used by %s)" % (c.name, used[c.key])) for c in live if c.key in used]
        if feels[0] in used:
            taken.append((feels[0], "%s (used by %s)" % (feels[1], used[feels[0]])))
        else:
            free.append(feels)
        groups = [
            free,
            taken,
            [(c.key, "%s (station status)" % c.name) for c in channels if c.valid and c.is_comms],
            [(c.key, "%s (no data)" % c.name) for c in channels if not c.valid],
        ]
        items = []
        for group in groups:
            if group:
                if items:
                    items.append(SEPARATOR)
                items += group
        if current and current not in {k for k, _ in items}:
            items.insert(0, (current, "%s (not found)" % wcrcp.split_channel_key(current)[1]))
        return items

    def getDeviceConfigUiValues(self, plugin_props, type_id, dev_id):
        """A new reading device starts on the first reading that has no device yet, so the menu
        opens at the top rather than the bottom."""
        values = indigo.Dict(plugin_props)
        if type_id == READING and not values.get("channelKey"):
            first = next((k for k, _ in self.channel_menu(valuesDict=values, targetId=dev_id)
                          if k not in ("", -1)), "")
            if first:
                values["channelKey"] = first
        return values, indigo.Dict()

    def validateDeviceConfigUi(self, values, type_id, dev_id):
        if type_id != READING:
            return True, values
        errors = indigo.Dict()
        key = str(values.get("channelKey", "") or "")
        virtual = wcrcp.is_virtual_key(key)
        if not key or key == "-1" or (not virtual and wcrcp.split_channel_key(key)[0] is None):
            errors["channelKey"] = "Choose a reading."
        else:
            other = self._used_readings(dev_id).get(key)
            if other:
                errors["channelKey"] = "Already used by \"%s\". Choose another reading." % other
        decimals = (values.get("decimals") or "").strip()
        if decimals and (_int(decimals, None, 0) is None or int(decimals) > 4):
            errors["decimals"] = "Choose a number of decimal places from the menu."
        if errors:
            return False, values, errors
        if virtual:
            values["address"] = "Feels Like"
            values["kind"] = KIND_FEELS_LIKE
            values["statItem"] = ""
            return True, values
        values["address"] = wcrcp.split_channel_key(key)[1]
        channel = wcrcp.find_channel(self.channels, key)
        if channel is not None:
            values["address"] = channel.name
            values["kind"] = channel.kind
            values["statItem"] = channel.stat_item or ""
        return True, values

    # ---------------------------------------------------------------- actions & menus

    def actionControlUniversal(self, action, dev):
        if action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info("Refreshing %s", dev.name)
            self._refresh_soon()

    def action_refresh_now(self, action, dev=None, caller_waiting_for_result=None):
        self._refresh_soon()

    def menu_refresh_now(self):
        self.logger.info("Refreshing all WeatherCat devices")
        self._refresh_soon()

    def action_tag_to_variable(self, action, dev=None, caller_waiting_for_result=None):
        tag = (action.props.get("tag") or "").strip()
        var_id = _int(action.props.get("variableId"), None)
        if not tag or var_id is None:
            self.logger.error("Put a WeatherCat Tag Into a Variable: choose a tag and a variable")
            return
        try:
            result = self.client.webtag(tag)
        except RCPError as e:
            self.logger.error("%s", e)
            return
        indigo.variable.updateValue(var_id, value=result)
        self.logger.debug("%s -> variable %d: %r", tag, var_id, result)

    def menu_log_channels(self):
        try:
            info = self.client.system_data()
            channels = self.client.channels()
            units = self.client.units()
        except RCPError as e:
            self.logger.error("%s", e)
            return
        self.logger.info("%s, RCP version %s, sample period %s s, units %s", " ".join(str(info.get("versString", "")).split()),
                         info.get("RCPVersion"), info.get("samplePeriod"), units.as_dict())
        for c in channels:
            if not c.valid:
                continue
            try:
                value, unit, decimals = wcrcp.convert(self.client.channel_value(c.number), c.kind, units)
                text = wcrcp.format_value(value, unit, decimals, c.kind)
            except RCPError as e:
                text = str(e)
            self.logger.info("  #%-3d type %-4d %-32s %s", c.number, c.type, c.name, text)
        missing = [c.name for c in channels if not c.valid]
        if missing:
            self.logger.info("  Not reporting: %s", ", ".join(missing))

    def menu_create_devices(self):
        try:
            channels = self.client.channels()
        except RCPError as e:
            self.logger.error("%s", e)
            return
        existing_keys = set()
        have_station = False
        for dev in indigo.devices.iter("self"):
            if dev.deviceTypeId == READING:
                existing_keys.add(dev.pluginProps.get("channelKey", ""))
            elif dev.deviceTypeId == STATION:
                have_station = True
        folder_id = self._folder_id()
        made = []
        if not have_station:
            made.append(self._create(self._unique_name("WeatherCat Station"), STATION, {}, folder_id, "station"))
        for c in channels:
            if not c.valid or c.is_comms or c.type in SKIP_WHEN_CREATING or c.key in existing_keys:
                continue
            props = {"channelKey": c.key, "showStats": True, "decimals": "", "kind": c.kind,
                     "statItem": c.stat_item or "", "address": c.name,
                     "SupportsOnState": False, "SupportsSensorValue": True, "SupportsStatusRequest": True}
            name = self._unique_name("WeatherCat " + FRIENDLY_NAMES.get(c.name, c.name))
            made.append(self._create(name, READING, props, folder_id, c.name))
        if wcrcp.FEELS_LIKE_KEY not in existing_keys and wcrcp.first_of_type(channels, wcrcp.TYPE_TEMPERATURE):
            props = {"channelKey": wcrcp.FEELS_LIKE_KEY, "showStats": False, "decimals": "",
                     "kind": KIND_FEELS_LIKE, "statItem": "", "address": "Feels Like",
                     "SupportsOnState": False, "SupportsSensorValue": True, "SupportsStatusRequest": True}
            made.append(self._create(self._unique_name("WeatherCat Feels Like"), READING, props, folder_id,
                                     "Feels Like"))
        made = [m for m in made if m]
        if made:
            self.logger.info("Created %d device(s) in the \"%s\" folder: %s", len(made), FOLDER_NAME, ", ".join(made))
        else:
            self.logger.info("Every live WeatherCat reading already has a device")
        self._refresh_soon()

    def _create(self, name, type_id, props, folder_id, address):
        try:
            indigo.device.create(protocol=indigo.kProtocol.Plugin, name=name, address=address,
                                 deviceTypeId=type_id, props=props, folder=folder_id)
            return name
        except Exception as e:
            self.logger.error("Couldn't create %s: %s", name, e)
            return None

    @staticmethod
    def _unique_name(base):
        name, n = base, 2
        while name in indigo.devices:
            name = "%s %d" % (base, n)
            n += 1
        return name

    @staticmethod
    def _folder_id():
        for folder in indigo.devices.folders:
            if folder.name == FOLDER_NAME:
                return folder.id
        return indigo.devices.folder.create(FOLDER_NAME).id
