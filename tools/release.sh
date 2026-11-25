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
# a tag sobe antes: quando o release.json novo aparecer no main, o zip da tag já existe
git push -q origin "v$V"
git push -q origin main
echo "Publicado: v$V. Os PCs instalados oferecem a atualização em até 6 h (ou em \"Procurar atualização\")."
