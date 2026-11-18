#!/bin/bash
# R36S PC Companion - liga/desliga rede USB via configfs.
# Uso: sudo ./companion-usbnet.sh up | down | status
# Função: RNDIS por padrão (NCM falha com Windows no kernel 4.4); FUNC=ncm para testar NCM
# R36S = 10.55.0.2   PC = 10.55.0.1

set -u
[ "$(id -u)" -ne 0 ] && exec sudo -- "$0" "$@"
LOG="$(dirname "$(readlink -f "$0")")/companion-usbnet.log"
exec > >(tee -a "$LOG") 2>&1

case "$(basename "$0")" in *rndis*) FUNC=${FUNC:-rndis} ;; esac
FUNC=${FUNC:-rndis}   # NCM do kernel 4.4 não passa dados no Windows 11
echo "---- $(date '+%F %T') $0 ${1:-up} (FUNC=$FUNC)"

G=/sys/kernel/config/usb_gadget/r36s
IP_R36S=10.55.0.2/24
VID=0x1d6b   # Linux Foundation
PID=0x0104   # Multifunction Composite Gadget
F=functions/$FUNC.usb0

up() {
  modprobe libcomposite 2>/dev/null
  modprobe "usb_f_$FUNC" 2>/dev/null
  mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config

  UDC=$(ls /sys/class/udc 2>/dev/null | head -1)
  [ -z "$UDC" ] && { echo "ERRO: nenhum UDC. Porta OTG em modo host? Rode Companion-Diag.sh"; exit 1; }

  [ -d "$G" ] && down >/dev/null
  mkdir -p "$G" && cd "$G" || exit 1

  echo $VID > idVendor
  echo $PID > idProduct
  echo 0x0100 > bcdDevice
  echo 0x0200 > bcdUSB
  mkdir -p strings/0x409
  echo "R36S$(cut -c1-8 /etc/machine-id 2>/dev/null)" > strings/0x409/serialnumber
  echo "R36S"                > strings/0x409/manufacturer
  echo "R36S PC Companion"   > strings/0x409/product

  mkdir -p configs/c.1/strings/0x409
  echo "$FUNC" > configs/c.1/strings/0x409/configuration
  echo 250     > configs/c.1/MaxPower

  mkdir -p "$F" || { echo "ERRO: função $FUNC indisponível no kernel"; exit 1; }
  # MACs fixos para o Windows reconhecer sempre o mesmo adaptador
  echo "02:36:53:00:00:01" > "$F/host_addr"
  echo "02:36:53:00:00:02" > "$F/dev_addr"

  if [ "$FUNC" = rndis ]; then
    # Descritores Microsoft OS: Windows instala o driver RNDIS sozinho
    echo 0xEF > bDeviceClass; echo 0x02 > bDeviceSubClass; echo 0x01 > bDeviceProtocol
    if [ -d os_desc ]; then
      echo 1       > os_desc/use
      echo 0xcd    > os_desc/b_vendor_code
      echo MSFT100 > os_desc/qw_sign
      echo RNDIS   > "$F/os_desc/interface.rndis/compatible_id"
      echo 5162001 > "$F/os_desc/interface.rndis/sub_compatible_id"
      ln -s configs/c.1 os_desc/
    fi
  fi
  ln -s "$F" configs/c.1/

  echo "$UDC" > UDC || { echo "ERRO ao ativar UDC $UDC"; exit 1; }

  IFACE=$(cat "$F/ifname" 2>/dev/null)
  case "$IFACE" in ""|*unnamed*) IFACE=usb0 ;; esac
  for _ in 1 2 3 4 5; do ip link show "$IFACE" >/dev/null 2>&1 && break; sleep 1; done
  ip addr flush dev "$IFACE" 2>/dev/null
  ip addr add $IP_R36S dev "$IFACE"
  ip link set "$IFACE" up
  echo "OK: $IFACE = $IP_R36S (UDC $UDC, $FUNC)"
  sleep 3
  report
}

down() {
  [ -d "$G" ] || { echo "gadget não está ativo"; return 0; }
  cd "$G" || return
  echo "" > UDC 2>/dev/null
  rm -f os_desc/c.1 configs/c.1/ncm.usb0 configs/c.1/rndis.usb0
  rmdir configs/c.1/strings/0x409 configs/c.1 functions/ncm.usb0 functions/rndis.usb0 strings/0x409 2>/dev/null
  cd / && rmdir "$G" 2>/dev/null
  echo "gadget removido"
}

report() {
  echo "== ip addr";   ip addr
  echo "== rotas";     ip route
  echo "== udc state"; cat /sys/class/udc/*/state 2>/dev/null
  echo "== firewall";  iptables -S 2>/dev/null | head -20; nft list ruleset 2>/dev/null | head -20
  echo "== ping PC";   ping -c 3 -W 1 10.55.0.1
  echo "== dmesg";     dmesg | grep -iE 'gadget|udc|dwc2|ncm|rndis|usb0|composite' | tail -40
}

status() {
  [ -d "$G" ] && echo "gadget ativo, UDC=$(cat $G/UDC)" || echo "gadget inativo"
  report
}

case "${1:-up}" in
  up) up ;; down) down ;; status) status ;;
  *) echo "uso: $0 up|down|status"; exit 1 ;;
esac
