#!/bin/sh
# Mette da parte lo storico della Plancia di un progetto e riparte pulito. Nulla si cancella.
exec python3 "$(dirname "$0")/installa.py" --archivia "$@"
