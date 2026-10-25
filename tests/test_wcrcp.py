#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 hap67 and contributors. Part of indigo-weathercat; see LICENSE.
"""Tests for the WeatherCat plugin, run against real RCP replies saved in fixtures/rcp.

    python3 tests/test_wcrcp.py          (add -v for each test's name)

No Indigo and no running WeatherCat needed: tests/fake_indigo.py stands in for Indigo, and
the fixtures stand in for WeatherCat.
"""
import json
import os
import sys
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PLUGIN = os.path.join(ROOT, "WeatherCat.indigoPlugin", "Contents", "Server Plugin")
FIXTURES = os.path.join(ROOT, "fixtures", "rcp")
sys.path[:0] = [HERE, PLUGIN]

import fake_indigo  # noqa: E402

fake_indigo.install()

import wcrcp  # noqa: E402
from wcrcp import RCPClient, RCPError, Units  # noqa: E402


def fixture_fetch():
    """fetch(path) that answers from the captured replies, like WeatherCat would."""
    with open(os.path.join(FIXTURES, "index.json"), encoding="utf-8") as f:
        by_path = {path: name for name, path in json.load(f).items()}
    seen = []

    def fetch(path):
        seen.append(path)
        name = by_path.get(urllib.parse.unquote(path))
        if name is None:
            raise AssertionError("no fixture for %s" % path)
        with open(os.path.join(FIXTURES, name), "rb") as f:
            return f.read()

    fetch.seen = seen
    return fetch


US = Units("°F", "inHg", "MPH", "in", "Feet")
METRIC = Units("°C", "hPa", "km/h", "mm", "Metres")


class ClientTests(unittest.TestCase):

    def setUp(self):
        self.fetch = fixture_fetch()
        self.client = RCPClient(fetch=self.fetch)

    def test_channel_list(self):
        channels = self.client.channels()
        self.assertEqual(len(channels), 70)
        outdoor = channels[0]
        self.assertEqual((outdoor.number, outdoor.type, outdoor.basic_type, outdoor.name, outdoor.valid),
                         (0, 1, 1, "Ext. Temperature", True))
        self.assertEqual(outdoor.key, "1|Ext. Temperature")
        self.assertEqual(outdoor.stat_item, "TEMPERATURE")
        self.assertEqual(sum(c.valid for c in channels), 34)

    def test_kinds(self):
        by_name = {c.name: c for c in self.client.channels()}
        self.assertEqual(by_name["Precipitation Daily"].kind, wcrcp.KIND_RAIN)      # basic type 0
        self.assertEqual(by_name["Precipitation Per Hour"].kind, wcrcp.KIND_RAIN_RATE)
        self.assertEqual(by_name["Wind Direction"].kind, wcrcp.KIND_DIRECTION)
        self.assertEqual(by_name["Calculated Cloud Base"].kind, wcrcp.KIND_HEIGHT)
        self.assertEqual(by_name["Comms Count"].kind, wcrcp.KIND_COUNT)
        self.assertTrue(by_name["Comms Count"].is_comms)
        self.assertFalse(by_name["Pressure"].is_comms)

    def test_channel_value_and_missing_channel(self):
        self.assertAlmostEqual(self.client.channel_value(0), 11.5, places=3)
        with self.assertRaises(RCPError) as ctx:
            self.client.channel_value(99)
        self.assertEqual(ctx.exception.code, -3)

    def test_webtags_are_sent_unencoded(self):
        self.assertEqual(self.client.webtag("STAT$TEMPERATURE:MAX:TODAY$"), "53.7")
        self.assertIn("/webtag/STAT$TEMPERATURE:MAX:TODAY$", self.fetch.seen)

    def test_bad_tags_raise(self):
        with self.assertRaises(RCPError):                 # '***Syntax Error' with error 0
            self.client.webtag("STAT$FOO:MAX:TODAY$")
        with self.assertRaises(RCPError):                 # error -1
            self.client.webtag("PRESSUREUNIT$")

    def test_units_from_weathercat(self):
        self.assertEqual(self.client.units(), US)

    def test_daily_stats(self):
        stats = self.client.daily_stats("TEMPERATURE")
        self.assertEqual(stats["todayHigh"], 53.7)
        self.assertEqual(stats["todayHighTime"], "3:48 AM")
        self.assertEqual(stats["todayLow"], 49.0)
        self.assertEqual(stats["todayLowTime"], "1:28 AM")
        self.assertEqual(stats["change1h"], -0.7)

    def test_system_data_and_alerts(self):
        info = self.client.system_data()
        self.assertEqual(info["RCPVersion"], 100)
        self.assertTrue(info["stationCommsStatus"])
        self.assertEqual(self.client.alerts(), [])

    def test_unreachable(self):
        client = RCPClient(host="127.0.0.1", port=1, timeout=1)
        with self.assertRaises(RCPError):
            client.channels()

    def test_not_a_plist(self):
        client = RCPClient(fetch=lambda path: b"<html>nope</html>")
        with self.assertRaises(RCPError):
            client.system_data()


class ConversionTests(unittest.TestCase):

    def check(self, raw, kind, units, expected_text):
        value, unit, decimals = wcrcp.convert(raw, kind, units)
        self.assertEqual(wcrcp.format_value(value, unit, decimals, kind), expected_text)

    def test_matches_weathercat_display(self):
        # Each pair checked against WeatherCat's own STAT$...:CURRENT$ answer on 25 Oct 2026.
        self.check(11.7778, wcrcp.KIND_TEMPERATURE, US, "53.2 °F")
        self.check(1029.6951, wcrcp.KIND_PRESSURE, US, "30.41 inHg")
        self.check(1.6093, wcrcp.KIND_WIND, US, "1.0 mph")
        self.check(58.42, wcrcp.KIND_RAIN, US, "2.30 in")
        self.check(362.523, wcrcp.KIND_HEIGHT, US, "1189 ft")

    def test_metric(self):
        self.check(11.7778, wcrcp.KIND_TEMPERATURE, METRIC, "11.8 °C")
        self.check(1029.6951, wcrcp.KIND_PRESSURE, METRIC, "1029.7 hPa")
        self.check(58.42, wcrcp.KIND_RAIN, METRIC, "58.4 mm")
        self.check(10.0, wcrcp.KIND_WIND, Units(wind="Knots"), "5.4 kn")
        self.check(36.0, wcrcp.KIND_WIND, Units(wind="m/s"), "10.0 m/s")

    def test_other_kinds(self):
        self.check(82.0, wcrcp.KIND_HUMIDITY, US, "82%")
        self.check(231.0, wcrcp.KIND_DIRECTION, US, "231° SW")
        self.check(0.0, wcrcp.KIND_RAIN_RATE, US, "0.00 in/h")
        self.check(364273.0, wcrcp.KIND_COUNT, US, "364273")

    def test_compass(self):
        self.assertEqual([wcrcp.compass(d) for d in (0, 11.2, 11.3, 90, 180, 231, 348.7, 348.8, 359)],
                         ["N", "N", "NNE", "E", "S", "SW", "NNW", "N", "N"])

    def test_old_degree_sign(self):
        self.assertTrue(Units(temperature="Â°F").fahrenheit)


class FeelsLikeTests(unittest.TestCase):
    """US National Weather Service rule, worked in metric as RCP sends values."""

    def test_hot_uses_heat_index(self):
        self.assertEqual(wcrcp.feels_like(30.0, 33.0, 30.0, 0.0), (33.0, "Heat index"))
        self.assertEqual(wcrcp.feels_like(26.67, 27.0, 26.67, 0.0)[1], "Heat index")    # 80.0 °F

    def test_cold_and_windy_uses_wind_chill(self):
        self.assertEqual(wcrcp.feels_like(5.0, 5.0, 1.0, 10.0), (1.0, "Wind chill"))
        self.assertEqual(wcrcp.feels_like(10.0, 10.0, 9.0, 4.83)[1], "Wind chill")      # 50 °F, 3 mph

    def test_cold_and_calm_uses_temperature(self):
        self.assertEqual(wcrcp.feels_like(5.0, 5.0, 1.0, 4.0), (5.0, "Temperature"))

    def test_mild_uses_temperature(self):
        self.assertEqual(wcrcp.feels_like(15.0, 15.0, 14.0, 20.0), (15.0, "Temperature"))

    def test_missing_channels(self):
        self.assertEqual(wcrcp.feels_like(30.0), (30.0, "Temperature"))
        self.assertEqual(wcrcp.feels_like(0.0, None, None, 20.0), (0.0, "Temperature"))

    def test_menu_safe_keys(self):
        self.assertEqual(wcrcp.channel_key(1, "Temp, garden; north"), "1|Temp_ garden_ north")
        self.assertEqual(wcrcp.find_channel([wcrcp.Channel(3, 25, 1, "Temp, garden", True)], "25|Temp_ garden").number, 3)


class FindChannelTests(unittest.TestCase):

    def setUp(self):
        self.channels = [wcrcp.Channel(0, 1, 1, "Ext. Temperature", True),
                         wcrcp.Channel(5, 15, 3, "Wind Gust (1 Min)", True),
                         wcrcp.Channel(6, 15, 3, "Wind Gust (1 Min) (2)", True)]

    def test_by_type_and_name(self):
        self.assertEqual(wcrcp.find_channel(self.channels, "15|Wind Gust (1 Min) (2)").number, 6)

    def test_renamed_but_unique_type(self):
        self.assertEqual(wcrcp.find_channel(self.channels, "1|Outside Temp").number, 0)

    def test_renamed_and_ambiguous(self):
        self.assertIsNone(wcrcp.find_channel(self.channels, "15|Gust"))

    def test_malformed(self):
        self.assertIsNone(wcrcp.find_channel(self.channels, "rubbish"))


class PluginTests(unittest.TestCase):
    """Runs plugin.py against fake Indigo and the captured WeatherCat replies."""

    def setUp(self):
        fake_indigo.reset()
        import plugin
        self.plugin_module = plugin
        self.plugin = plugin.Plugin("com.5th-imperium.weathercat", "WeatherCat", "0.1.0",
                                    {"host": "127.0.0.1", "port": "49255", "pollSeconds": "30", "statsMinutes": "5"})
        self.plugin.client = RCPClient(fetch=fixture_fetch())

    def start_all(self):
        for dev in fake_indigo.devices.values():
            self.plugin.deviceStartComm(dev)

    def device(self, name):
        return next(d for d in fake_indigo.devices.values() if d.name == name)

    def test_create_devices_and_poll(self):
        self.plugin.menu_create_devices()
        names = sorted(d.name for d in fake_indigo.devices.values())
        self.assertIn("WeatherCat Station", names)
        self.assertIn("WeatherCat Outdoor Temperature", names)
        self.assertIn("WeatherCat Wind Gust (10 Mins)", names)
        self.assertNotIn("WeatherCat Precipitation Total", names)     # raw counter skipped
        self.assertIn("WeatherCat Heat Index", names)
        self.assertIn("WeatherCat Feels Like", names)
        self.assertFalse(any("Comms" in n for n in names))              # comms counts live on the station
        self.assertEqual(len(names), 1 + 34 - 4 - 1 + 1)                # station + live - comms - raw total + feels like
        self.assertEqual(len(fake_indigo.devices.folders), 1)

        self.start_all()
        self.plugin.poll(with_stats=True)

        t = self.device("WeatherCat Outdoor Temperature")
        self.assertEqual(t.states["sensorValue"], 52.7)          # WeatherCat shows 52.7 (STAT$TEMPERATURE:CURRENT$)
        self.assertEqual(t.ui_values["sensorValue"], "52.7 °F")
        self.assertEqual(t.states["todayHigh"], 53.7)
        self.assertEqual(t.states["todayHighTime"], "3:48 AM")
        self.assertEqual(t.states["change1h"], -0.7)
        self.assertIsNone(t.error_state)
        self.assertEqual(t.image, "TemperatureSensor")

        d = self.device("WeatherCat Wind Direction")
        self.assertEqual(d.states["compass"], "SW")
        self.assertEqual(d.ui_values["sensorValue"], "232° SW")

        f = self.device("WeatherCat Feels Like")
        self.assertEqual(f.ui_values["sensorValue"], "52.7 °F")         # mild: the air temperature
        self.assertEqual(f.states["feelsLikeSource"], "Temperature")
        self.assertIn("feelsLikeSource", [x["Key"] for x in self.plugin.getDeviceStateList(f)])

        p = self.device("WeatherCat Pressure")
        self.assertEqual(p.ui_values["sensorValue"], "30.41 inHg")

        s = self.device("WeatherCat Station")
        self.assertTrue(s.states["online"])
        self.assertTrue(s.states["stationComms"])
        self.assertEqual(s.states["status"], "Overcast")
        self.assertEqual(s.states["sunset"], "5:58 PM")
        self.assertEqual(s.states["rcpVersion"], 100)
        self.assertEqual(s.states["alertsTriggeredCount"], 0)
        self.assertEqual(s.states["weathercatVersion"], "WeatherCat V3.33 Build 20. 12:05:49 Dec 21 2025")

    def test_running_twice_creates_nothing_new(self):
        self.plugin.menu_create_devices()
        count = len(fake_indigo.devices)
        self.plugin.menu_create_devices()
        self.assertEqual(len(fake_indigo.devices), count)

    def test_state_list_follows_channel(self):
        self.plugin.menu_create_devices()
        temp = self.device("WeatherCat Outdoor Temperature")
        keys = [s["Key"] for s in self.plugin.getDeviceStateList(temp)]
        self.assertIn("todayHigh", keys)
        self.assertNotIn("compass", keys)
        rain = self.device("WeatherCat Rain Today")
        self.assertNotIn("todayHigh", [s["Key"] for s in self.plugin.getDeviceStateList(rain)])
        wind = self.device("WeatherCat Wind Direction")
        self.assertIn("compass", [s["Key"] for s in self.plugin.getDeviceStateList(wind)])

    def test_no_data_and_missing_channels(self):
        fake_indigo.device.create("Plugin", "UV", "", "wcReading", {"channelKey": "24|UV Index"})
        fake_indigo.device.create("Plugin", "Gone", "", "wcReading", {"channelKey": "999|Gone"})
        self.start_all()
        self.plugin.poll(with_stats=True)
        self.assertEqual(self.device("UV").error_state, "no data")
        self.assertFalse(self.device("UV").states["hasData"])
        self.assertEqual(self.device("Gone").error_state, "not found")

    def test_offline_then_back(self):
        self.plugin.menu_create_devices()
        self.start_all()
        good = self.plugin.client

        def down(path):
            raise RCPError("Can't reach WeatherCat at http://127.0.0.1:49255 (Connection refused)")
        self.plugin.client = RCPClient(fetch=down)
        self.plugin.poll(with_stats=True)
        self.assertEqual(self.device("WeatherCat Pressure").error_state, "offline")
        self.assertFalse(self.device("WeatherCat Station").states["online"])
        self.assertEqual(self.device("WeatherCat Station").image, "SensorOff")

        self.plugin.client = good
        self.plugin.poll(with_stats=False)
        self.assertIsNone(self.device("WeatherCat Pressure").error_state)
        self.assertTrue(self.device("WeatherCat Station").states["online"])

    def test_decimal_override(self):
        fake_indigo.device.create("Plugin", "T", "", "wcReading", {"channelKey": "1|Ext. Temperature", "decimals": "0"})
        self.start_all()
        self.plugin.poll(with_stats=False)
        self.assertEqual(self.device("T").ui_values["sensorValue"], "53 °F")  # 52.7 rounded

    def test_channel_menu(self):
        items = self.plugin.channel_menu(valuesDict={"channelKey": ""})
        labels = [label for _, label in items]
        self.assertEqual(labels[0], "Ext. Temperature")
        self.assertIn("UV Index (no data)", labels)
        self.assertIn("Comms Count (station status)", labels)
        self.assertIn(wcrcp.FEELS_LIKE_NAME, labels)
        # groups in order: free readings, station status, no data (nothing used yet)
        self.assertEqual(labels.count("%%separator%%"), 2)
        self.assertLess(labels.index("Calculated Heat Index"), labels.index("Comms Count (station status)"))
        self.assertLess(labels.index("Comms Count (station status)"), labels.index("UV Index (no data)"))
        self.assertTrue(all("," not in str(k) and ";" not in str(k) for k, _ in items))

    def test_channel_menu_marks_used_readings(self):
        fake_indigo.device.create("Plugin", "(WC) External Temperature", "", "wcReading",
                                  {"channelKey": "1|Ext. Temperature"})
        items = self.plugin.channel_menu(valuesDict={"channelKey": ""}, targetId=0)
        labels = [label for _, label in items]
        self.assertEqual(labels[0], "Ext. Humidity")
        used = "Ext. Temperature (used by (WC) External Temperature)"
        self.assertIn(used, labels)
        self.assertEqual(labels[labels.index(used) - 1], "%%separator%%")
        # the device's own reading isn't marked as used when editing it
        own = next(d for d in fake_indigo.devices.values())
        self.assertEqual(self.plugin.channel_menu(valuesDict={"channelKey": "1|Ext. Temperature"},
                                                  targetId=own.id)[0][1], "Ext. Temperature")

    def test_new_device_starts_on_first_free_reading(self):
        values, errors = self.plugin.getDeviceConfigUiValues(fake_indigo.Dict(), "wcReading", 0)
        self.assertEqual(values["channelKey"], "1|Ext. Temperature")
        fake_indigo.device.create("Plugin", "T", "", "wcReading", {"channelKey": "1|Ext. Temperature"})
        values, errors = self.plugin.getDeviceConfigUiValues(fake_indigo.Dict(), "wcReading", 0)
        self.assertEqual(values["channelKey"], "12|Ext. Humidity")
        existing = fake_indigo.Dict({"channelKey": "4|Pressure"})
        self.assertEqual(self.plugin.getDeviceConfigUiValues(existing, "wcReading", 5)[0]["channelKey"], "4|Pressure")

    def test_duplicate_reading_is_refused(self):
        first = fake_indigo.device.create("Plugin", "(WC) Pressure", "", "wcReading", {"channelKey": "4|Pressure"})
        bad = self.plugin.validateDeviceConfigUi(fake_indigo.Dict({"channelKey": "4|Pressure", "decimals": ""}), "wcReading", 0)
        self.assertFalse(bad[0])
        self.assertIn("(WC) Pressure", bad[2]["channelKey"])
        same = self.plugin.validateDeviceConfigUi(fake_indigo.Dict({"channelKey": "4|Pressure", "decimals": ""}), "wcReading", first.id)
        self.assertTrue(same[0])
        sep = self.plugin.validateDeviceConfigUi(fake_indigo.Dict({"channelKey": "-1", "decimals": ""}), "wcReading", 0)
        self.assertFalse(sep[0])

    def test_feels_like_device_by_hand(self):
        ok = self.plugin.validateDeviceConfigUi(fake_indigo.Dict({"channelKey": wcrcp.FEELS_LIKE_KEY, "decimals": ""}), "wcReading", 0)
        self.assertTrue(ok[0])
        self.assertEqual(ok[1]["kind"], "feelsLike")

    def test_validate_device(self):
        ok = self.plugin.validateDeviceConfigUi(fake_indigo.Dict({"channelKey": "4|Pressure", "decimals": ""}), "wcReading", 1)
        self.assertTrue(ok[0])
        self.assertEqual(ok[1]["address"], "Pressure")
        bad = self.plugin.validateDeviceConfigUi(fake_indigo.Dict({"channelKey": "", "decimals": "x"}), "wcReading", 1)
        self.assertFalse(bad[0])
        self.assertIn("channelKey", bad[2])
        self.assertIn("decimals", bad[2])

    def test_tag_to_variable(self):
        action = type("A", (), {"props": {"tag": "STAT$TEMPERATURE:MAX:TODAY$", "variableId": "123"}})()
        self.plugin.action_tag_to_variable(action)
        self.assertEqual(fake_indigo.variables_set[123], "53.7")

    def test_prefs_validation(self):
        good = {"host": "127.0.0.1", "port": "49255", "pollSeconds": "30", "statsMinutes": "5"}
        self.assertTrue(self.plugin.validatePrefsConfigUi(fake_indigo.Dict(good))[0])
        bad = self.plugin.validatePrefsConfigUi(fake_indigo.Dict(dict(good, port="x", pollSeconds="2")))
        self.assertFalse(bad[0])
        self.assertEqual(set(bad[2]), {"port", "pollSeconds"})


if __name__ == "__main__":
    unittest.main()
