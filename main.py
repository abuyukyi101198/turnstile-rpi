import subprocess
import time
from evdev import InputDevice, ecodes
import requests
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import RPi.GPIO as GPIO

# Suppress only the InsecureRequestWarning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Define the Bash script content to find USB input devices
bash_script = """
#!/bin/bash

find /sys/bus/usb/devices/usb*/ -name dev | while IFS= read -r sysdevpath; do
    syspath="${sysdevpath%/dev}"
    devname="$(udevadm info -q name -p "$syspath")"
    if [[ "$devname" == "input/"* ]]; then
        eval "$(udevadm info -q property --export -p "$syspath")"
        if [[ -n "$ID_SERIAL" ]]; then
            echo "/dev/$devname"
        fi
    fi
done
"""
# Define the key code mappings for the characters
key_map = {
    # Alphabet
    ecodes.KEY_A: 'a', ecodes.KEY_B: 'b', ecodes.KEY_C: 'c', ecodes.KEY_D: 'd', ecodes.KEY_E: 'e',
    ecodes.KEY_F: 'f', ecodes.KEY_G: 'g', ecodes.KEY_H: 'h', ecodes.KEY_I: 'i', ecodes.KEY_J: 'j',
    ecodes.KEY_K: 'k', ecodes.KEY_L: 'l', ecodes.KEY_M: 'm', ecodes.KEY_N: 'n', ecodes.KEY_O: 'o',
    ecodes.KEY_P: 'p', ecodes.KEY_Q: 'q', ecodes.KEY_R: 'r', ecodes.KEY_S: 's', ecodes.KEY_T: 't',
    ecodes.KEY_U: 'u', ecodes.KEY_V: 'v', ecodes.KEY_W: 'w', ecodes.KEY_X: 'x', ecodes.KEY_Y: 'y',
    ecodes.KEY_Z: 'z',

    # Numerals
    ecodes.KEY_1: '1', ecodes.KEY_2: '2', ecodes.KEY_3: '3', ecodes.KEY_4: '4', ecodes.KEY_5: '5',
    ecodes.KEY_6: '6', ecodes.KEY_7: '7', ecodes.KEY_8: '8', ecodes.KEY_9: '9', ecodes.KEY_0: '0',

    # Punctuation marks
    ecodes.KEY_DOT: '.', ecodes.KEY_COMMA: ',', ecodes.KEY_SEMICOLON: ';', ecodes.KEY_APOSTROPHE: "'",
    ecodes.KEY_MINUS: '-', ecodes.KEY_EQUAL: '=', ecodes.KEY_LEFTBRACE: '[', ecodes.KEY_RIGHTBRACE: ']',
    ecodes.KEY_BACKSLASH: '\\', ecodes.KEY_SLASH: '/', ecodes.KEY_BACKSPACE: '\b',

    # Special keys
    ecodes.KEY_ENTER: '\n', ecodes.KEY_SPACE: ' ', ecodes.KEY_TAB: '\t',
    ecodes.KEY_LEFTSHIFT: 'SHIFT', ecodes.KEY_RIGHTSHIFT: 'SHIFT', ecodes.KEY_CAPSLOCK: 'CAPS',
    ecodes.KEY_LEFTALT: 'ALT', ecodes.KEY_RIGHTALT: 'ALT', ecodes.KEY_LEFTCTRL: 'CTRL',
    ecodes.KEY_RIGHTCTRL: 'CTRL', ecodes.KEY_LEFTMETA: 'META', ecodes.KEY_RIGHTMETA: 'META',
    ecodes.KEY_BACK: 'BACK', ecodes.KEY_ESC: 'ESC',
}
# Define the global capitalization SHIFT state
shift_pressed = False
# Define relay trigger pin
OUTPUT_PIN = 16


def get_input_source():
    # Execute the Bash script to find input sources
    process = subprocess.Popen(['bash', '-c', bash_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    output = output.decode('utf-8').strip()
    error = error.decode('utf-8')
    return output, error


def convert_key_event_to_string(key_event):
    global shift_pressed
    if key_event.code == ecodes.KEY_LEFTSHIFT or key_event.code == ecodes.KEY_RIGHTSHIFT:
        shift_pressed = (key_event.value == 1)
        return None  # Don't print anything for SHIFT key events
    elif key_event.code in key_map:
        key_string = key_map[key_event.code]
        if shift_pressed:
            return key_string.upper()
        else:
            return key_string
    else:
        return None


def send_http_request():
    url = 'https://worfact-api.infoart.com.tr/qrcode/scan'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic cXJfY29kZTpoZDJiZnRxazhodWttdWp4MHQyYng='
    }
    data = {
        'ip_address': '127.0.0.1',
        'user_id': 552,
        'mac_id': '1a:1a:1a:1a:1a'
    }
    response = requests.post(url, headers=headers, json=data, verify=False)
    return response.text.strip() == 'true'


def send_signal():
    GPIO.output(OUTPUT_PIN, GPIO.HIGH)
    time.sleep(0.1)
    GPIO.output(OUTPUT_PIN, GPIO.LOW)


def listen_to_input(input_source):
    try:
        # Open the input device using evdev
        device = InputDevice(input_source)
        print(f"Listening to {device.name}")
        # Initialize an empty string to store characters until ENTER is pressed
        input_string = ''

        # Start listening to input events
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:
                key_string = convert_key_event_to_string(event)
                if key_string:
                    # Append the character to the input string
                    if key_string == '\n':
                        # If ENTER is pressed, print the input string, send the HTTP request and reset the input string
                        res = send_http_request()
                        print(f"{input_string}: {res}")
                        if res:
                            send_signal()
                        input_string = ''
                    else:
                        input_string += key_string
    except FileNotFoundError:
        raise FileNotFoundError(f"Input source {input_source} not found.")
    except PermissionError:
        raise PermissionError(f"Permission denied while accessing {input_source}. Make sure to run the script as root.")


def main():
    while True:
        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(OUTPUT_PIN, GPIO.OUT)

            # Get the input source
            input_source, error = get_input_source()
            if error:
                print("Error while detecting USB input source")
                continue  # Retry the operation

            listen_to_input(input_source)  # Change this to the detected input source

        except KeyboardInterrupt:
            break  # Exit the loop on keyboard interrupt
        except Exception as e:
            print(f"An exception occurred: {e}")
            time.sleep(1)  # Wait for a second before retrying
        finally:
            GPIO.cleanup()

    print("Exiting...")


if __name__ == '__main__':
    main()