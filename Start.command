#!/bin/sh
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Bitte Python 3.11 oder neuer von https://www.python.org installieren.'
  exit 1
fi
exec python3 start.py "$@"
