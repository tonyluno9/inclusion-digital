@echo off
rem Crea el acceso directo "K'ab T'aan" (con el logo) que abre la app. La consola queda minimizada.
rem Uso: crear_acceso_directo.bat            -> en el Escritorio
rem      crear_acceso_directo.bat CARPETA    -> en otra carpeta
setlocal
set "APP=%~dp0"
set "DESTINO=%~1"
if "%DESTINO%"=="" for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESTINO=%%D"

powershell -NoProfile -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%DESTINO%\K''ab T''aan.lnk');" ^
  "$s.TargetPath = '%APP%iniciar.bat';" ^
  "$s.WorkingDirectory = '%APP%';" ^
  "$s.IconLocation = '%APP%web\assets\img\logo.ico';" ^
  "$s.Description = 'K''ab T''aan - Lengua de Senas Mexicana a texto, voz y avatar';" ^
  "$s.WindowStyle = 7;" ^
  "$s.Save()"
if errorlevel 1 (
    echo [ERROR] No se pudo crear el acceso directo.
    exit /b 1
)
echo Acceso directo creado: %DESTINO%\K'ab T'aan.lnk
endlocal
