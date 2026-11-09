#!/bin/sh
# Scarica l ultima versione della Plancia (git pull) e aggiorna la skill per tutti i progetti.
D="$(cd "$(dirname "$0")" && pwd)"
git -C "$D" pull --ff-only && python3 "$D/factory.py" metodo --globale --scrivi && echo "Fatto. Riapri la Plancia."
