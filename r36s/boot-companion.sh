#!/bin/bash
# R36S PC Companion - abre o app no boot, antes do EmulationStation.
# Chamado pelo drop-in emulationstation.service.d/companion.conf (ExecStartPre).
# Só roda uma vez por boot; ao sair do app, o EmulationStation abre.
# Desativar: crie ~/.config/.NO_BOOT_COMPANION (ou use a aba Sistema do app).

[ -f "$HOME/.config/.NO_BOOT_COMPANION" ] && exit 0
[ -f /dev/shm/companion-booted ] && exit 0
touch /dev/shm/companion-booted

/opt/r36s-companion/run-companion.sh --boot
exit 0
