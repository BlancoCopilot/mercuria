@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
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
call _clave.bat
%PY% ingestar.py
if not errorlevel 1 %PY% exportar_sql.py
echo.
echo Si dice LISTO, cierra la ventana del chatbot y vuelve a abrir INICIAR.bat
pause

exit /b
:sinpython
echo No encuentro Python.
pause
