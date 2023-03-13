import environ

BASE_DIR = environ.Path(__file__) - 1
env = environ.Env()
env.read_env(BASE_DIR('.env'))


FOCUSER_IP = "192.168.5.51"
FOCUSER_PORT = "/dev/ttyAMA1"

HA_HOST = "http://192.168.1.11:8123"
HA_TOKEN = env("HA_TOKEN")
HA_ENTITY = "switch.astro_flattner"
