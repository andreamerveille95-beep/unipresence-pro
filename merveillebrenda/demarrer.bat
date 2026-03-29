@echo off
setlocal
title UniPresence Pro — IUE Douala
color 0A
chcp 65001 >nul 2>&1

echo.
echo  ╔════════════════════════════════════════════════════╗
echo  ║          UniPresence Pro — IUE Douala              ║
echo  ║        Serveur en cours de démarrage...            ║
echo  ╚════════════════════════════════════════════════════╝
echo.

:: ── Vérifier que l'installation a été faite ──────────────
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo  [ATTENTION] L'installation n'a pas encore été effectuée.
    echo.
    echo  Veuillez d'abord double-cliquer sur  INSTALLER.bat
    echo.
    echo  Appuyez sur une touche pour fermer...
    pause >nul
    exit /b 1
)

:: ── Activer l'environnement virtuel ──────────────────────
call "%~dp0venv\Scripts\activate.bat"

:: ── Informations de connexion ─────────────────────────────
echo  Adresse principale  :  http://localhost:5000
echo  Scanner QR          :  http://localhost:5000/scanner
echo  Tableau de bord     :  http://localhost:5000/dashboard
echo.
echo  Identifiants admin  :  admin@iue.cm  /  admin123
echo.
echo  ─────────────────────────────────────────────────────
echo  NE PAS FERMER CETTE FENETRE
echo  (Le serveur s'arrête si vous la fermez)
echo  ─────────────────────────────────────────────────────
echo.

:: ── Lancer le serveur ─────────────────────────────────────
cd /d "%~dp0backend"
python server.py

echo.
echo  ─────────────────────────────────────────────────────
echo  Le serveur s'est arrêté.
echo  Appuyez sur une touche pour fermer...
pause >nul
endlocal
