import math
import time

import requests


class NodeMCU:
    SETTLE_CHECK_WAIT = 1
    SETTLE_WAIT = 2
    TIMEOUT = 120

    HTTP_TIMEOUT = 5.0

    TIME_PER_STEP = 0.01
    TIME_START_STOP = 2

    def __init__(self, ip):
        self.ip = ip

    def set_position(self, position, wait=True, tolerance=0):
        initial_wait = 0
        if wait:
            current_position = self.get_position()
            diff = abs(float(current_position) - float(position))
            initial_wait = self.TIME_START_STOP + diff * self.TIME_PER_STEP

        self._do_request("POST", position=position)

        if wait:
            time.sleep(math.ceil(initial_wait))

        start = time.time()
        while wait:
            time.sleep(self.SETTLE_CHECK_WAIT)
            current_position = self.get_position()

            diff = abs(float(current_position) - float(position))

            if diff <= tolerance:
                break

            elapsed = time.time() - start
            if elapsed > self.TIMEOUT:
                raise Exception()

        if wait:
            time.sleep(self.SETTLE_WAIT)

    def get_position(self):
        resp = self._do_request("GET")
        return int(resp["position"])

    def reset_position(self, position):
        self._do_request("PATCH", position=position)

    def _do_request(self, method, position=None):
        full_url = f"http://{self.ip}/"

        r = None
        if method == "GET":
            r = requests.get(full_url, timeout=self.HTTP_TIMEOUT)
        if method == "POST":
            r = requests.post(
                full_url + "?targetPosition=" + str(position), timeout=self.HTTP_TIMEOUT
            )
        if method == "PATCH":
            r = requests.patch(
                full_url, "?position=" + str(position), timeout=self.HTTP_TIMEOUT
            )
        resp = r.json()
        if resp["result"] != "OK":
            raise Exception("Invalid response from focuser")
        return resp
