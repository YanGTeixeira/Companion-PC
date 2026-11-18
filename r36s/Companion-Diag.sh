#!/bin/bash
# R36S PC Companion - diagnóstico de USB gadget
# Copie para /roms/ports/ (ou /roms2/ports/) e rode pelo menu Ports.
# Gera um relatório em /roms/ports/companion-diag.txt (ou ao lado do script).

[ "$(id -u)" -ne 0 ] && exec sudo -- "$0" "$@"

OUT="$(dirname "$(readlink -f "$0")")/companion-diag.txt"
exec > >(tee "$OUT") 2>&1

sec() { echo; echo "===== $* ====="; }

sec "SISTEMA"
uname -a
cat /etc/os-release 2>/dev/null | head -5
cat /proc/device-tree/model 2>/dev/null; echo
free -m | head -2

sec "CONFIG DO KERNEL (gadget)"
if [ -r /proc/config.gz ]; then
  zcat /proc/config.gz | grep -E 'USB_GADGET|USB_CONFIGFS|USB_F_|USB_LIBCOMPOSITE|USB_DWC2|USB_ROLE|USB_OTG' | sort
else
  CFG="/boot/config-$(uname -r)"
  [ -r "$CFG" ] && grep -E 'USB_GADGET|USB_CONFIGFS|USB_F_|USB_LIBCOMPOSITE|USB_DWC2|USB_ROLE' "$CFG" | sort \
    || echo "config do kernel indisponível (sem /proc/config.gz)"
fi

sec "MÓDULOS DISPONÍVEIS"
find "/lib/modules/$(uname -r)" -name '*.ko*' 2>/dev/null \
  | grep -Ei 'libcomposite|usb_f_|g_ether|g_serial|dwc2|u_ether' || echo "nenhum módulo de gadget encontrado"
echo "-- carregados:"
lsmod 2>/dev/null | grep -Ei 'composite|usb_f|dwc2|g_' || echo "(nenhum)"

sec "TENTATIVA DE CARREGAR libcomposite"
modprobe libcomposite 2>&1 && echo "libcomposite OK" || echo "libcomposite falhou (pode estar embutido no kernel)"

sec "CONTROLADOR USB DEVICE (UDC)"
ls -l /sys/class/udc/ 2>/dev/null || echo "sem /sys/class/udc"
[ -z "$(ls /sys/class/udc 2>/dev/null)" ] && echo ">>> NENHUM UDC: a porta OTG provavelmente está fixa em modo host"

sec "MODO DA PORTA OTG (device tree)"
find /proc/device-tree -name dr_mode 2>/dev/null | while read -r f; do
  printf '%s = %s\n' "$f" "$(tr -d '\0' < "$f")"
done
ls /sys/class/usb_role/ 2>/dev/null && for r in /sys/class/usb_role/*/role; do echo "$r = $(cat "$r")"; done
for f in /sys/devices/platform/*usb*/*/otg_mode /sys/devices/platform/*/otg_mode; do
  [ -e "$f" ] && echo "$f = $(cat "$f")"
done

sec "CONFIGFS"
mount | grep configfs || { mount -t configfs none /sys/kernel/config 2>&1 && echo "configfs montado agora"; }
ls /sys/kernel/config/usb_gadget 2>/dev/null && echo "usb_gadget disponível" || echo ">>> /sys/kernel/config/usb_gadget AUSENTE"

sec "REDE"
ip -br link 2>/dev/null || ifconfig -a
which udhcpd dnsmasq 2>/dev/null

sec "PYTHON / PYGAME / SDL"
python3 --version 2>&1
python3 -c "import pygame; print('pygame', pygame.version.ver, 'SDL', pygame.get_sdl_version())" 2>&1
python3 -c "import websockets; print('websockets', websockets.__version__)" 2>&1 | tail -1
ls /dev/input/ 2>/dev/null

sec "USB ATUAL"
lsusb 2>/dev/null || cat /sys/kernel/debug/usb/devices 2>/dev/null | head -40

echo
echo "Relatório salvo em: $OUT"
sleep 3
