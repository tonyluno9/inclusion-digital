@echo off
chcp 65001 >nul
setlocal EnableExtensions
pushd "%~dp0"

echo ============================================
echo  Instalador - Reconocimiento de LSM
echo ============================================
echo.

rem --- Buscar Python 3.10 - 3.12 ---
set "PYCMD="
for %%V in (3.12 3.11 3.10) do (
    if not defined PYCMD (
        py -%%V -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PYCMD=py -%%V"
    )
)
if not defined PYCMD (
    python -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,12) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYCMD=python"
)
if not defined PYCMD (
    echo [ERROR] No se encontro Python 3.10, 3.11 o 3.12.
    echo         Descargalo en: https://www.python.org/downloads/
    echo         Durante la instalacion marca "Add python.exe to PATH".
    goto :fin
)
echo Python encontrado: usando "%PYCMD%"
%PYCMD% --version

rem --- Entorno virtual ---
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Creando entorno virtual en .venv ...
    %PYCMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        goto :fin
    )
) else (
    echo Entorno virtual .venv ya existe.
)
set "VPY=.venv\Scripts\python.exe"

echo.
echo Actualizando pip ...
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] No se pudo actualizar pip.
    goto :fin
)

echo.
echo Instalando dependencias (requirements.txt) ...
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de requirements.txt.
    goto :fin
)

echo.
choice /C SN /M "Instalar tambien los paquetes opcionales (voz a texto, requirements-opcional.txt)"
if errorlevel 2 (
    echo Se omiten los paquetes opcionales.
) else (
    "%VPY%" -m pip install -r requirements-opcional.txt
    if errorlevel 1 echo [AVISO] Algun paquete opcional no se pudo instalar; la app funciona sin el.
)

echo.
echo Ejecutando pruebas ...
"%VPY%" -m unittest discover -s tests -t .
if errorlevel 1 (
    echo.
    echo [AVISO] Hubo pruebas con error. Revisa los mensajes anteriores.
) else (
    echo.
    echo [OK] Instalacion completa y pruebas correctas. Abre iniciar.bat para usar la app.
)

echo.
choice /C SN /M "Crear el acceso directo INCLUSION en el Escritorio"
if not errorlevel 2 call "%~dp0crear_acceso_directo.bat"

:fin
echo.
popd
pause
endlocal
