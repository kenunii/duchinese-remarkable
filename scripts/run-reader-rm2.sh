#!/bin/sh
set -eu

APP=${1:-/home/root/duchinese-reader/duchinese_reader}

restore_xochitl() {
    systemctl start xochitl
}

trap restore_xochitl EXIT HUP INT TERM

systemctl stop xochitl
export QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS="rotate=180:invertx"
export QT_QUICK_BACKEND=epaper
"$APP" -platform epaper
