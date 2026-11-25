#!/usr/bin/env bash
# Publica uma versão nova do Companion PC: os PCs instalados veem em até 6 h e oferecem "Atualizar".
# Uso: tools/release.sh 1.10 "O que mudou (aparece no app)"
set -euo pipefail
cd "$(dirname "$0")/.."

V="${1:-}"; NOTES="${2:-}"
SRV=windows/server/companion_server.py
CUR=$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' "$SRV")
if [[ ! "$V" =~ ^[0-9]+(\.[0-9]+){0,3}$ ]]; then
  echo "uso: tools/release.sh <versão> \"novidades\"   (versão atual: $CUR)"; exit 1
fi
# a versão nova tem que ser maior (comparação por número: 1.10 > 1.9)
if [[ "$(printf '%s\n%s\n' "$CUR" "$V" | sort -V | tail -1)" != "$V" || "$CUR" == "$V" ]]; then
  echo "a versão $V não é maior que a atual ($CUR)"; exit 1
fi
[[ "$(git rev-parse --abbrev-ref HEAD)" == main ]] || { echo "rode na branch main"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "há mudanças sem commit; faça o commit antes"; exit 1; }
git rev-parse -q --verify "refs/tags/v$V" >/dev/null && { echo "a tag v$V já existe"; exit 1; }

# testes no Python do Windows (quando roda pelo WSL), senão no python3 daqui
PY=$(command -v py.exe || command -v python3)
(cd windows/server && "$PY" -m unittest -q) || { echo "testes falharam - nada foi publicado"; exit 1; }

sed -i "s/^VERSION = \".*\"$/VERSION = \"$V\"/" "$SRV"
python3 -c 'import json,sys; print(json.dumps({"version": sys.argv[1], "notes": sys.argv[2]}, ensure_ascii=False, indent=2))' \
  "$V" "$NOTES" > release.json
git add "$SRV" release.json
git commit -q -m "versão $V" -m "$NOTES"
git tag -a "v$V" -m "Companion PC $V"
# envia; no WSL sem login no GitHub, tenta pelo git do Windows (que usa o login salvo no Windows)
push() {
  git push -q origin "$1" 2>/dev/null && return 0
  if command -v git.exe >/dev/null; then
    echo "git do WSL sem login no GitHub; enviando $1 pelo git do Windows..."
    git.exe -c safe.directory='*' push -q origin "$1" && { git fetch -q origin 2>/dev/null || true; return 0; }
  fi
  echo "não deu para enviar $1. O commit e a tag v$V já estão feitos; envie com: git push origin v$V && git push origin main"
  exit 1
}
# a tag sobe antes: quando o release.json novo aparecer no main, o zip da tag já existe
push "v$V"
push main
echo "Publicado: v$V. Os PCs instalados oferecem a atualização em até 6 h (ou em \"Procurar atualização\")."
