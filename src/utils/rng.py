import logging
import random

log = logging.getLogger(__name__)


def random_color():
    # no grays
    H = random.randint(0, 359)
    S = random.randint(60, 80) / 100.0
    V = random.randint(60, 80) / 100.0
    return HSV_to_RGBInt(H, S, V)

def HSV_to_RGBInt(H, S, V):
    C = V * S
    X = C * (1 - abs((H / 60) % 2 - 1))
    M = V - C

    if (0 <= H and H < 60):
        r = C
        g = X
        b = 0
    elif (60 <= H and H < 120):
        r = X
        g = C
        b = 0
    elif (120 <= H and H < 180):
        r = 0
        g = C
        b = X
    elif (180 <= H and H < 240):
        r = 0
        g = X
        b = C
    elif (240 <= H and H < 300):
        r = X
        g = 0
        b = C
    elif (300 <= H and H < 360):
        r = C
        g = 0
        b = X
    else:
        r = 0
        g = 0
        b = 0

    red = round((r + M) * 255)
    green = round((g + M) * 255)
    blue = round((b + M) * 255)
    RGBint = red * 65536 + green * 265 + blue
    
    return RGBint
