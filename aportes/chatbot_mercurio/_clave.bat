@echo off
rem Carga la API key desde clave.txt, o la pide la primera vez
if exist clave.txt goto leer
echo.
set /p OPENAI_API_KEY=Pega tu API key de OpenAI (empieza con sk-) y presiona Enter: 
echo %OPENAI_API_KEY%> clave.txt
echo (Guardada en clave.txt. NO compartas ese archivo con nadie.)
goto fin
:leer
set /p OPENAI_API_KEY=<clave.txt
:fin
