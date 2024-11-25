#TODO - catch KeyboadInterupt exception
#TODO - specify logging path via main arguments

from pyudev import Context, Monitor, MonitorObserver
from evdev import InputDevice, ecodes
from kasa import Kasa

import sys
import threading
import re
import evdev
import json
import logging
import time

DEVICE_NAME = "Wireless Phone Controller"

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", filename="/tmp/blue-kasa.log", filemode='a')

logger = logging.getLogger(__name__)

class DeviceListener:
    def __init__(self, kasa):
        self.kasa = kasa

        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)

        self.current = {ecodes.KEY_PLAYPAUSE : 0}
        self.device = None

        self.groups = []
    
    def device_connected(self, path):
        with self.condition:
            self.device = InputDevice(path)

            self.condition.notify_all()

    def device_removed(self):
        with self.condition:
            self.device = None

            self.condition.notify_all()

    def has_device(self, path):
        return self.device is not None and self.device.path == path

    def get_device(self, name):
        devices = [InputDevice(path) for path in evdev.list_devices()]

        for device in devices:
            if device.name == name:
                return device

    def start(self):
        with self.condition:
            self.device = self.get_device(DEVICE_NAME)

            logger.info("device found - {0}".format(self.device.path))

            self.condition.notify_all()

        while True:
            with self.condition:
                while self.device is None:
                    self.condition.wait()
                    
                try:
                    while event := self.device.read_one():
                        if event.type == evdev.ecodes.EV_KEY:
                            logger.debug("event code - {0} value - {1}".format(event.code, event.value))

                            if event.code == ecodes.KEY_PLAYPAUSE:
                                if self.current[event.code] == 1 and event.value == 0:
                                    start = time.time()

                                    for group in self.groups:
                                        logger.debug("toggle - {0} {1}".format(group["name"], group["children"]))

                                        kasa.toggle_device(group["name"], group["children"])
                                    
                                    logger.debug("command finished in {:.2f}s".format(time.time() - start))

                                self.current[event.code] = event.value
                except OSError:
                    pass

    def add_kasa_group(self, name, children=[]):
        self.groups.append({"name" : name, "children" : children})

def ends_with(name, pattern):
    return bool(re.search(pattern, name))

def device_event_handler(device):
    global listener
    logger.debug('event - {0.action} {0.device_node}'.format(device))

    if device.device_node:
        for name in (i['NAME'] for i in device.ancestors if 'NAME' in i):
            if DEVICE_NAME in name and ends_with(device.device_node, "event[0-9]+$"):
                if device.action == u'add':
                    logger.info("device added - {0}".format(device.device_node))

                    listener.device_connected(device.device_node)

                if device.action == u'remove':
                    logger.info("device removed - {0}".format(device.device_node))
                    
                    listener.device_removed()

        if device.action == "remove" and listener.has_device(device.device_node):
            logger.info("device removed - {0}".format(device.device_node))

            listener.device_removed()


if __name__ == "__main__":
    configuration = {}

    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], "r") as file:
                configuration = json.load(file)
        except:
            print("failed to open {0}".format(sys.argv[1]))
            exit(-1)
    else:
        print("usage - python3 blue-kasa.py filename")
        exit(-1)

    kasa = Kasa()
    kasa.load_devices()

    listener = DeviceListener(kasa)

    for entry in configuration:
        children = []

        if "children" in entry:
            for child in entry["children"]:
                children.append(child["name"])

        listener.add_kasa_group(entry["name"], children)

    context = Context()

    monitor = Monitor.from_netlink(context)
    monitor.filter_by(subsystem='input')

    observer = MonitorObserver(monitor, callback=device_event_handler, name='monitor-observer')
    observer.start()

    listener.start()
