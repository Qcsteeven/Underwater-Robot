# config.py
import os

PI_HOST = '192.168.1.100'

MOTOR_PINS = {
    'motor_left': 12,
    'motor_right': 18,
    'motor_up_down_left': 19,
    'motor_up_down_right': 13
}

STOP = 1500
MAX_UP = 2000
MAX_DOWN = 1000

DEAD_ZONE = 0.1
TRIGGER_DEAD_ZONE = 0.02
HORIZONTAL_RAMP_STEP = 7
VERTICAL_RAMP_STEP = 13

# Камера
RTSP_URL = "rtsp://admin:admin@192.168.1.88:554/11"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_FOLDER = os.path.join(BASE_DIR, "VIDEO_REC")