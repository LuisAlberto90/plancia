#!/bin/sh
# Prepara la Plancia in un progetto: ./Installa-in-un-progetto.sh [cartella]
exec python3 "$(dirname "$0")/installa.py" "$@"
