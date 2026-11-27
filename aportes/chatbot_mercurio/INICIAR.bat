@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title Chatbot Mercurio

set PY=
if exist "%USERPROFILE%\anaconda3\python.exe" set PY="%USERPROFILE%\anaconda3\python.exe"
if exist "%USERPROFILE%\anaconda3_new\python.exe" set PY="%USERPROFILE%\anaconda3_new\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if defined PY goto pyok
where python >nul 2>nul
if errorlevel 1 goto sinpython
set PY=python
:pyok
echo Usando Python: %PY%

if exist .instalado goto clave
echo Instalando lo necesario (solo la primera vez, tarda unos minutos)...
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto error
echo ok> .instalado

:clave
call _clave.bat

if exist indice_vectores.npy goto encender
echo.
echo Leyendo documentos por primera vez...
%PY% ingestar.py
if errorlevel 1 goto error

:encender
echo.
echo ===========================================================
echo  CHATBOT ENCENDIDO. NO CIERRES ESTA VENTANA.
echo  Para probarlo: http://localhost:8000/docs
echo  Para tu amiga: http://TU-IP:8000/chat   (tu IP es la de abajo)
ipconfig | findstr /i "IPv4"
echo  Si Windows pregunta por el Firewall, dale "Permitir".
echo ===========================================================
start "" http://localhost:8000/docs
%PY% -m uvicorn api:app --host 0.0.0.0 --port 8000
pause
exit /b

:sinpython
echo No encuentro Python. Instálalo desde https://www.python.org/downloads/
echo y MARCA la casilla "Add Python to PATH". Luego vuelve a abrir INICIAR.bat
pause
exit /b

:error
echo.
echo Algo falló. Sácale una captura a esta ventana y mándasela a Claude.
pause
