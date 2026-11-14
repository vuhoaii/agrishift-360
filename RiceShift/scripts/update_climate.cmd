@echo off
cd /d "%~dp0.."
if not exist "logs" mkdir "logs"
"C:\Users\LOQ\AppData\Local\Programs\Python\Python312\python.exe" -m services.climate_updater > "logs\climate_update_latest.log" 2>&1
exit /b %ERRORLEVEL%