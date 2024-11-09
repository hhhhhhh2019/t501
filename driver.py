import usb
import yaml
from evdev import UInput, ecodes, AbsInfo
import sys
from math import floor


with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

print(config)


tablet = usb.core.find(
    idVendor=config["vendor"], idProduct=config["product"]
)

if tablet is None:
    raise Exception("Device not found")


for i in [0, 1, 2]:  # we need detach all interfaces
    if tablet.is_kernel_driver_active(i):
        tablet.detach_kernel_driver(i)
        print(f"Kernel driver for {i} interfrace detached")

tablet.set_configuration()
usb.util.claim_interface(tablet, 2)
print("Interface claimed successfully")


def set_report(wValue, report):
    try:
        tablet.ctrl_transfer(0x21, 9, wValue, 2, report, 250)
    except usb.core.USBError as e:
        print(f"Error setting report: {e}")
        return 1
    return 0


reports = [
    (0x0308, [0x08, 0x04, 0x1d, 0x01, 0xff, 0xff, 0x06, 0x2e]),
    (0x0308, [0x08, 0x03, 0x00, 0xff, 0xf0, 0x00, 0xff, 0xf0]),
    (0x0308, [0x08, 0x06, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
    (0x0308, [0x08, 0x03, 0x00, 0xff, 0xf0, 0x00, 0xff, 0xf0]),
]

for i, (wValue, report) in enumerate(reports):
    result = set_report(wValue, report)
    if result != 0:
        print(f"Failed at report {i}")

usb.util.release_interface(tablet, 2)


tablet = usb.core.find(
    idVendor=config["vendor"], idProduct=config["product"]
)


endpoint = tablet[0].interfaces()[1].endpoints()[0]

tablet.reset()

for i in [0, 1, 2]:  # we need detach all interfaces
    if tablet.is_kernel_driver_active(i):
        tablet.detach_kernel_driver(i)
        print(f"Kernel driver for {i} interfrace detached")

tablet.set_configuration()


if config["pen"]["swap_xy"]:
    config["pen"]["resolution_x"], config["pen"]["resolution_y"] =\
        config["pen"]["resolution_y"], config["pen"]["resolution_x"]


pen_events = {
    ecodes.EV_KEY: [
        ecodes.BTN_TOOL_PEN,
        ecodes.BTN_STYLUS,
        ecodes.BTN_STYLUS2,
    ],
    ecodes.EV_ABS: [
            (ecodes.ABS_X, AbsInfo(0, 0, config["pen"]["max_x"], 0, 0, config["pen"]["resolution_x"])),
            (ecodes.ABS_Y, AbsInfo(0, 0, config["pen"]["max_y"], 0, 0, config["pen"]["resolution_y"])),
            (ecodes.ABS_PRESSURE, AbsInfo(0, 0, 1000, 0, 0, 1))
    ]
}


buttons = {
    "E":         [ecodes.KEY_E],
    "B":         [ecodes.KEY_B],
    "C-":        [ecodes.KEY_LEFTCTRL, ecodes.KEY_KPMINUS],
    "C+":        [ecodes.KEY_LEFTCTRL, ecodes.KEY_KPPLUS],
    "[":         [ecodes.KEY_LEFTBRACE],
    "]":         [ecodes.KEY_RIGHTBRACE],
    "mouseup":   [ecodes.KEY_LEFTCTRL, ecodes.KEY_Z],
    "tab":       [ecodes.KEY_TAB],
    "mousedown": [ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_Z],
    "space":     [ecodes.KEY_SPACE],
    "ctrl":      [ecodes.KEY_LEFTCTRL],
    "alt":       [ecodes.KEY_LEFTALT],

    "mute":      [ecodes.KEY_MUTE],
    "vol+":      [ecodes.KEY_VOLUMEUP],
    "vol-":      [ecodes.KEY_VOLUMEDOWN],
    "music":     [ecodes.KEY_MEDIA],
    "playpause": [ecodes.KEY_PLAYPAUSE],
    "prev":      [ecodes.KEY_PREVIOUSSONG],
    "next":      [ecodes.KEY_NEXTSONG],
    "home":      [ecodes.KEY_HOME],
    "calc":      [ecodes.KEY_CALC],
    "desk":      [ecodes.KEY_BUTTONCONFIG],
}

btn_events = {
    ecodes.EV_KEY: [
        j for i in buttons for j in buttons[i]
    ],
}


pen = UInput(events=pen_events, name=config["name"], version=3)
btn = UInput(events=btn_events, name=config["name"] + "_buttons", version=0x3)


def press(keys, event):
    for i in keys:
        btn.write(ecodes.EV_KEY, i, event)


while True:
    try:
        data = tablet.read(
            endpoint.bEndpointAddress,
            endpoint.wMaxPacketSize
        )

        x = data[1] * 256 + data[2]
        y = data[3] * 256 + data[4]
        pressure_raw = data[5] * 256 + data[6]
        stylus_button = data[9]

        raw_x, raw_y = x, y

        buttons_raw = data[11:13]

        if config["pen"]["swap_xy"]:
            x, y = y, x

        if config["pen"]["inverse_x"]:
            x = config["pen"]["max_x"] - x

        if config["pen"]["inverse_y"]:
            y = config["pen"]["max_y"] - y

        if pressure_raw < config["pen"]["max_pressure"]:
            pressure = min(1000, floor(
                (config["pen"]["max_pressure"] - pressure_raw) /
                config["pen"]["min_pressure"] * 1000
            ))

            pen.write(ecodes.EV_KEY, ecodes.BTN_TOOL_PENCIL, 1)
        else:
            pressure = 0

            pen.write(ecodes.EV_KEY, ecodes.BTN_TOOL_PENCIL, 0)

        press(buttons["E"],         int((data[12] & 0b00000010) == 0))
        press(buttons["B"],         int((data[12] & 0b00010000) == 0))
        press(buttons["C-"],        int((data[11] & 0b10000000) == 0))
        press(buttons["C+"],        int((data[12] & 0b00000001) == 0))
        press(buttons["["],         int((data[11] & 0b01000000) == 0))
        press(buttons["]"],         int((data[12] & 0b00100000) == 0))
        press(buttons["mouseup"],   int((data[11] & 0b00100000) == 0))
        press(buttons["tab"],       int((data[11] & 0b00000001) == 0))
        press(buttons["mousedown"], int((data[11] & 0b00010000) == 0))
        press(buttons["space"],     int((data[11] & 0b00000010) == 0))
        press(buttons["ctrl"],      int((data[11] & 0b00001000) == 0))
        press(buttons["alt"],       int((data[11] & 0b00000100) == 0))

        press(buttons["mute"],      int(pressure != 0 and raw_y > 60000 and raw_x == 200))
        press(buttons["vol-"],      int(pressure != 0 and raw_y > 60000 and raw_x == 609))
        press(buttons["vol+"],      int(pressure != 0 and raw_y > 60000 and raw_x == 1018))
        press(buttons["music"],     int(pressure != 0 and raw_y > 60000 and raw_x == 1427))
        press(buttons["playpause"], int(pressure != 0 and raw_y > 60000 and raw_x == 1836))
        press(buttons["prev"],      int(pressure != 0 and raw_y > 60000 and raw_x == 2245))
        press(buttons["next"],      int(pressure != 0 and raw_y > 60000 and raw_x == 2654))
        press(buttons["home"],      int(pressure != 0 and raw_y > 60000 and raw_x == 3063))
        press(buttons["calc"],      int(pressure != 0 and raw_y > 60000 and raw_x == 3472))
        press(buttons["desk"],      int(pressure != 0 and raw_y > 60000 and raw_x == 3881))

        # print(list(map(lambda x: bin(x)[2:].zfill(8), buttons_raw)))
        # print(data)
        # print(x, y, pressure, stylus_button)

        if stylus_button == 4:
            pen.write(ecodes.EV_KEY, ecodes.BTN_STYLUS, 1)
        else:
            pen.write(ecodes.EV_KEY, ecodes.BTN_STYLUS, 0)

        if stylus_button == 6:
            pen.write(ecodes.EV_KEY, ecodes.BTN_STYLUS2, 1)
        else:
            pen.write(ecodes.EV_KEY, ecodes.BTN_STYLUS2, 0)

        pen.write(ecodes.EV_ABS, ecodes.ABS_X, x)
        pen.write(ecodes.EV_ABS, ecodes.ABS_Y, y)
        pen.write(ecodes.EV_ABS, ecodes.ABS_PRESSURE, pressure)
        pen.syn()

        btn.syn()

    except usb.core.USBError as e:
        if e.args[0] == 19:
            pen.close()
            btn.close()
            raise Exception("Device has been disconnected")
    except KeyboardInterrupt:
        pen.close()
        btn.close()
        sys.exit("\nDriver terminated successfully.")
    except Exception as e:
        print(e)
