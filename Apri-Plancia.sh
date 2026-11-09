#!/bin/sh
cd "$HOME" && exec python3 "$(dirname "$(readlink -f "$0")")/factory.py" pannello
