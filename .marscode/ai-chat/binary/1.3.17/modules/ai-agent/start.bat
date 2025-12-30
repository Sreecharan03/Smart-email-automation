@echo off
REM for dev

if defined MARSCODE_DEV_MODE (
    if defined MARSCODE_DEV_AI_AGENT_MANUAL (
        :loop
        timeout /t 99999 >nul
        goto loop
    ) else (
        set "RUST_LOG=info"
        set "CLOUDIDE_TENANT_NAME=cn"
        set "ICUBE_MODULAR_DATA_DIR=%USERPROFILE%\.icube"
        set "DB_PATH=%USERPROFILE%\.icube\ai-agent\database.db"
        set "FILE_BASE_DIR=%USERPROFILE%\.icube\ai-agent\snapshot"
        set "TTNET_LIB_DIR_PATH=%~dp0deps\ttnet\windows"
        cargo run
    )
) else (
    if "%TRAE_RESOLVE_TYPE%"=="remote" (
        set "AI_NATIVE_ENV=plugin_remote"
    ) else if "%TRAE_RESOLVE_TYPE%"=="ssh" (
        set "AI_NATIVE_ENV=desktop_ssh"
    )
    set "DB_PATH=%ICUBE_MODULAR_DATA_DIR%\ai-agent\database.db"
    set "FILE_BASE_DIR=%ICUBE_MODULAR_DATA_DIR%\ai-agent\snapshot"

    ai-agent.exe
)
