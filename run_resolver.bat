@echo off
setlocal

rem Launch the Streamarr resolver API in the background using the project virtualenv.

set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [Streamarr] Virtualenv python not found at "%VENV_PY%".
    echo [Streamarr] Run ^`python -m venv .venv^` and install requirements first.
    exit /b 1
)

if "%~1" NEQ "" (
    set "PROXY_BASE_URL=%~1"
)

if "%PROXY_BASE_URL%" NEQ "" (
    echo [Streamarr] Using PROXY_BASE_URL=%PROXY_BASE_URL%
) else (
    echo [Streamarr] PROXY_BASE_URL not set; playlists will reuse the incoming host.
)

if not defined RESOLVER_PORT (
    set "RESOLVER_PORT=5055"
)

echo [Streamarr] Starting resolver on port %RESOLVER_PORT%...
pushd "%ROOT%"
start "Streamarr Resolver" "%VENV_PY%" -m backend.resolver.api
popd

echo [Streamarr] Resolver launched in a separate window. Close that window or use taskkill to stop it.
exit /b 0
