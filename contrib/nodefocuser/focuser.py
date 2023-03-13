import time
import machine
import uos
import json


class Device:
    MIN_POSITION = 0
    MAX_POSITION = 64500  # 40mm for RC6 focuser

    MIN_SPEED = 10
    DEFAULT_SPEED = 250
    MAX_SPEED = 300

    DIR_UP = 1
    DIR_DOWN = -1

    BROADCAST_INTERVAL = 1
    RECEIVE_INTERVAL = 1.5
    SAVE_INTERVAL = 10

    position = MIN_POSITION

    steps = 0
    step_dir = DIR_UP

    pins = (
        machine.Pin(0, machine.Pin.OUT),  # D7
        machine.Pin(4, machine.Pin.OUT),  # D7
        machine.Pin(5, machine.Pin.OUT),  # D7
        machine.Pin(16, machine.Pin.OUT),  # D7
    )

    PIN_MAP = (
        (0, 0, 1, 1),
        (0, 1, 1, 0),
        (1, 1, 0, 0),
        (1, 0, 0, 1),
    )

    uart = None

    speed = DEFAULT_SPEED
    IDLE_SLEEP = 0.05

    last_saved_position = None

    @classmethod
    def main(cls):

        send_in = cls.BROADCAST_INTERVAL
        read_in = cls.RECEIVE_INTERVAL
        save_in = cls.SAVE_INTERVAL

        while 1:
            if cls.steps > 0:

                cls.steps -= 1
                cls.position += cls.step_dir

                cls.drive_pins(cls.position)

                sleep = 1.0 / cls.speed
            else:
                sleep = cls.IDLE_SLEEP

            time.sleep(sleep)
            send_in -= sleep
            read_in -= sleep
            save_in -= sleep

            if send_in <= 0:
                send_in = cls.BROADCAST_INTERVAL
                cls.send_position()

            if read_in <= 0:
                read_in = cls.RECEIVE_INTERVAL
                cls.read_command()

            if save_in <= 0:
                save_in = cls.SAVE_INTERVAL
                cls.save_state()

    @classmethod
    def save_state(cls):
        if cls.last_saved_position != cls.position:
            f = open("state.txt", "w")
            f.write(str(cls.position))
            f.close()
            cls.last_saved_position = cls.position

    @classmethod
    def load_state(cls):
        try:
            with open("state.txt", "r") as f:
                cls.position = int(f.read())
                cls.last_saved_position = cls.position
        except:
            pass

    @classmethod
    def drive_pins(cls, position):
        index = position % 4
        pin_map = cls.PIN_MAP[index]
        cls.pins[0].value(pin_map[0])
        cls.pins[1].value(pin_map[1])
        cls.pins[2].value(pin_map[2])
        cls.pins[3].value(pin_map[3])

    @classmethod
    def set_target(cls, target):
        target = round(target)
        if target > cls.MAX_POSITION or target < cls.MIN_POSITION:
            raise ValueError(
                "Position has to be between {} and {}".format(
                    cls.MIN_POSITION, cls.MAX_POSITION
                )
            )

        position = cls.position

        dist = abs(target - position)

        if target >= position:
            cls.steps = dist
            cls.step_dir = cls.DIR_UP
        else:
            cls.steps = dist
            cls.step_dir = cls.DIR_DOWN

    @classmethod
    def park(cls):
        cls.set_target(cls.MIN_POSITION)

    @classmethod
    def reset(cls, target):
        target = round(target)
        if target > cls.MAX_POSITION or target < cls.MIN_POSITION:
            raise ValueError(
                "Position has to be between {} and {}".format(
                    cls.MIN_POSITION, cls.MAX_POSITION
                )
            )

        cls.position = target

    @classmethod
    def set_speed(cls, speed):
        if speed > cls.MAX_SPEED or speed < cls.MIN_SPEED:
            raise ValueError(
                "Speed has to be between {} and {}".format(cls.MIN_SPEED, cls.MAX_SPEED)
            )

        cls.speed = speed

    @classmethod
    def send_position(cls):
        direction = "outward" if cls.step_dir == cls.DIR_UP else "inward"
        if cls.steps == 0:
            status = "idle"
        else:
            status = "move"

        msg = (
            json.dumps(
                {
                    "status": {
                        "position": cls.position,
                        "direction": direction,
                        "status": status,
                    }
                }
            )
            + "\n"
        )

        if cls.uart:
            cls.uart.write(msg.encode())
        else:
            print(msg)

    @classmethod
    def read_command(cls):
        if not cls.uart:
            return

        if cls.uart.any():
            in_data = None
            try:
                in_data = cls.uart.readline()
                if not in_data:
                    return

                cmd = json.loads(in_data.decode())

                msg = json.dumps({"ack": cmd}) + "\n"

                if "reset" in cmd:
                    cls.reset(cmd["reset"])

                if "position" in cmd:
                    cls.set_target(cmd["position"])

                if "park" in cmd and cmd["park"]:
                    cls.park()

                if "speed" in cmd:
                    cls.set_speed(cmd["speed"])

                cls.uart.write(msg.encode())
            except Exception as ex:
                msg = (
                    json.dumps(
                        {
                            "error": "Error processing command",
                            "details": str(ex),
                            "in_data": in_data,
                        }
                    )
                    + "\n"
                )
                cls.uart.write(msg.encode())


def start():
    machine.freq(160000000)
    uos.dupterm(None, 1)

    Device.uart = machine.UART(0, baudrate=9600, rxbuf=64)
    Device.load_state()
    Device.main()
