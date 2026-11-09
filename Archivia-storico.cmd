@echo off
rem Doppio clic: mette da parte lo storico della Plancia di un progetto (piani, eventi, prove) e riparte pulito. Nulla si cancella.
py "%~dp0installa.py" --archivia %*
if errorlevel 9009 python "%~dp0installa.py" --archivia %*
pause
