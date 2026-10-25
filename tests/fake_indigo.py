# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 hap67 and contributors. Part of indigo-weathercat; see LICENSE.
"""A small stand-in for Indigo's `indigo` module, just enough to run plugin.py in tests.

It records what the plugin writes to devices so tests can check it. It isn't a full model of
Indigo: device comm restarts after a props change are not simulated.
"""
import logging
import types


class Dict(dict):
    pass


class _Enum:
    def __init__(self, *names):
        for n in names:
            setattr(self, n, n)


kStateImageSel = _Enum("SensorOn", "SensorOff", "SensorTripped", "TemperatureSensor", "HumiditySensor",
                       "WindSpeedSensor", "WindDirectionSensor", "LightSensor")
kProtocol = _Enum("Plugin")
kUniversalAction = _Enum("RequestStatus")


class Device:
    def __init__(self, dev_id, name, type_id, props, folder_id=0, address=""):
        self.id = dev_id
        self.name = name
        self.deviceTypeId = type_id
        self.pluginProps = Dict(props)
        self.folderId = folder_id
        self.address = address
        self.states = {}
        self.ui_values = {}
        self.error_state = None
        self.image = None
        self.state_list_changes = 0

    def updateStateOnServer(self, key, value, uiValue=None, decimalPlaces=None):
        self.updateStatesOnServer([{"key": key, "value": value, "uiValue": uiValue}])

    def updateStatesOnServer(self, updates):
        for u in updates:
            self.states[u["key"]] = u["value"]
            if u.get("uiValue") is not None:
                self.ui_values[u["key"]] = u["uiValue"]

    def setErrorStateOnServer(self, message):
        self.error_state = message

    def updateStateImageOnServer(self, image):
        self.image = image

    def replacePluginPropsOnServer(self, props):
        self.pluginProps = Dict(props)

    def stateListOrDisplayStateIdChanged(self):
        self.state_list_changes += 1


class Folder:
    def __init__(self, folder_id, name):
        self.id = folder_id
        self.name = name


class _Folders(list):
    pass


class _FolderApi:
    def __init__(self, owner):
        self.owner = owner

    def create(self, name):
        f = Folder(9000 + len(self.owner.folders), name)
        self.owner.folders.append(f)
        return f


class _Devices(dict):
    def __init__(self):
        super().__init__()
        self.folders = _Folders()
        self.folder = _FolderApi(self)

    def __contains__(self, key):
        if isinstance(key, str):
            return any(d.name == key for d in self.values())
        return dict.__contains__(self, key)

    def iter(self, which=None):
        return iter(list(self.values()))


devices = _Devices()
variables_set = {}


class _DeviceApi:
    def create(self, protocol, name, address, deviceTypeId, props, folder=0):
        dev_id = 1000 + len(devices)
        devices[dev_id] = Device(dev_id, name, deviceTypeId, props, folder, address)
        return devices[dev_id]


device = _DeviceApi()


class _VariableApi:
    def updateValue(self, var_id, value):
        variables_set[var_id] = value


variable = _VariableApi()


class PluginBase:
    class StopThread(Exception):
        pass

    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs, **kwargs):
        self.pluginId = plugin_id
        self.pluginPrefs = plugin_prefs
        self.logger = logging.getLogger("fake-indigo-plugin")
        self.indigo_log_handler = logging.NullHandler()
        self.debug = False

    def getDeviceStateList(self, dev):
        return []

    @staticmethod
    def getDeviceStateDictForNumberType(key, trigger, control):
        return {"Key": key, "Type": "Number"}

    @staticmethod
    def getDeviceStateDictForStringType(key, trigger, control):
        return {"Key": key, "Type": "String"}

    def sleep(self, seconds):
        raise self.StopThread()


def reset():
    devices.clear()
    devices.folders.clear()
    variables_set.clear()


def install():
    """Make `import indigo` return this module."""
    import sys
    sys.modules["indigo"] = sys.modules[__name__]
