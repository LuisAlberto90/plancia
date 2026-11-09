@echo off
rem Doppio clic: scarica l ultima versione della Plancia (git pull) e aggiorna la skill per tutti i progetti.
git -C "%~dp0." pull --ff-only
if errorlevel 1 (echo. & echo Aggiornamento non riuscito: copia le righe sopra e mandale a chi ti supporta. & pause & exit /b 1)
py "%~dp0factory.py" metodo --globale --scrivi
if errorlevel 9009 python "%~dp0factory.py" metodo --globale --scrivi
echo.
echo Fatto. Chiudi le finestre della Plancia aperte e riaprila con Apri-Plancia.cmd.
pause
