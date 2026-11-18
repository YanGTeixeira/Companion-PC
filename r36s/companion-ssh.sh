#!/bin/bash
# R36S PC Companion - liga a rede USB (se preciso) e o servidor SSH,
# autorizando a chave r36s_companion.pub que está na mesma pasta.
# Log: companion-ssh.log ao lado do script.

[ "$(id -u)" -ne 0 ] && exec sudo -- "$0" "$@"
DIR="$(dirname "$(readlink -f "$0")")"
exec > >(tee -a "$DIR/companion-ssh.log") 2>&1
echo "---- $(date '+%F %T') $0"

# 1) rede USB
if ! ip -br addr 2>/dev/null | grep -q '10\.55\.0\.2/'; then
  echo "== ligando rede USB (RNDIS)"
  FUNC=rndis bash "$DIR/companion-usbnet.sh" up >/dev/null 2>&1
fi
ip -br addr | grep 10.55.0.2 || echo "AVISO: 10.55.0.2 não configurado"

# 2) usuário principal (dono de /home/*, uid >= 1000)
USR=$(awk -F: '$3>=1000 && $3<60000 && $6 ~ /^\/home\// {print $1; exit}' /etc/passwd)
HOMEDIR=$(getent passwd "$USR" | cut -d: -f6)
echo "== usuário: $USR ($HOMEDIR)"

# 3) chave autorizada
if [ -f "$DIR/r36s_companion.pub" ]; then
  install -d -m 700 -o "$USR" -g "$USR" "$HOMEDIR/.ssh"
  AK="$HOMEDIR/.ssh/authorized_keys"
  touch "$AK"
  grep -qF "$(cut -d' ' -f2 "$DIR/r36s_companion.pub")" "$AK" || { tr -d '\r' < "$DIR/r36s_companion.pub" >> "$AK"; echo >> "$AK"; }
  chown "$USR:$USR" "$AK"; chmod 600 "$AK"
  echo "chave autorizada em $AK"
else
  echo "AVISO: r36s_companion.pub não encontrado em $DIR"
fi

# 4) servidor SSH
if command -v sshd >/dev/null || [ -x /usr/sbin/sshd ]; then
  echo "== OpenSSH encontrado"
  ssh-keygen -A >/dev/null 2>&1
  systemctl enable ssh 2>/dev/null || systemctl enable sshd 2>/dev/null
  systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || /usr/sbin/sshd
  sleep 1
  systemctl --no-pager status ssh 2>/dev/null | head -5
elif command -v dropbear >/dev/null; then
  echo "== Dropbear encontrado"
  systemctl enable --now dropbear 2>/dev/null || dropbear -R -p 22
else
  echo ">>> NENHUM servidor SSH instalado (nem OpenSSH nem Dropbear)"
  echo "pacotes ssh:"; dpkg -l 2>/dev/null | grep -iE 'ssh|dropbear' | awk '{print $1,$2,$3}'
fi

echo "== porta 22"
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep -E ':22\b' || echo "nada escutando na 22"
echo "== firewall"; iptables -S 2>/dev/null | head -10
echo "fim."
sleep 3
