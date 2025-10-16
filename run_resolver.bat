@echo off
setlocal EnableDelayedExpansion

rem Navigate to repository root
pushd "%~dp0"

rem Activate virtual environment if present
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

rem Load environment variables from .env (ignores comments and blank lines)
if exist ".env" (
    echo Loading environment from .env ...
    for /f "usebackq eol=# tokens=1* delims==" %%A in (".env") do (
        set "envName=%%A"
        if defined envName (
            set "envValue=%%B"
            if defined envValue (
                if "!envValue:~0,1!"==^" (
                    if "!envValue:~-1!"==^" (
                        set "envValue=!envValue:~1,-1!"
                    )
                )
            )
            set "!envName!=!envValue!"
            echo   !envName!=!envValue!
        )
    )
) else (
    echo No .env file found. Using existing environment.
)

where python >nul 2>&1
if errorlevel 1 (
    echo Python interpreter not found. Install Python or ensure the virtual environment is set up.
    popd
    pause
    exit /b 1
)

set "resolverPort=%RESOLVER_PORT%"
if "%resolverPort%"=="" set "resolverPort=%PORT%"
if "%resolverPort%"=="" set "resolverPort=5055"

echo Starting Streamarr resolver on port %resolverPort% ...
python -m flask --app backend.resolver.api run --host 0.0.0.0 --port %resolverPort%
set "exitCode=%ERRORLEVEL%"

popd
if not "%exitCode%"=="0" (
    echo Resolver exited with code %exitCode%.
    pause
)
exit /b %exitCode%
