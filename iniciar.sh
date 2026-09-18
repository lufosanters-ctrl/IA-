#!/usr/bin/env bash
# Sobe o Núcleo criando o ambiente virtual na primeira execução.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "→ criando ambiente virtual…"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
  echo "→ dependências instaladas"
fi

[ -f .env ] || { cp .env.example .env; echo "→ .env criado a partir do exemplo"; }

exec ./.venv/bin/python -m app
