@echo off
REM for dev

if defined MARSCODE_DEV_MODE (
    if defined MARSCODE_DEV_CKG_MANUAL (
        :loop
        timeout /t 99999 >nul
        goto loop
    ) else (
        set "AI_NATIVE_ENV=desktop"
        set "RUST_LOG=INFO"
        set "CLOUDIDE_TENANT_NAME=cn"
        set "ICUBE_MODULAR_DATA_DIR=%USERPROFILE%\.icube"
        set "DB_PATH=%USERPROFILE%\.icube\ai-chat\database.db"
        set "FILE_BASE_DIR=%USERPROFILE%\.icube\ai-chat\snapshot"
        set "ICUBE_PRODUCT_PROVIDER=Spring"
        set "DEV_MODE=1"

        set "platform=win32"
        node .\rust-ai-ckg.mjs

        REM set default value
        if not defined CKG_APP_ID (
            set "CKG_APP_ID=6eefa01c-1036-4c7e-9ca5-d891f63bfcd8"
        )
        if not defined CKG_SOURCE_PRODUCT (
            set "CKG_SOURCE_PRODUCT=native_ide"
        )

        .\binary\ckg_server_windows_x64.exe -port=%PORT0% -ide_version=%ICUBE_BUILD_VERSION% -version_code=2 -storage_path="%ICUBE_MODULAR_DATA_DIR%\ckg_server" -local_embedding -embedding_storage_type=sqlite_vec -app_id=%CKG_APP_ID% -limit_cpu=1 -source_product=%CKG_SOURCE_PRODUCT%
    )
) else (
    if "%AI_NATIVE_ENV%"=="plugin" (
        if "%TRAE_RESOLVE_TYPE%"=="remote" (
            set "AI_NATIVE_ENV=plugin_remote"
        ) else (
            set "AI_NATIVE_ENV=plugin"
        )
    ) else if "%AI_NATIVE_ENV%"=="plugin_boe" (
        if "%TRAE_RESOLVE_TYPE%"=="remote" (
            set "AI_NATIVE_ENV=plugin_remote"
        ) else (
            set "AI_NATIVE_ENV=plugin"
        )
    ) else if "%ICUBE_PRODUCT_TYPE%"=="desktop" (
        if "%TRAE_RESOLVE_TYPE%"=="ssh" (
            set "AI_NATIVE_ENV=desktop_ssh"
        )  else (
            set "AI_NATIVE_ENV=desktop"
        )
    ) else if "%CLOUDIDE_TENANT_NAME%"=="bytedance" (
        set "AI_NATIVE_ENV=cloudide"
    ) else if "%CLOUDIDE_PROJECT_SCENE%"=="practice" (
        set "AI_NATIVE_ENV=practice"
    ) else if "%CLOUDIDE_PROVIDER_REGION%"=="cn" (
        set "AI_NATIVE_ENV=marscode_boe"
    ) else if "%CLOUDIDE_PROVIDER_REGION%"=="us" (
        set "AI_NATIVE_ENV=marscode_boei18n"
    ) else if "%CLOUDIDE_PROVIDER_REGION%"=="sg" (
        set "AI_NATIVE_ENV=marscode_boei18n"
    ) else (
        set "AI_NATIVE_ENV=marscode_boe"
    )

    set "DB_PATH=%ICUBE_MODULAR_DATA_DIR%\ai-chat\database.db"
    set "FILE_BASE_DIR=%ICUBE_MODULAR_DATA_DIR%\ai-chat\snapshot"

    REM set default value
    if not defined CKG_APP_ID (
        set "CKG_APP_ID=6eefa01c-1036-4c7e-9ca5-d891f63bfcd8"
    )
    if not defined CKG_SOURCE_PRODUCT (
        set "CKG_SOURCE_PRODUCT=native_ide"
    )

    REM 如果设置了 PLUGIN_IDE_TYPE，添加 --ideType 参数
    set "IDE_TYPE_ARG="
    if defined PLUGIN_IDE_TYPE (
        set "IDE_TYPE_ARG=--ideType=%PLUGIN_IDE_TYPE%"
    )

    .\binary\ckg_server_windows_x64.exe -port=%PORT0% -ide_version=%ICUBE_BUILD_VERSION% -version_code=2 -storage_path="%ICUBE_MODULAR_DATA_DIR%\ckg_server" -local_embedding -embedding_storage_type=sqlite_vec -app_id=%CKG_APP_ID% -limit_cpu=1 -source_product=%CKG_SOURCE_PRODUCT% %IDE_TYPE_ARG%
)
