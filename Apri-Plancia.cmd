@echo off
rem Doppio clic: apre la Plancia con tutti i progetti (scheda Progetti). Chiudi la finestra per fermarla.
cd /d "%USERPROFILE%"
py "%~dp0factory.py" pannello
if errorlevel 9009 python "%~dp0factory.py" pannello
pause
