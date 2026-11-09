@echo off
rem Doppio clic: scegli la cartella del progetto. Oppure trascina la cartella del progetto su questo file.
py "%~dp0installa.py" %*
if errorlevel 9009 python "%~dp0installa.py" %*
