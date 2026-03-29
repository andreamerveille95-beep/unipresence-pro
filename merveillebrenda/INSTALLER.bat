@echo off
setlocal enabledelayedexpansion
title UniPresence Pro — Installation
color 0B
chcp 65001 >nul 2>&1

echo.
echo  ╔════════════════════════════════════════════════════╗
echo  ║         UniPresence Pro — Installation             ║
echo  ║     Institut Universitaire de l'Entrepreneuriat    ║
echo  ║                  IUE Douala                        ║
echo  ╚════════════════════════════════════════════════════╝
echo.

:: ─────────────────────────────────────────────────────────
::  ÉTAPE 1 — Vérification de Python
:: ─────────────────────────────────────────────────────────
echo  [1/4]  Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo.
    echo  Téléchargez Python 3.10 ou plus récent ici :
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT : Cochez "Add Python to PATH" lors de l'installation.
    echo.
    start https://www.python.org/downloads/
    echo  Appuyez sur une touche pour fermer...
    pause >nul
    exit /b 1
)

:: Vérifier la version minimale (3.10)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if !PY_MAJOR! LSS 3 (
    echo  [ERREUR] Python !PYVER! détecté. Version 3.10+ requise.
    echo  Appuyez sur une touche pour fermer...
    pause >nul
    exit /b 1
)
if !PY_MAJOR! EQU 3 if !PY_MINOR! LSS 10 (
    echo  [ERREUR] Python !PYVER! détecté. Version 3.10+ requise.
    echo  Appuyez sur une touche pour fermer...
    pause >nul
    exit /b 1
)
echo         Python !PYVER! detecté  [OK]

:: ─────────────────────────────────────────────────────────
::  ÉTAPE 2 — Environnement virtuel
:: ─────────────────────────────────────────────────────────
echo.
echo  [2/4]  Création de l'environnement virtuel...
if exist "%~dp0venv\Scripts\activate.bat" (
    echo         Environnement virtuel déjà présent  [OK]
) else (
    python -m venv "%~dp0venv"
    if errorlevel 1 (
        echo  [ERREUR] Impossible de créer l'environnement virtuel.
        pause >nul
        exit /b 1
    )
    echo         Environnement virtuel créé  [OK]
)

:: ─────────────────────────────────────────────────────────
::  ÉTAPE 3 — Installation des dépendances
:: ─────────────────────────────────────────────────────────
echo.
echo  [3/4]  Installation des dépendances Python...
echo         (bcrypt, qrcode, Pillow, ReportLab, OpenCV...)
echo.
call "%~dp0venv\Scripts\activate.bat"
pip install --upgrade pip --quiet
pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo  [ERREUR] L'installation des dépendances a échoué.
    echo  Vérifiez votre connexion Internet et réessayez.
    pause >nul
    exit /b 1
)
echo.
echo  [3/4]  Dépendances installées  [OK]

:: ─────────────────────────────────────────────────────────
::  ÉTAPE 4 — Vérification de la base de données
:: ─────────────────────────────────────────────────────────
echo.
echo  [4/4]  Vérification de la base de données...
if not exist "%~dp0backend\data" (
    mkdir "%~dp0backend\data"
)
echo         Dossier data prêt  [OK]

:: ─────────────────────────────────────────────────────────
::  INSTALLATION TERMINÉE
:: ─────────────────────────────────────────────────────────
echo.
echo  ╔════════════════════════════════════════════════════╗
echo  ║           Installation terminée !                  ║
echo  ╠════════════════════════════════════════════════════╣
echo  ║                                                    ║
echo  ║   Pour lancer l'application :                      ║
echo  ║     Double-cliquez sur  DEMARRER.bat               ║
echo  ║                                                    ║
echo  ║   Puis ouvrez votre navigateur :                   ║
echo  ║     http://localhost:5000                          ║
echo  ║                                                    ║
echo  ║   Identifiants par défaut :                        ║
echo  ║     Email    : admin@iue.cm                        ║
echo  ║     Mot de passe : admin123                        ║
echo  ║                                                    ║
echo  ╚════════════════════════════════════════════════════╝
echo.

set /p LAUNCH="  Lancer l'application maintenant ? [O/N] : "
if /i "!LAUNCH!"=="O" (
    echo.
    echo  Démarrage du serveur...
    start "" "%~dp0DEMARRER.bat"
    timeout /t 2 >nul
    start http://localhost:5000
)

echo.
echo  Appuyez sur une touche pour fermer cette fenêtre...
pause >nul
endlocal
