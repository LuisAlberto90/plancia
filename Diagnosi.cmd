@echo off
rem Doppio clic: crea lo zip di diagnosi di un progetto (nessun codice sorgente) e apre la cartella dove si trova.
py "%~dp0installa.py" --diagnosi %*
if errorlevel 9009 python "%~dp0installa.py" --diagnosi %*
