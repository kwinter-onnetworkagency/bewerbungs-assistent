#!/usr/bin/env python3
"""Offline-Einstieg ohne Paketinstallation."""
import sys

if sys.version_info < (3, 11):
    raise SystemExit("Bitte zuerst Python 3.11 oder neuer von https://www.python.org installieren.")

from bewerbung.cli import main

if __name__ == "__main__":
    main()
