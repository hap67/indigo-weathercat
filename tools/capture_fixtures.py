#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 hap67 and contributors. Part of indigo-weathercat; see LICENSE.
"""Save real WeatherCat RCP replies into fixtures/rcp/ for the tests (they also suit any other
project that reads WeatherCat's RCP and wants test data).

    python3 tools/capture_fixtures.py [--refresh] [host] [port]

Each reply is saved exactly as WeatherCat sent it. index.json maps file names to the RCP path.
Existing files are kept (so test expectations stay put) unless --refresh is given.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "fixtures", "rcp")
SAFE = "$:()"

TAGS = [
    "STAT$TEMPERATURE:CURRENT$", "STAT$TEMPERATURE:MAX:TODAY$", "STAT$TEMPERATURE:MAX:TODAY:TIME$",
    "STAT$TEMPERATURE:MIN:TODAY$", "STAT$TEMPERATURE:MIN:TODAY:TIME$", "STAT$TEMPERATURE:DELTA1$",
    "STAT$PRESSURE:MAX:TODAY$", "STAT$WINDGUST:MAX:TODAY$", "STAT$RAIN:TOTAL:TODAY$",
    "STAT$FOO:MAX:TODAY$",
    "TEMPUNITS$", "PRESSUREUNITS$", "WINDSPEEDUNITS$", "RAINUNITS$", "HEIGHTUNITS$", "PRESSUREUNIT$",
    "CC$", "CF$", "CSF$", "CU$", "BTTEXT$", "DOMWDTEXT$", "COMMSFAILFLAG$",
    "SUNRISELOCAL$", "SUNSETLOCAL$", "DAYLIGHTTIME$", "L$",
]

# Today's high/low (and times) and 1-hour change for every STAT$ item the plugin uses.
STAT_ITEMS = ["TEMPERATURE", "DEWPOINT", "WINDCHILL", "PRESSURE", "WINDSPEED", "AVERAGEWINDSPEED",
              "EXTHUMIDITY", "INTHUMIDITY", "INTTEMPERATURE", "WINDGUST", "SOLAR", "UV", "HEATINDEX"]
for _item in STAT_ITEMS:
    for _pattern in ("STAT$%s:MAX:TODAY$", "STAT$%s:MAX:TODAY:TIME$", "STAT$%s:MIN:TODAY$",
                     "STAT$%s:MIN:TODAY:TIME$", "STAT$%s:DELTA1$"):
        if _pattern % _item not in TAGS:
            TAGS.append(_pattern % _item)


def safe_name(path):
    name = path.strip("/").replace("/", "_")
    for ch in "$:()":
        name = name.replace(ch, "-")
    return name.strip("-_") + ".plist"


def main():
    args = [a for a in sys.argv[1:] if a != "--refresh"]
    refresh = "--refresh" in sys.argv[1:]
    host = args[0] if args else "127.0.0.1"
    port = int(args[1]) if len(args) > 1 else 49255
    base = "http://%s:%d" % (host, port)
    os.makedirs(OUT, exist_ok=True)
    paths = ["/discovery/systemData", "/discovery/channelList", "/discovery/alertsList",
             "/data/getChannelValue/99"]
    import plistlib
    channels = plistlib.loads(urllib.request.urlopen(base + "/discovery/channelList", timeout=5).read())["result"]
    paths += ["/data/getChannelValue/%d" % c["channelNumber"] for c in channels]
    paths += ["/webtag/" + urllib.parse.quote(t, safe=SAFE) for t in TAGS]
    index_path = os.path.join(OUT, "index.json")
    index = {}
    if os.path.exists(index_path) and not refresh:
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
    added = 0
    for path in paths:
        name = safe_name(urllib.parse.unquote(path))
        index[name] = urllib.parse.unquote(path)
        target = os.path.join(OUT, name)
        if os.path.exists(target) and not refresh:
            continue
        data = urllib.request.urlopen(base + path, timeout=5).read()
        with open(target, "wb") as f:
            f.write(data)
        added += 1
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(index, f, indent=1, sort_keys=True, ensure_ascii=False)
    print("Saved %d new replies (%d in all) to %s" % (added, len(index), os.path.normpath(OUT)))


if __name__ == "__main__":
    main()
