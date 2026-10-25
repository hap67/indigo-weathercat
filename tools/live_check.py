#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 hap67 and contributors. Part of indigo-weathercat; see LICENSE.
"""Run the plugin once against the real WeatherCat, without Indigo, and print what each device
would show. Uses tests/fake_indigo.py in place of Indigo; nothing in Indigo is touched.

    python3 tools/live_check.py [host] [port]
"""
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path[:0] = [os.path.join(ROOT, "tests"), os.path.join(ROOT, "WeatherCat.indigoPlugin", "Contents", "Server Plugin")]

import fake_indigo  # noqa: E402

fake_indigo.install()
import plugin  # noqa: E402


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = sys.argv[2] if len(sys.argv) > 2 else "49255"
    p = plugin.Plugin("com.5th-imperium.weathercat", "WeatherCat", "0.1.0",
                      {"host": host, "port": port, "pollSeconds": "30", "statsMinutes": "5"})
    p.menu_create_devices()
    for dev in fake_indigo.devices.values():
        p.deviceStartComm(dev)
    p.poll(with_stats=True)
    for dev in sorted(fake_indigo.devices.values(), key=lambda d: d.name):
        if dev.deviceTypeId == plugin.STATION:
            print("%-45s %s" % (dev.name, dev.states.get("status")))
            for key in ("stationComms", "forecast", "pressureTrend", "sunrise", "sunset", "lastSample",
                        "weathercatVersion", "rcpVersion", "units"):
                print("    %-20s %s" % (key, dev.states.get(key)))
            continue
        shown = dev.error_state or dev.ui_values.get("sensorValue", "")
        extra = ""
        if "todayHigh" in dev.states:
            extra = "high %s at %s, low %s at %s, 1 h %s" % (
                dev.ui_values.get("todayHigh"), dev.states.get("todayHighTime"),
                dev.ui_values.get("todayLow"), dev.states.get("todayLowTime"), dev.ui_values.get("change1h"))
        print("%-45s %-14s %s" % (dev.name, shown, extra))


if __name__ == "__main__":
    main()
