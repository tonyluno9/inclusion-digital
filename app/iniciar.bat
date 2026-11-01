@echo off
chcp 65001 >nul
pushd "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [AVISO] No hay entorno .venv; se usa el Python del sistema. Ejecuta instalar.bat primero.
)

python main.py %*
set "CODIGO=%errorlevel%"

popd
if not "%CODIGO%"=="0" (
    echo.
    echo [ERROR] La aplicacion termino con errores ^(codigo %CODIGO%^).
    echo         Si es la primera vez, ejecuta instalar.bat. Revisa los mensajes anteriores.
    pause
)
exit /b %CODIGO%
