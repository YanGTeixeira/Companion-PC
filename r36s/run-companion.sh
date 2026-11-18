#!/bin/bash
# R36S PC Companion - garante a rede USB e abre o app.
# Usado pelo lançador do Ports e pelo boot (boot-companion.sh).
APP=/roms/ports/pc-companion

# Rede USB: se o IP não estiver no usb0, refaz o gadget
if ! ip -br addr show usb0 2>/dev/null | grep -q '10\.55\.0\.2/'; then
  sudo systemctl restart r36s-companion-usbnet.service
fi

export TERM=linux
[ -d "/run/user/$UID" ] && export XDG_RUNTIME_DIR="/run/user/$UID"
sudo chmod 666 /dev/tty1 2>/dev/null
printf "\033c" > /dev/tty1 2>/dev/null

cd "$APP" || exit 1
python3 companion.py "$@" > "$APP/companion.log" 2>&1
rc=$?
printf "\033c" > /dev/tty1 2>/dev/null
exit $rc
