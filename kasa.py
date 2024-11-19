import logging
import subprocess
import json

from enum import Enum

logger = logging.getLogger(__name__) 

class PowerState(Enum):
    ON = "ON"
    OFF = "OFF"
    UNKNOWN = "UNKNOWN"

class Kasa:
    _devices = []

    def __run_command(self, args):
        logger.info("executing command - {0}".format(" ".join(args)))

        result = subprocess.run(args, capture_output=True, text=True)

        logger.debug("command return code - {0}".format(str(result.returncode)))
        logger.debug("command response - {0}".format(result.stdout))

        if result.returncode != 0:
            logger.error("failed to execute command - {0}".format(" ".join(args)))

        return result;

    def load_devices(self):
        result = self.__run_command(["kasa", "--json", "discover"])
        js = "{}"

        if result.returncode == 0:
            js = json.loads(result.stdout)

        self._devices.clear()

        #js = "{}"
        #with open("kasa-discover.json", "r") as file:
        #    js = json.load(file)
        
        for ip in js:
            info = js[ip]["system"]["get_sysinfo"]

            device = {}
            device["ipaddress"] = ip
            device["name"] = info["alias"]
            device["children"] = []

            if "children" in info:
                for ch in info["children"]:
                    child = {}
                    child["name"] = ch["alias"]
                    child["state"] = ch["state"]

                    device["children"].append(child)
            else:
                device["state"] = info["relay_state"]

            self._devices.append(device)

        return self._devices
    
    @property
    def devices(self):
        return self._devices

    def get_ip_address(self, name):
        for device in self._devices:
            if device["name"] == name:
                return device["ipaddress"]

        return None

    def __parse_toggle_result(self, result):
        state = PowerState.UNKNOWN

        if result.returncode == 0:
            lines = result.stdout.splitlines()

            if len(lines) > 0:
                if lines[-1].find("Turning on") != -1:
                    state = PowerState.ON
                elif lines[-1].find("Turning off") != -1:
                    state = PowerState.OFF
                else:
                    logger.warning("unable to determine power state - {0}".format(result.stdout))

        return state

    def toggle_device(self, name, children=[]):
        ip = self.get_ip_address(name)
        state = PowerState.UNKNOWN

        if ip is None:
            logger.info("device {0} not found. rescanning devices".format(name))

            self.load_devices()
            ip = self.get_ip_address(name)

            if ip is None:
                logger.error("device {0} not found".format(name))
                return state

        if len(children) > 0:
            for child in children:
                result = self.__run_command(["kasa", "--host", ip, "device", "--child", child, "toggle"])
                s = self.__parse_toggle_result(result)

                if state == PowerState.UNKNOWN:
                    state = s

                if state == PowerState.OFF:
                    if s == PowerState.ON:
                        state = s
        else:
                result = self.__run_command(["kasa", "--host", ip, "device", "toggle"])
                state = self.__parse_toggle_result(result)

        return state
        
#devices = get_devices()

#print(get_devices())

#service = Kasa()

#toggle_device("TP-LINK_Smart Plug_7400", ["Sun Room Lights", "Plug 2"])
#print(service.toggle_device("TP-LINK_Power Strip_57F4", ["Christmas Tree"]))

"""
class Dummy:
    pass

with open("dummy.txt") as file:
    dummy = Dummy()
    dummy.returncode = 0
    dummy.stdout = file.read()

    print(service.parse_toggle_result(dummy))
"""
