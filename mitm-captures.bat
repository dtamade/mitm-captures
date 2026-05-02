@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "COMMAND=%~1"
if "%COMMAND%"=="" goto :usage
shift /1

set "TARGET_DIR=%cd%"
set "LISTEN_HOST=127.0.0.1"
set "LISTEN_PORT=18080"
set "PROGRAM_MODE=0"
set "FORCE_RECOVER=0"
set "KEEP_ENV=0"
set "NO_HAR=0"
set "HAR_BACKEND=auto"
set "PRINT_STDOUT=0"
set "PYTHON_CMD="
set "MITMDUMP_CMD="
set "WINHTTP_SNAPSHOT_STATUS=not-requested"

call :parse_args %1 %2 %3 %4 %5 %6 %7 %8 %9
if not defined ARG_ERROR if /i not "%HAR_BACKEND%"=="auto" if /i not "%HAR_BACKEND%"=="mitmdump" if /i not "%HAR_BACKEND%"=="python" (
    set "ARG_ERROR=Invalid --har-backend: %HAR_BACKEND%"
)
if defined ARG_ERROR (
    >&2 echo [ERROR] %ARG_ERROR%
    exit /b 1
)

set "CAPTURES_DIR=%TARGET_DIR%\captures"
set "ENV_FILE=%CAPTURES_DIR%\proxy_info.env"
set "LATEST_FLOW_FILE=%CAPTURES_DIR%\latest.flow"
set "LATEST_HAR_FILE=%CAPTURES_DIR%\latest.har"
set "LATEST_LOG_FILE=%CAPTURES_DIR%\latest.log"
set "LATEST_MANIFEST_FILE=%CAPTURES_DIR%\latest.manifest.json"
set "LATEST_INDEX_FILE=%CAPTURES_DIR%\latest.index.ndjson"
set "LATEST_SUMMARY_FILE=%CAPTURES_DIR%\latest.summary.md"
set "LATEST_AI_JSON_FILE=%CAPTURES_DIR%\latest.ai.json"
set "LATEST_AI_MD_FILE=%CAPTURES_DIR%\latest.ai.md"
set "LATEST_AI_BUNDLE_FILE=%CAPTURES_DIR%\latest.ai.bundle.txt"
set "CAPTURE_LOCK_DIR=%CAPTURES_DIR%\.capture.lock"
set "CAPTURE_LOCK_OWNER_FILE=%CAPTURE_LOCK_DIR%\.owner.pid"
set "START_LATEST_FLOW_BACKUP_FILE="
set "START_LATEST_HAR_BACKUP_FILE="
set "START_LATEST_LOG_BACKUP_FILE="
set "START_LATEST_INDEX_BACKUP_FILE="
set "START_LATEST_SUMMARY_BACKUP_FILE="
set "START_LATEST_AI_JSON_BACKUP_FILE="
set "START_LATEST_AI_MD_BACKUP_FILE="
set "START_LATEST_AI_BUNDLE_BACKUP_FILE="

if /i "%COMMAND%"=="install" goto :dispatch_install
if /i "%COMMAND%"=="start" goto :dispatch_start
if /i "%COMMAND%"=="stop" goto :dispatch_stop
if /i "%COMMAND%"=="status" goto :dispatch_status
if /i "%COMMAND%"=="ai" goto :dispatch_ai
if /i "%COMMAND%"=="cert" goto :dispatch_cert

goto :usage

:dispatch_install
call :validate_target_dir || exit /b 1
goto :cmd_install

:dispatch_start
call :validate_target_dir || exit /b 1
call :validate_start_args || exit /b 1
call :run_with_capture_lock cmd_start
exit /b

:dispatch_stop
call :validate_target_dir || exit /b 1
call :run_with_capture_lock cmd_stop
exit /b

:dispatch_status
call :validate_target_dir || exit /b 1
call :run_with_capture_lock cmd_status
exit /b

:dispatch_ai
call :validate_target_dir || exit /b 1
call :run_with_capture_lock cmd_ai
exit /b

:dispatch_cert
goto :cmd_cert

:usage
echo Usage:
echo   mitm-captures.bat ^<install^|start^|stop^|status^|ai^|cert^> [options]
echo.
echo Common options:
echo   --dir ^<path^>          Target project directory ^(default: current directory^)
echo   --host ^<host^>         Listen host for start ^(default: 127.0.0.1^)
echo   --port ^<port^>         Listen port for start ^(default: 18080^)
echo   --program              Program mode; do not touch Windows proxy
echo   --force-recover        Remove stale proxy_info.env before start
echo   --keep-env             Keep proxy_info.env after stop
echo   --no-har               Skip HAR generation on stop
echo   --har-backend ^<name^>  HAR backend: auto^|mitmdump^|python
echo   --stdout               Print the AI bundle after ai
echo.
echo Examples:
echo   mitm-captures.bat install
echo   mitm-captures.bat start --dir C:\work\demo
echo   mitm-captures.bat stop --dir C:\work\demo
echo   mitm-captures.bat status --dir C:\work\demo
echo   mitm-captures.bat ai --dir C:\work\demo --stdout
echo   mitm-captures.bat cert
exit /b 1

:parse_args
if "%~1"=="" exit /b 0
if /i "%~1"=="--dir" (
    if "%~2"=="" (
        set "ARG_ERROR=Option --dir requires a value"
        exit /b 0
    )
    set "TARGET_DIR=%~2"
    shift /1
    shift /1
    goto :parse_args
)
if /i "%~1"=="--host" (
    if "%~2"=="" (
        set "ARG_ERROR=Option --host requires a value"
        exit /b 0
    )
    set "LISTEN_HOST=%~2"
    shift /1
    shift /1
    goto :parse_args
)
if /i "%~1"=="--port" (
    if "%~2"=="" (
        set "ARG_ERROR=Option --port requires a value"
        exit /b 0
    )
    set "LISTEN_PORT=%~2"
    shift /1
    shift /1
    goto :parse_args
)
if /i "%~1"=="--program" (
    set "PROGRAM_MODE=1"
    shift /1
    goto :parse_args
)
if /i "%~1"=="--force-recover" (
    set "FORCE_RECOVER=1"
    shift /1
    goto :parse_args
)
if /i "%~1"=="--keep-env" (
    set "KEEP_ENV=1"
    shift /1
    goto :parse_args
)
if /i "%~1"=="--no-har" (
    set "NO_HAR=1"
    shift /1
    goto :parse_args
)
if /i "%~1"=="--har-backend" (
    if "%~2"=="" (
        set "ARG_ERROR=Option --har-backend requires a value"
        exit /b 0
    )
    set "HAR_BACKEND=%~2"
    shift /1
    shift /1
    goto :parse_args
)
if /i "%~1"=="--stdout" (
    set "PRINT_STDOUT=1"
    shift /1
    goto :parse_args
)
set "ARG_ERROR=Unknown option: %~1"
exit /b 0

:cmd_install
call :ensure_captures_dir
call :ensure_deps || exit /b 1
echo [OK] Windows capture dependencies are installed or already available.
exit /b 0

:cmd_start
call :ensure_captures_dir
call :ensure_deps || exit /b 1

if exist "%ENV_FILE%" call :handle_existing_state_before_start || exit /b 1

call :new_run_id
set "FLOW_FILE=%BASE_NO_EXT%.flow"
set "HAR_FILE=%BASE_NO_EXT%.har"
set "LOG_FILE=%BASE_NO_EXT%.log"
set "MANIFEST_FILE=%BASE_NO_EXT%.manifest.json"
set "INDEX_FILE=%BASE_NO_EXT%.index.ndjson"
set "SUMMARY_FILE=%BASE_NO_EXT%.summary.md"
set "AI_JSON_FILE=%BASE_NO_EXT%.ai.json"
set "AI_MD_FILE=%BASE_NO_EXT%.ai.md"
set "BUNDLE_FILE=%BASE_NO_EXT%.ai.bundle.txt"
set "WINHTTP_DUMP_FILE=%BASE_NO_EXT%.winhttp.dump.txt"
set "START_LATEST_FLOW_BACKUP_FILE=%BASE_NO_EXT%.start-latest.flow.bak"
set "START_LATEST_HAR_BACKUP_FILE=%BASE_NO_EXT%.start-latest.har.bak"
set "START_LATEST_LOG_BACKUP_FILE=%BASE_NO_EXT%.start-latest.log.bak"
set "START_LATEST_INDEX_BACKUP_FILE=%BASE_NO_EXT%.start-latest.index.ndjson.bak"
set "START_LATEST_SUMMARY_BACKUP_FILE=%BASE_NO_EXT%.start-latest.summary.md.bak"
set "START_LATEST_AI_JSON_BACKUP_FILE=%BASE_NO_EXT%.start-latest.ai.json.bak"
set "START_LATEST_AI_MD_BACKUP_FILE=%BASE_NO_EXT%.start-latest.ai.md.bak"
set "START_LATEST_AI_BUNDLE_BACKUP_FILE=%BASE_NO_EXT%.start-latest.ai.bundle.txt.bak"

call :now_iso STARTED_AT
set "PREV_PROXY_ENABLE=__UNSET__"
set "PREV_PROXY_SERVER=__UNSET__"
set "PREV_PROXY_OVERRIDE=__UNSET__"
set "WINHTTP_SNAPSHOT_STATUS=not-requested"
set "MITM_PID="

if not "%PROGRAM_MODE%"=="1" (
    call :save_windows_proxy_state || (
        >&2 echo [ERROR] Failed to snapshot current WinHTTP proxy; aborting before changing Windows proxy.
        exit /b 1
    )
)

for /f %%I in ('powershell -NoProfile -Command "$p = Start-Process -FilePath $env:MITMDUMP_CMD -ArgumentList @(''-q'', ''--listen-host'', $env:LISTEN_HOST, ''--listen-port'', $env:LISTEN_PORT, ''--set'', ''block_global=false'', ''--set'', ''flow_detail=0'', ''-w'', $env:FLOW_FILE) -RedirectStandardOutput $env:LOG_FILE -RedirectStandardError $env:LOG_FILE -PassThru; $p.Id"') do set "MITM_PID=%%I"

if not defined MITM_PID (
    >&2 echo [ERROR] Failed to start mitmdump.
    exit /b 1
)

call :wait_for_startup_stability
if errorlevel 1 (
    >&2 echo [ERROR] mitmdump exited during startup.
    if exist "%LOG_FILE%" type "%LOG_FILE%"
    exit /b 1
)

call :write_state || call :rollback_failed_start "state-write-failed"
if errorlevel 1 exit /b 1
call :write_manifest || call :rollback_failed_start "manifest-write-failed"
if errorlevel 1 exit /b 1

if not "%PROGRAM_MODE%"=="1" (
    call :set_windows_proxy "%LISTEN_HOST%" "%LISTEN_PORT%" || call :rollback_failed_start "windows-proxy-set-failed"
)
if errorlevel 1 exit /b 1
set "LATEST_STATUS=ok"
call :stage_start_latest_outputs
if not "%LATEST_STATUS%"=="ok" call :rollback_failed_start "latest-stage-failed"
if errorlevel 1 exit /b 1
call :clear_start_latest_outputs
if not "%LATEST_STATUS%"=="ok" call :rollback_failed_start "latest-clear-failed"
if errorlevel 1 exit /b 1
call :copy_latest "%MANIFEST_FILE%" "%LATEST_MANIFEST_FILE%" || call :rollback_failed_start "latest-manifest-write-failed"
if errorlevel 1 exit /b 1
call :cleanup_start_latest_backups >nul 2>&1

echo ================================================================
echo  mitmproxy capture started
echo ================================================================
echo  PID:            %MITM_PID%
echo  Listen:         %LISTEN_HOST%:%LISTEN_PORT%
echo  Flow file:      %FLOW_FILE%
echo  Log file:       %LOG_FILE%
echo  Manifest file:  %MANIFEST_FILE%
if "%PROGRAM_MODE%"=="1" (
    echo  Proxy mode:    program ^(system proxy unchanged^)
) else (
    echo  Proxy mode:    Windows proxy -> manual %LISTEN_HOST%:%LISTEN_PORT%
)
exit /b 0

:cmd_stop
call :ensure_captures_dir
if not exist "%ENV_FILE%" (
    echo [WARN] No active capture metadata found: %ENV_FILE%
    echo [WARN] Nothing to stop.
    exit /b 0
)

call :load_state || exit /b 1
call :validate_loaded_state || exit /b 1
if not "%PROGRAM_MODE%"=="1" call :validate_proxy_restore_state || exit /b 1

for %%I in ("%FLOW_FILE%") do set "BASE_NO_EXT=%%~dpnI"
if not defined HAR_FILE set "HAR_FILE=%BASE_NO_EXT%.har"
if not defined LOG_FILE set "LOG_FILE=%BASE_NO_EXT%.log"
if not defined MANIFEST_FILE set "MANIFEST_FILE=%BASE_NO_EXT%.manifest.json"
if not defined INDEX_FILE set "INDEX_FILE=%BASE_NO_EXT%.index.ndjson"
if not defined SUMMARY_FILE set "SUMMARY_FILE=%BASE_NO_EXT%.summary.md"
if not defined AI_JSON_FILE set "AI_JSON_FILE=%BASE_NO_EXT%.ai.json"
if not defined AI_MD_FILE set "AI_MD_FILE=%BASE_NO_EXT%.ai.md"
if not defined BUNDLE_FILE set "BUNDLE_FILE=%BASE_NO_EXT%.ai.bundle.txt"
if not defined WINHTTP_DUMP_FILE set "WINHTTP_DUMP_FILE=%BASE_NO_EXT%.winhttp.dump.txt"
if not defined WINHTTP_SNAPSHOT_STATUS set "WINHTTP_SNAPSHOT_STATUS=unknown"
if not defined CAPTURES_DIR set "CAPTURES_DIR=%TARGET_DIR%\captures"

set "STOP_STATUS=not-running"
set "PROXY_STATUS=skipped"
set "HAR_STATUS=skipped"
set "REPORT_STATUS=skipped"
set "AI_BRIEF_STATUS=skipped"
set "AI_BUNDLE_STATUS=skipped"
set "MANIFEST_STATUS=skipped"
set "LATEST_STATUS=ok"

if defined MITM_PID (
    call :capture_pid_matches_state "%MITM_PID%" "%FLOW_FILE%"
    if errorlevel 2 (
        if "%FORCE_RECOVER%"=="1" (
            set "STOP_STATUS=already-exited"
        ) else (
            >&2 echo [ERROR] Active PID no longer matches capture state: %MITM_PID%
            exit /b 1
        )
    ) else (
        if errorlevel 1 (
            set "STOP_STATUS=already-exited"
        ) else (
            taskkill /pid %MITM_PID% /t /f >nul 2>&1
            if errorlevel 1 (
                set "STOP_STATUS=kill-failed"
            ) else (
                set "STOP_STATUS=ok"
            )
        )
    )
)
if not "%PROGRAM_MODE%"=="1" (
    call :restore_windows_proxy
    if errorlevel 1 (
        set "PROXY_STATUS=restore-failed"
    ) else (
        set "PROXY_STATUS=ok"
    )
)

call :resolve_mitmdump_cmd >nul 2>&1
if errorlevel 1 set "MITMDUMP_CMD="
call :resolve_mitmproxy_python_cmd >nul 2>&1
if errorlevel 1 set "PYTHON_CMD="

if "%STOP_STATUS%"=="kill-failed" set "HAR_STATUS=blocked-by-active-capture"
if "%STOP_STATUS%"=="kill-failed" set "REPORT_STATUS=blocked-by-active-capture"
if "%STOP_STATUS%"=="kill-failed" set "AI_BRIEF_STATUS=blocked-by-active-capture"
if "%STOP_STATUS%"=="kill-failed" set "AI_BUNDLE_STATUS=blocked-by-active-capture"
if /i "%STOP_STATUS%"=="kill-failed" (
    call :write_manifest
    if errorlevel 1 (
        set "MANIFEST_STATUS=failed"
    ) else (
        set "MANIFEST_STATUS=ok"
    )
)
if /i not "%STOP_STATUS%"=="kill-failed" (
    if "%NO_HAR%"=="1" (
        set "HAR_STATUS=skipped"
    )
    if not "%NO_HAR%"=="1" (
        call :generate_har
    )

    if exist "%FLOW_FILE%" (
        if not defined PYTHON_CMD (
            set "REPORT_STATUS=failed"
        ) else (
            "%PYTHON_CMD%" "%SCRIPT_DIR%\flow_report.py" "%FLOW_FILE%" "%INDEX_FILE%" "%SUMMARY_FILE%"
            if errorlevel 1 (
                set "REPORT_STATUS=failed"
            ) else (
                set "REPORT_STATUS=ok"
            )
        )
    )

    call :write_manifest
    if errorlevel 1 (
        set "MANIFEST_STATUS=failed"
    ) else (
        set "MANIFEST_STATUS=ok"
    )

    if not "%MANIFEST_STATUS%"=="failed" if exist "%INDEX_FILE%" (
        if not defined PYTHON_CMD (
            set "AI_BRIEF_STATUS=failed"
        ) else (
            "%PYTHON_CMD%" "%SCRIPT_DIR%\ai_brief.py" "%MANIFEST_FILE%" "%INDEX_FILE%" "%AI_JSON_FILE%" "%AI_MD_FILE%"
            if errorlevel 1 (
                set "AI_BRIEF_STATUS=failed"
            ) else (
                set "AI_BRIEF_STATUS=ok"
            )
        )
    )

    call :build_ai_bundle
    call :write_manifest
    if errorlevel 1 (
        set "MANIFEST_STATUS=failed"
    ) else (
        set "MANIFEST_STATUS=ok"
    )

    if "%MANIFEST_STATUS%"=="failed" set "LATEST_STATUS=failed"
    if "%LATEST_STATUS%"=="ok" call :clear_latest_outputs
    if "%LATEST_STATUS%"=="ok" (
        call :copy_latest_checked "%FLOW_FILE%" "%LATEST_FLOW_FILE%"
        call :copy_latest_checked "%HAR_FILE%" "%LATEST_HAR_FILE%"
        call :copy_latest_checked "%LOG_FILE%" "%LATEST_LOG_FILE%"
        if not "%MANIFEST_STATUS%"=="failed" call :copy_latest_checked "%MANIFEST_FILE%" "%LATEST_MANIFEST_FILE%"
        call :copy_latest_checked "%INDEX_FILE%" "%LATEST_INDEX_FILE%"
        call :copy_latest_checked "%SUMMARY_FILE%" "%LATEST_SUMMARY_FILE%"
        call :copy_latest_checked "%AI_JSON_FILE%" "%LATEST_AI_JSON_FILE%"
        call :copy_latest_checked "%AI_MD_FILE%" "%LATEST_AI_MD_FILE%"
        call :copy_latest_checked "%BUNDLE_FILE%" "%LATEST_AI_BUNDLE_FILE%"
    )
    if not "%LATEST_STATUS%"=="ok" call :clear_latest_outputs
)

echo ================================================================
echo  mitmproxy capture stopped
echo ================================================================
echo  Flow file:        %FLOW_FILE%
echo  HAR file:         %HAR_FILE%
echo  Manifest file:    %MANIFEST_FILE%
echo  Index file:       %INDEX_FILE%
echo  Summary file:     %SUMMARY_FILE%
echo  AI JSON file:     %AI_JSON_FILE%
echo  AI brief file:    %AI_MD_FILE%
echo  AI bundle file:   %BUNDLE_FILE%
echo  Latest flow:      %LATEST_FLOW_FILE%
echo  Latest summary:   %LATEST_SUMMARY_FILE%
echo  Latest AI brief:  %LATEST_AI_MD_FILE%
if not "%PROGRAM_MODE%"=="1" echo  Proxy restore:    %PROXY_STATUS%

set "STOP_EXIT_CODE=0"
if "%STOP_STATUS%"=="kill-failed" set "STOP_EXIT_CODE=2"
if "%PROXY_STATUS%"=="restore-failed" set "STOP_EXIT_CODE=2"
if "%HAR_STATUS%"=="failed" set "STOP_EXIT_CODE=2"
if "%REPORT_STATUS%"=="failed" set "STOP_EXIT_CODE=2"
if "%AI_BRIEF_STATUS%"=="failed" set "STOP_EXIT_CODE=2"
if "%AI_BUNDLE_STATUS%"=="failed" set "STOP_EXIT_CODE=2"
if "%MANIFEST_STATUS%"=="failed" set "STOP_EXIT_CODE=2"
if "%LATEST_STATUS%"=="failed" set "STOP_EXIT_CODE=2"
if not "%KEEP_ENV%"=="1" if "%STOP_EXIT_CODE%"=="0" del /q "%ENV_FILE%" >nul 2>&1
if not "%KEEP_ENV%"=="1" if not "%STOP_EXIT_CODE%"=="0" >&2 echo [WARN] Stop finished with errors; preserving state file for retry: %ENV_FILE%
exit /b %STOP_EXIT_CODE%

:cmd_status
call :ensure_captures_dir
if not exist "%ENV_FILE%" (
    echo No active capture metadata: %ENV_FILE%
    if exist "%LATEST_MANIFEST_FILE%" echo Latest manifest: %LATEST_MANIFEST_FILE%
    if exist "%LATEST_SUMMARY_FILE%" echo Latest summary:  %LATEST_SUMMARY_FILE%
    exit /b 0
)

call :load_state || exit /b 1
call :validate_loaded_state || exit /b 1
set "RUNNING=no"
if defined MITM_PID (
    call :capture_pid_matches_state "%MITM_PID%" "%FLOW_FILE%"
    if errorlevel 2 (
        >&2 echo [ERROR] Active PID no longer matches capture state: %MITM_PID%
        exit /b 1
    )
    if not errorlevel 1 set "RUNNING=yes"
)

echo ================================================================
echo  mitmproxy capture status
echo ================================================================
echo  Running:         %RUNNING%
echo  PID:             %MITM_PID%
echo  Listen:          %LISTEN_HOST%:%LISTEN_PORT%
echo  Program mode:    %PROGRAM_MODE%
echo  Started at:      %STARTED_AT%
echo  Flow file:       %FLOW_FILE%
echo  HAR file:        %HAR_FILE%
echo  State file:      %ENV_FILE%
echo  Latest flow:     %LATEST_FLOW_FILE%
echo  Latest summary:  %LATEST_SUMMARY_FILE%
echo  Latest AI brief: %LATEST_AI_MD_FILE%
exit /b 0

:cmd_ai
call :ensure_captures_dir
if not exist "%LATEST_AI_MD_FILE%" (
    >&2 echo [ERROR] Missing file: %LATEST_AI_MD_FILE%
    >&2 echo [ERROR] Run start then stop first to generate AI artifacts.
    exit /b 1
)
if not exist "%LATEST_AI_JSON_FILE%" (
    >&2 echo [ERROR] Missing file: %LATEST_AI_JSON_FILE%
    >&2 echo [ERROR] Run start then stop first to generate AI artifacts.
    exit /b 1
)

set "MANIFEST_FILE=%LATEST_MANIFEST_FILE%"
set "SUMMARY_FILE=%LATEST_SUMMARY_FILE%"
set "AI_MD_FILE=%LATEST_AI_MD_FILE%"
set "AI_JSON_FILE=%LATEST_AI_JSON_FILE%"
set "BUNDLE_FILE=%LATEST_AI_BUNDLE_FILE%"
call :build_ai_bundle
if errorlevel 1 exit /b 1

echo Bundle written: %LATEST_AI_BUNDLE_FILE%
if "%PRINT_STDOUT%"=="1" type "%LATEST_AI_BUNDLE_FILE%"
exit /b 0

:cmd_cert
call :ensure_deps || exit /b 1
set "MITM_CERT=%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer"
if not exist "%MITM_CERT%" call :bootstrap_cert_material || exit /b 1
if not exist "%MITM_CERT%" (
    >&2 echo [ERROR] mitmproxy certificate not found: %MITM_CERT%
    exit /b 1
)
certutil -user -addstore Root "%MITM_CERT%"
if errorlevel 1 exit /b 1
echo [OK] mitmproxy CA certificate installed for the current user.
exit /b 0

:run_with_capture_lock
call :ensure_captures_dir
call :acquire_capture_lock || exit /b 1
call :%~1
set "RUN_WITH_CAPTURE_LOCK_RC=%ERRORLEVEL%"
call :release_capture_lock >nul 2>&1
exit /b %RUN_WITH_CAPTURE_LOCK_RC%

:acquire_capture_lock
:acquire_capture_lock_retry
mkdir "%CAPTURE_LOCK_DIR%" >nul 2>&1
if not errorlevel 1 (
    call :write_capture_lock_owner || (
        call :release_capture_lock >nul 2>&1
        exit /b 1
    )
    exit /b 0
)
call :recover_stale_capture_lock
if not errorlevel 1 goto :acquire_capture_lock_retry
>&2 echo [ERROR] Another capture operation is running. Please retry.
exit /b 1

:recover_stale_capture_lock
if not exist "%CAPTURE_LOCK_OWNER_FILE%" (
    if "%FORCE_RECOVER%"=="1" (
        call :release_capture_lock >nul 2>&1
        if exist "%CAPTURE_LOCK_DIR%" exit /b 1
        exit /b 0
    )
    exit /b 1
)
call :read_capture_lock_owner_pid
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    call :read_capture_lock_owner_pid
)
call :resolve_current_cmd_pid CURRENT_CMD_PID
if defined CAPTURE_LOCK_OWNER_PID if defined CURRENT_CMD_PID if /I "%CAPTURE_LOCK_OWNER_PID%"=="%CURRENT_CMD_PID%" (
    call :release_capture_lock >nul 2>&1
    if exist "%CAPTURE_LOCK_DIR%" exit /b 1
    exit /b 0
)
if defined CAPTURE_LOCK_OWNER_PID (
    call :pid_running "%CAPTURE_LOCK_OWNER_PID%"
    if not errorlevel 1 exit /b 1
)
if not defined CAPTURE_LOCK_OWNER_PID if not "%FORCE_RECOVER%"=="1" exit /b 1
call :release_capture_lock >nul 2>&1
if exist "%CAPTURE_LOCK_DIR%" exit /b 1
exit /b 0

:read_capture_lock_owner_pid
set "CAPTURE_LOCK_OWNER_PID="
if not exist "%CAPTURE_LOCK_OWNER_FILE%" exit /b 1
set /p CAPTURE_LOCK_OWNER_PID=<"%CAPTURE_LOCK_OWNER_FILE%"
if not defined CAPTURE_LOCK_OWNER_PID exit /b 1
echo(%CAPTURE_LOCK_OWNER_PID%| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 (
    set "CAPTURE_LOCK_OWNER_PID="
    exit /b 1
)
exit /b 0

:write_capture_lock_owner
call :resolve_current_cmd_pid CAPTURE_LOCK_OWNER_PID
if errorlevel 1 exit /b 1
>"%CAPTURE_LOCK_OWNER_FILE%" echo %CAPTURE_LOCK_OWNER_PID%
if errorlevel 1 exit /b 1
if not exist "%CAPTURE_LOCK_OWNER_FILE%" exit /b 1
exit /b 0

:resolve_current_cmd_pid
set "CURRENT_CMD_PID="
for /f %%I in ('powershell -NoProfile -Command "$owner = (Get-CimInstance Win32_Process -Filter ('ProcessId=' + $PID)).ParentProcessId; if ($owner) { $owner }" 2^>nul') do set "CURRENT_CMD_PID=%%I"
if not defined CURRENT_CMD_PID exit /b 1
set "%~1=%CURRENT_CMD_PID%"
exit /b 0

:release_capture_lock
if exist "%CAPTURE_LOCK_OWNER_FILE%" del /q "%CAPTURE_LOCK_OWNER_FILE%" >nul 2>&1
if exist "%CAPTURE_LOCK_DIR%" rd "%CAPTURE_LOCK_DIR%" >nul 2>&1
exit /b 0

:validate_target_dir
powershell -NoProfile -Command "if (Test-Path -LiteralPath $env:TARGET_DIR -PathType Container) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    >&2 echo [ERROR] Target directory does not exist: %TARGET_DIR%
    exit /b 1
)
exit /b 0

:validate_start_args
if "%LISTEN_HOST%"=="" (
    >&2 echo [ERROR] Listen host cannot be empty
    exit /b 1
)
echo(%LISTEN_PORT%| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 (
    >&2 echo [ERROR] Invalid port: %LISTEN_PORT%
    exit /b 1
)
if %LISTEN_PORT% lss 1 (
    >&2 echo [ERROR] Invalid port: %LISTEN_PORT%
    exit /b 1
)
if %LISTEN_PORT% gtr 65535 (
    >&2 echo [ERROR] Invalid port: %LISTEN_PORT%
    exit /b 1
)
exit /b 0

:ensure_deps
call :resolve_python_cmd
if errorlevel 1 (
    where winget >nul 2>&1
    if errorlevel 1 (
        >&2 echo [ERROR] Python is missing and winget is unavailable.
        exit /b 1
    )
    winget install -e --id Python.Python.3 --accept-package-agreements --accept-source-agreements
    if errorlevel 1 exit /b 1
    call :resolve_python_cmd
    if errorlevel 1 (
        >&2 echo [ERROR] Python installed but could not be resolved in the current shell.
        exit /b 1
    )
)

call :resolve_mitmdump_cmd
if not errorlevel 1 exit /b 0

where winget >nul 2>&1
if not errorlevel 1 (
    winget install -e --id mitmproxy.mitmproxy --accept-package-agreements --accept-source-agreements
    if not errorlevel 1 (
        call :resolve_mitmdump_cmd
        if not errorlevel 1 exit /b 0
    )
)

"%PYTHON_CMD%" -m pip install --user mitmproxy
if errorlevel 1 exit /b 1
call :resolve_mitmdump_cmd
if errorlevel 1 (
    >&2 echo [ERROR] mitmdump installed but could not be resolved in the current shell.
    exit /b 1
)
exit /b 0

:resolve_python_cmd
set "PYTHON_CMD="
for /f "delims=" %%I in ('where python 2^>nul') do (
    if not defined PYTHON_CMD (
        call :validate_python_cmd "%%I"
        if not errorlevel 1 set "PYTHON_CMD=%%I"
    )
)
if defined PYTHON_CMD exit /b 0
for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
    if not defined PYTHON_CMD (
        call :validate_python_cmd "%%I"
        if not errorlevel 1 set "PYTHON_CMD=%%I"
    )
)
if defined PYTHON_CMD exit /b 0
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Item @(($env:LOCALAPPDATA + '\Programs\Python\Python*\python.exe'), ($env:LOCALAPPDATA + '\Microsoft\WindowsApps\python.exe'), (${env:ProgramFiles} + '\Python*\python.exe'), (${env:ProgramFiles(x86)} + '\Python*\python.exe')) -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }"') do (
    if not defined PYTHON_CMD (
        call :validate_python_cmd "%%I"
        if not errorlevel 1 set "PYTHON_CMD=%%I"
    )
)
if defined PYTHON_CMD exit /b 0
exit /b 1

:resolve_mitmproxy_python_cmd
set "PYTHON_CMD="
if defined MITMDUMP_CMD (
    call :python_cmd_from_mitmdump "%MITMDUMP_CMD%"
    if defined PYTHON_CMD exit /b 0
)
for /f "delims=" %%I in ('where python 2^>nul') do (
    if not defined PYTHON_CMD (
        call :validate_python_with_mitmproxy_cmd "%%I"
        if not errorlevel 1 set "PYTHON_CMD=%%I"
    )
)
if defined PYTHON_CMD exit /b 0
for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
    if not defined PYTHON_CMD (
        call :validate_python_with_mitmproxy_cmd "%%I"
        if not errorlevel 1 set "PYTHON_CMD=%%I"
    )
)
if defined PYTHON_CMD exit /b 0
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Item @(($env:LOCALAPPDATA + '\Programs\Python\Python*\python.exe'), ($env:LOCALAPPDATA + '\Microsoft\WindowsApps\python.exe'), (${env:ProgramFiles} + '\Python*\python.exe'), (${env:ProgramFiles(x86)} + '\Python*\python.exe')) -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }"') do (
    if not defined PYTHON_CMD (
        call :validate_python_with_mitmproxy_cmd "%%I"
        if not errorlevel 1 set "PYTHON_CMD=%%I"
    )
)
if defined PYTHON_CMD exit /b 0
exit /b 1

:python_cmd_from_mitmdump
set "MITMDUMP_PYTHON_CANDIDATE="
for %%I in ("%~1") do (
    if exist "%%~dpI..\python.exe" set "MITMDUMP_PYTHON_CANDIDATE=%%~dpI..\python.exe"
)
if not defined MITMDUMP_PYTHON_CANDIDATE exit /b 1
call :validate_python_with_mitmproxy_cmd "%MITMDUMP_PYTHON_CANDIDATE%"
if errorlevel 1 exit /b 1
set "PYTHON_CMD=%MITMDUMP_PYTHON_CANDIDATE%"
exit /b 0

:resolve_mitmdump_cmd
set "MITMDUMP_CMD="
for /f "delims=" %%I in ('where mitmdump 2^>nul') do (
    if not defined MITMDUMP_CMD (
        call :validate_mitmdump_cmd "%%I"
        if not errorlevel 1 set "MITMDUMP_CMD=%%I"
    )
)
if defined MITMDUMP_CMD exit /b 0
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Item @(($env:LOCALAPPDATA + '\Microsoft\WinGet\Links\mitmdump.exe'), ($env:LOCALAPPDATA + '\Microsoft\WindowsApps\mitmdump.exe'), ($env:LOCALAPPDATA + '\Programs\Python\Python*\Scripts\mitmdump.exe'), ($env:APPDATA + '\Python\Python*\Scripts\mitmdump.exe')) -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }"') do (
    if not defined MITMDUMP_CMD (
        call :validate_mitmdump_cmd "%%I"
        if not errorlevel 1 set "MITMDUMP_CMD=%%I"
    )
)
if defined MITMDUMP_CMD exit /b 0
exit /b 1

:validate_mitmdump_cmd
set "MITMDUMP_VALIDATE_CMD=%~1"
set "MITMDUMP_VALIDATE_NAME="
for %%J in ("%MITMDUMP_VALIDATE_CMD%") do set "MITMDUMP_VALIDATE_NAME=%%~nxJ"
if /I not "%MITMDUMP_VALIDATE_NAME%"=="mitmdump.exe" exit /b 1
set "MITMDUMP_VALIDATE_OUT=%TEMP%\mitm-captures-mitmdump-validate-%RANDOM%%RANDOM%.txt"
set "MITMDUMP_VALIDATE_RESULT="
"%MITMDUMP_VALIDATE_CMD%" --version > "%MITMDUMP_VALIDATE_OUT%" 2>nul
if errorlevel 1 (
    del /q "%MITMDUMP_VALIDATE_OUT%" >nul 2>&1
    exit /b 1
)
set /p MITMDUMP_VALIDATE_RESULT=<"%MITMDUMP_VALIDATE_OUT%"
del /q "%MITMDUMP_VALIDATE_OUT%" >nul 2>&1
if not defined MITMDUMP_VALIDATE_RESULT exit /b 1
exit /b 0

:validate_python_cmd
set "PYTHON_VALIDATE_CMD=%~1"
set "PYTHON_VALIDATE_OUT=%TEMP%\mitm-captures-python-validate-%RANDOM%%RANDOM%.txt"
set "PYTHON_VALIDATE_RESULT="
"%PYTHON_VALIDATE_CMD%" -c "import sys; print(sys.executable)" > "%PYTHON_VALIDATE_OUT%" 2>nul
if errorlevel 1 (
    del /q "%PYTHON_VALIDATE_OUT%" >nul 2>&1
    exit /b 1
)
set /p PYTHON_VALIDATE_RESULT=<"%PYTHON_VALIDATE_OUT%"
del /q "%PYTHON_VALIDATE_OUT%" >nul 2>&1
if not defined PYTHON_VALIDATE_RESULT exit /b 1
echo(%PYTHON_VALIDATE_RESULT%| findstr /I /C:"\Microsoft\WindowsApps\python.exe" >nul
if not errorlevel 1 exit /b 1
exit /b 0

:validate_python_with_mitmproxy_cmd
set "PYTHON_VALIDATE_CMD=%~1"
set "PYTHON_VALIDATE_OUT=%TEMP%\mitm-captures-python-mitmproxy-validate-%RANDOM%%RANDOM%.txt"
set "PYTHON_VALIDATE_RESULT="
"%PYTHON_VALIDATE_CMD%" -c "import mitmproxy, sys; print(sys.executable)" > "%PYTHON_VALIDATE_OUT%" 2>nul
if errorlevel 1 (
    del /q "%PYTHON_VALIDATE_OUT%" >nul 2>&1
    exit /b 1
)
set /p PYTHON_VALIDATE_RESULT=<"%PYTHON_VALIDATE_OUT%"
del /q "%PYTHON_VALIDATE_OUT%" >nul 2>&1
if not defined PYTHON_VALIDATE_RESULT exit /b 1
echo(%PYTHON_VALIDATE_RESULT%| findstr /I /C:"\Microsoft\WindowsApps\python.exe" >nul
if not errorlevel 1 exit /b 1
exit /b 0

:ensure_captures_dir
if not exist "%CAPTURES_DIR%" mkdir "%CAPTURES_DIR%"
exit /b 0

:new_run_id
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd_HHmmss')"') do set "STAMP=%%I"
set "RUN_ID=capture_%STAMP%_%RANDOM%"
set "BASE_NO_EXT=%CAPTURES_DIR%\%RUN_ID%"
exit /b 0

:now_iso
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')"') do set "%~1=%%I"
exit /b 0

:wait_for_startup_stability
set "STARTUP_WAIT_SECONDS=6"
:wait_for_startup_stability_loop
call :pid_running "%MITM_PID%"
if errorlevel 1 exit /b 1
if "%STARTUP_WAIT_SECONDS%"=="0" exit /b 0
timeout /t 1 /nobreak >nul
set /a STARTUP_WAIT_SECONDS-=1
goto :wait_for_startup_stability_loop

:handle_existing_state_before_start
call :load_state || exit /b 1
if defined MITM_PID (
    call :capture_pid_matches_state "%MITM_PID%" "%FLOW_FILE%"
    if errorlevel 2 (
        if "%FORCE_RECOVER%"=="1" (
            call :cleanup_start_latest_backups >nul 2>&1
            del /q "%ENV_FILE%" >nul 2>&1
            exit /b 0
        )
        >&2 echo [ERROR] Active PID no longer matches capture state: %MITM_PID%
        exit /b 1
    )
    if not errorlevel 1 (
        >&2 echo [ERROR] Active capture already exists: %ENV_FILE%
        >&2 echo [ERROR] Run mitm-captures.bat stop first.
        exit /b 1
    )
)
if "%FORCE_RECOVER%"=="1" (
    call :cleanup_start_latest_backups >nul 2>&1
    del /q "%ENV_FILE%" >nul 2>&1
    exit /b 0
)
>&2 echo [ERROR] Stale capture metadata found: %ENV_FILE%
>&2 echo [ERROR] Re-run with --force-recover to discard it.
exit /b 1

:load_state
call :reset_loaded_state_variables
set "STATE_IMPORT_FILE=%TEMP%\mitm-captures-state-%RANDOM%%RANDOM%.cmd"
powershell -NoProfile -Command "$allowedStateKeys = @{ 'MITM_PID' = $true; 'PROGRAM_MODE' = $true; 'TARGET_DIR' = $true; 'CAPTURES_DIR' = $true; 'RUN_ID' = $true; 'FLOW_FILE' = $true; 'HAR_FILE' = $true; 'LOG_FILE' = $true; 'MANIFEST_FILE' = $true; 'INDEX_FILE' = $true; 'SUMMARY_FILE' = $true; 'AI_JSON_FILE' = $true; 'AI_MD_FILE' = $true; 'BUNDLE_FILE' = $true; 'LISTEN_HOST' = $true; 'LISTEN_PORT' = $true; 'STARTED_AT' = $true; 'PREV_PROXY_ENABLE' = $true; 'PREV_PROXY_SERVER' = $true; 'PREV_PROXY_OVERRIDE' = $true; 'WINHTTP_DUMP_FILE' = $true; 'WINHTTP_SNAPSHOT_STATUS' = $true; 'START_LATEST_FLOW_BACKUP_FILE' = $true; 'START_LATEST_HAR_BACKUP_FILE' = $true; 'START_LATEST_LOG_BACKUP_FILE' = $true; 'START_LATEST_INDEX_BACKUP_FILE' = $true; 'START_LATEST_SUMMARY_BACKUP_FILE' = $true; 'START_LATEST_AI_JSON_BACKUP_FILE' = $true; 'START_LATEST_AI_MD_BACKUP_FILE' = $true; 'START_LATEST_AI_BUNDLE_BACKUP_FILE' = $true }; $cmdLines = foreach ($line in Get-Content -LiteralPath $env:ENV_FILE) { if ($line -match '^(?<k>[^=]+)=(?<v>.*)$') { $key = $Matches.k; if (-not $allowedStateKeys.ContainsKey($key)) { throw ('Unexpected state key: ' + $key) }; $value = $Matches.v.Replace('%', '%%'); 'set ""{0}={1}""' -f $key, $value } }; Set-Content -Encoding OEM -LiteralPath $env:STATE_IMPORT_FILE $cmdLines"
if errorlevel 1 (
    del /q "%STATE_IMPORT_FILE%" >nul 2>&1
    exit /b 1
)
call "%STATE_IMPORT_FILE%"
set "LOAD_STATE_RC=%ERRORLEVEL%"
del /q "%STATE_IMPORT_FILE%" >nul 2>&1
set "STATE_IMPORT_FILE="
exit /b %LOAD_STATE_RC%

:reset_loaded_state_variables
set "MITM_PID="
set "PROGRAM_MODE="
set "TARGET_DIR="
set "CAPTURES_DIR="
set "RUN_ID="
set "FLOW_FILE="
set "HAR_FILE="
set "LOG_FILE="
set "MANIFEST_FILE="
set "INDEX_FILE="
set "SUMMARY_FILE="
set "AI_JSON_FILE="
set "AI_MD_FILE="
set "BUNDLE_FILE="
set "LISTEN_HOST="
set "LISTEN_PORT="
set "STARTED_AT="
set "PREV_PROXY_ENABLE="
set "PREV_PROXY_SERVER="
set "PREV_PROXY_OVERRIDE="
set "WINHTTP_DUMP_FILE="
set "WINHTTP_SNAPSHOT_STATUS="
set "START_LATEST_FLOW_BACKUP_FILE="
set "START_LATEST_HAR_BACKUP_FILE="
set "START_LATEST_LOG_BACKUP_FILE="
set "START_LATEST_INDEX_BACKUP_FILE="
set "START_LATEST_SUMMARY_BACKUP_FILE="
set "START_LATEST_AI_JSON_BACKUP_FILE="
set "START_LATEST_AI_MD_BACKUP_FILE="
set "START_LATEST_AI_BUNDLE_BACKUP_FILE="
exit /b 0

:validate_loaded_state
if not defined MITM_PID (
    >&2 echo [ERROR] Invalid state file: missing MITM_PID
    exit /b 1
)
echo(%MITM_PID%| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 (
    >&2 echo [ERROR] Invalid state file: invalid MITM_PID=%MITM_PID%
    exit /b 1
)
if not defined PROGRAM_MODE (
    >&2 echo [ERROR] Invalid state file: missing PROGRAM_MODE
    exit /b 1
)
if not "%PROGRAM_MODE%"=="0" if not "%PROGRAM_MODE%"=="1" (
    >&2 echo [ERROR] Invalid state file: unsupported PROGRAM_MODE=%PROGRAM_MODE%
    exit /b 1
)
if not defined FLOW_FILE (
    >&2 echo [ERROR] Invalid state file: missing FLOW_FILE
    exit /b 1
)
if not defined LISTEN_HOST (
    >&2 echo [ERROR] Invalid state file: missing LISTEN_HOST
    exit /b 1
)
if "%LISTEN_HOST%"=="" (
    >&2 echo [ERROR] Invalid state file: missing LISTEN_HOST
    exit /b 1
)
if not defined LISTEN_PORT (
    >&2 echo [ERROR] Invalid state file: missing LISTEN_PORT
    exit /b 1
)
echo(%LISTEN_PORT%| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 (
    >&2 echo [ERROR] Invalid state file: invalid LISTEN_PORT=%LISTEN_PORT%
    exit /b 1
)
if %LISTEN_PORT% lss 1 (
    >&2 echo [ERROR] Invalid state file: invalid LISTEN_PORT=%LISTEN_PORT%
    exit /b 1
)
if %LISTEN_PORT% gtr 65535 (
    >&2 echo [ERROR] Invalid state file: invalid LISTEN_PORT=%LISTEN_PORT%
    exit /b 1
)
exit /b 0

:validate_proxy_restore_state
if "%PROGRAM_MODE%"=="1" exit /b 0
if not defined PREV_PROXY_ENABLE (
    >&2 echo [ERROR] Invalid state file: missing PREV_PROXY_ENABLE
    exit /b 1
)
if /I not "%PREV_PROXY_ENABLE%"=="__UNSET__" (
    echo(%PREV_PROXY_ENABLE%| findstr /R /I /C:"^0x[01]$" /C:"^[01]$" >nul
    if errorlevel 1 (
        >&2 echo [ERROR] Invalid state file: invalid PREV_PROXY_ENABLE=%PREV_PROXY_ENABLE%
        exit /b 1
    )
)
if not defined PREV_PROXY_SERVER (
    >&2 echo [ERROR] Invalid state file: missing PREV_PROXY_SERVER
    exit /b 1
)
if not defined PREV_PROXY_OVERRIDE (
    >&2 echo [ERROR] Invalid state file: missing PREV_PROXY_OVERRIDE
    exit /b 1
)
if not defined WINHTTP_DUMP_FILE (
    >&2 echo [ERROR] Invalid state file: missing WINHTTP_DUMP_FILE
    exit /b 1
)
if /i not "%WINHTTP_SNAPSHOT_STATUS%"=="ok" (
    >&2 echo [ERROR] Invalid state file: missing WinHTTP proxy snapshot status
    exit /b 1
)
exit /b 0

:rollback_failed_start
set "ROLLBACK_REASON=%~1"
set "ROLLBACK_PROXY_STATUS=skipped"
set "ROLLBACK_LATEST_STATUS=skipped"
if not "%PROGRAM_MODE%"=="1" if /i "%WINHTTP_SNAPSHOT_STATUS%"=="ok" (
    call :restore_windows_proxy >nul 2>&1
    if errorlevel 1 (
        set "ROLLBACK_PROXY_STATUS=restore-failed"
    ) else (
        set "ROLLBACK_PROXY_STATUS=restore-ok"
    )
)
if defined MITM_PID taskkill /pid %MITM_PID% /t /f >nul 2>&1
call :restore_start_latest_outputs
if errorlevel 1 (
    set "ROLLBACK_LATEST_STATUS=restore-failed"
) else (
    set "ROLLBACK_LATEST_STATUS=restore-ok"
)
if /i not "%ROLLBACK_PROXY_STATUS%"=="restore-failed" if /i not "%ROLLBACK_LATEST_STATUS%"=="restore-failed" if exist "%ENV_FILE%" del /q "%ENV_FILE%" >nul 2>&1
if /i not "%ROLLBACK_PROXY_STATUS%"=="restore-failed" if /i not "%ROLLBACK_LATEST_STATUS%"=="restore-failed" if exist "%MANIFEST_FILE%" del /q "%MANIFEST_FILE%" >nul 2>&1
if /i "%ROLLBACK_PROXY_STATUS%"=="restore-failed" if /i "%ROLLBACK_LATEST_STATUS%"=="restore-failed" (
    >&2 echo [ERROR] Start failed during %ROLLBACK_REASON%; mitmdump rolled back but Windows proxy restore and latest artifact restore both failed. Session state was preserved for retry.
    exit /b 1
)
if /i "%ROLLBACK_PROXY_STATUS%"=="restore-failed" (
    >&2 echo [ERROR] Start failed during %ROLLBACK_REASON%; mitmdump rolled back but Windows proxy restore also failed. Session state was preserved for retry.
    exit /b 1
)
if /i "%ROLLBACK_LATEST_STATUS%"=="restore-failed" (
    >&2 echo [ERROR] Start failed during %ROLLBACK_REASON%; mitmdump rolled back but latest artifact restore also failed. Session state was preserved for retry.
    exit /b 1
)
>&2 echo [ERROR] Start failed during %ROLLBACK_REASON%; rolled back the spawned mitmdump process.
exit /b 1

:write_state
set "STATE_WRITE_TMP_FILE=%ENV_FILE%.tmp.%RANDOM%%RANDOM%"
powershell -NoProfile -Command "$pairs = [ordered]@{ MITM_PID=$env:MITM_PID; PROGRAM_MODE=$env:PROGRAM_MODE; TARGET_DIR=$env:TARGET_DIR; CAPTURES_DIR=$env:CAPTURES_DIR; RUN_ID=$env:RUN_ID; FLOW_FILE=$env:FLOW_FILE; HAR_FILE=$env:HAR_FILE; LOG_FILE=$env:LOG_FILE; MANIFEST_FILE=$env:MANIFEST_FILE; INDEX_FILE=$env:INDEX_FILE; SUMMARY_FILE=$env:SUMMARY_FILE; AI_JSON_FILE=$env:AI_JSON_FILE; AI_MD_FILE=$env:AI_MD_FILE; BUNDLE_FILE=$env:BUNDLE_FILE; LISTEN_HOST=$env:LISTEN_HOST; LISTEN_PORT=$env:LISTEN_PORT; STARTED_AT=$env:STARTED_AT; PREV_PROXY_ENABLE=$env:PREV_PROXY_ENABLE; PREV_PROXY_SERVER=$env:PREV_PROXY_SERVER; PREV_PROXY_OVERRIDE=$env:PREV_PROXY_OVERRIDE; WINHTTP_DUMP_FILE=$env:WINHTTP_DUMP_FILE; WINHTTP_SNAPSHOT_STATUS=$env:WINHTTP_SNAPSHOT_STATUS; START_LATEST_FLOW_BACKUP_FILE=$env:START_LATEST_FLOW_BACKUP_FILE; START_LATEST_HAR_BACKUP_FILE=$env:START_LATEST_HAR_BACKUP_FILE; START_LATEST_LOG_BACKUP_FILE=$env:START_LATEST_LOG_BACKUP_FILE; START_LATEST_INDEX_BACKUP_FILE=$env:START_LATEST_INDEX_BACKUP_FILE; START_LATEST_SUMMARY_BACKUP_FILE=$env:START_LATEST_SUMMARY_BACKUP_FILE; START_LATEST_AI_JSON_BACKUP_FILE=$env:START_LATEST_AI_JSON_BACKUP_FILE; START_LATEST_AI_MD_BACKUP_FILE=$env:START_LATEST_AI_MD_BACKUP_FILE; START_LATEST_AI_BUNDLE_BACKUP_FILE=$env:START_LATEST_AI_BUNDLE_BACKUP_FILE }; $lines = foreach ($pair in $pairs.GetEnumerator()) { '{0}={1}' -f $pair.Key, [string]$pair.Value }; Set-Content -Encoding UTF8 -LiteralPath $env:STATE_WRITE_TMP_FILE $lines"
if errorlevel 1 (
    if exist "%STATE_WRITE_TMP_FILE%" del /q "%STATE_WRITE_TMP_FILE%" >nul 2>&1
    exit /b 1
)
move /y "%STATE_WRITE_TMP_FILE%" "%ENV_FILE%" >nul
if errorlevel 1 (
    if exist "%STATE_WRITE_TMP_FILE%" del /q "%STATE_WRITE_TMP_FILE%" >nul 2>&1
    exit /b 1
)
if exist "%STATE_WRITE_TMP_FILE%" del /q "%STATE_WRITE_TMP_FILE%" >nul 2>&1
exit /b 0

:save_windows_proxy_state
call :read_reg_value ProxyEnable PREV_PROXY_ENABLE
call :read_reg_value ProxyServer PREV_PROXY_SERVER
call :read_reg_value ProxyOverride PREV_PROXY_OVERRIDE
netsh winhttp dump > "%WINHTTP_DUMP_FILE%" 2>nul
if errorlevel 1 (
    set "WINHTTP_SNAPSHOT_STATUS=failed"
    del /q "%WINHTTP_DUMP_FILE%" >nul 2>&1
    exit /b 1
)
if not exist "%WINHTTP_DUMP_FILE%" (
    set "WINHTTP_SNAPSHOT_STATUS=failed"
    exit /b 1
)
set "WINHTTP_SNAPSHOT_STATUS=ok"
exit /b 0

:read_reg_value
set "%~2=__UNSET__"
for /f "skip=2 tokens=1,2,*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v %~1 2^>nul') do (
    if /i "%%A"=="%~1" set "%~2=__EMPTY__"
    if /i "%%A"=="%~1" if not "%%C"=="" set "%~2=%%C"
)
exit /b 0

:set_windows_proxy
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f >nul
if errorlevel 1 exit /b 1
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /t REG_SZ /d "%~1:%~2" /f >nul
if errorlevel 1 exit /b 1
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride /t REG_SZ /d "localhost;127.0.0.1;<local>" /f >nul
if errorlevel 1 exit /b 1
netsh winhttp set proxy "%~1:%~2" bypass-list="localhost;127.0.0.1;<local>" >nul
if errorlevel 1 exit /b 1
call :refresh_proxy_settings
exit /b 0

:restore_windows_proxy
if not defined WINHTTP_DUMP_FILE (
    >&2 echo [ERROR] Missing WinHTTP proxy snapshot file path; refusing to reset current WinHTTP proxy.
    exit /b 1
)
if /i not "%WINHTTP_SNAPSHOT_STATUS%"=="ok" (
    >&2 echo [ERROR] Missing WinHTTP proxy snapshot; refusing to reset current WinHTTP proxy.
    exit /b 1
)
if not exist "%WINHTTP_DUMP_FILE%" (
    >&2 echo [ERROR] WinHTTP proxy snapshot file missing: %WINHTTP_DUMP_FILE%
    exit /b 1
)
if /i "%PREV_PROXY_ENABLE%"=="__UNSET__" (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul
)
if /i not "%PREV_PROXY_ENABLE%"=="__UNSET__" (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d %PREV_PROXY_ENABLE% /f >nul
)

if /i "%PREV_PROXY_SERVER%"=="__UNSET__" (
    reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /f >nul 2>&1
) else (
    if /i "%PREV_PROXY_SERVER%"=="__EMPTY__" (
        reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /t REG_SZ /d "" /f >nul
    ) else (
        reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /t REG_SZ /d "%PREV_PROXY_SERVER%" /f >nul
    )
)

if /i "%PREV_PROXY_OVERRIDE%"=="__UNSET__" (
    reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride /f >nul 2>&1
) else (
    if /i "%PREV_PROXY_OVERRIDE%"=="__EMPTY__" (
        reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride /t REG_SZ /d "" /f >nul
    ) else (
        reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyOverride /t REG_SZ /d "%PREV_PROXY_OVERRIDE%" /f >nul
    )
)
netsh -f "%WINHTTP_DUMP_FILE%" >nul
if errorlevel 1 exit /b 1
call :refresh_proxy_settings
exit /b 0

:refresh_proxy_settings
rundll32.exe user32.dll,UpdatePerUserSystemParameters >nul 2>&1
exit /b 0

:pid_running
echo(%~1| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 exit /b 1
call :pid_running_via_tasklist "%~1"
exit /b %ERRORLEVEL%

:capture_pid_matches_state
set "PROCESS_MATCH_PID=%~1"
set "PROCESS_MATCH_FLOW_FILE=%~2"
if "%PROCESS_MATCH_FLOW_FILE%"=="" exit /b 2
call :pid_running "%PROCESS_MATCH_PID%"
if errorlevel 1 exit /b 1
set "PROCESS_MATCH_OUT=%TEMP%\mitm-captures-pid-match-%RANDOM%%RANDOM%.txt"
set "PROCESS_MATCH_RESULT="
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $env:PROCESS_MATCH_PID) -ErrorAction Stop; $cmd = $p.CommandLine; $nameok = $p.Name -and $p.Name -ieq 'mitmdump.exe'; $writeflagpos = $cmd.IndexOf(' -w ', [System.StringComparison]::OrdinalIgnoreCase); $flowpos = $cmd.IndexOf($env:PROCESS_MATCH_FLOW_FILE, [System.StringComparison]::OrdinalIgnoreCase); if ($nameok -and $writeflagpos -ge 0 -and $flowpos -gt $writeflagpos) { 'ok' }" > "%PROCESS_MATCH_OUT%" 2>nul
if errorlevel 1 (
    if exist "%PROCESS_MATCH_OUT%" del /q "%PROCESS_MATCH_OUT%" >nul 2>&1
    exit /b 2
)
set /p PROCESS_MATCH_RESULT=<"%PROCESS_MATCH_OUT%"
if errorlevel 1 set "PROCESS_MATCH_RESULT="
if exist "%PROCESS_MATCH_OUT%" del /q "%PROCESS_MATCH_OUT%" >nul 2>&1
if /i not "%PROCESS_MATCH_RESULT%"=="ok" exit /b 2
exit /b 0

:generate_har
if not exist "%FLOW_FILE%" (
    set "HAR_STATUS=skipped"
    exit /b 0
)

if /i "%HAR_BACKEND%"=="mitmdump" (
    if not defined MITMDUMP_CMD (
        set "HAR_STATUS=failed"
        exit /b 1
    )
    set "MITM_HAR_FILE=%HAR_FILE%"
    "%MITMDUMP_CMD%" -q -nr "%FLOW_FILE%" -s "%SCRIPT_DIR%\.har_addon.py"
    if errorlevel 1 (
        set "HAR_STATUS=failed"
        exit /b 1
    )
    set "HAR_STATUS=ok"
    exit /b 0
)

if /i "%HAR_BACKEND%"=="auto" (
    if defined MITMDUMP_CMD (
        set "MITM_HAR_FILE=%HAR_FILE%"
        "%MITMDUMP_CMD%" -q -nr "%FLOW_FILE%" -s "%SCRIPT_DIR%\.har_addon.py" >nul 2>&1
        if not errorlevel 1 (
            set "HAR_STATUS=ok"
            exit /b 0
        )
    )
)

if not defined PYTHON_CMD (
    set "HAR_STATUS=failed"
    exit /b 1
)

"%PYTHON_CMD%" "%SCRIPT_DIR%\flow2har.py" "%FLOW_FILE%" "%HAR_FILE%"
if errorlevel 1 (
    set "HAR_STATUS=failed"
    exit /b 1
)
set "HAR_STATUS=ok"
exit /b 0

:build_ai_bundle
if not exist "%AI_MD_FILE%" (
    set "AI_BUNDLE_STATUS=failed"
    exit /b 1
)
if not exist "%AI_JSON_FILE%" (
    set "AI_BUNDLE_STATUS=failed"
    exit /b 1
)
call :now_iso GENERATED_AT
set "SUMMARY_LINE="
if exist "%SUMMARY_FILE%" set "SUMMARY_LINE=%SUMMARY_FILE%"
set "BUNDLE_TMP_FILE=%BUNDLE_FILE%.tmp.%RANDOM%%RANDOM%"
if exist "%BUNDLE_TMP_FILE%" del /q "%BUNDLE_TMP_FILE%" >nul 2>&1
powershell -NoProfile -Command "$bundle = @(); $bundle += '# AI Analysis Bundle'; $bundle += ''; $bundle += ('GeneratedAt: ' + $env:GENERATED_AT); $bundle += ('TargetDir: ' + $env:TARGET_DIR); $bundle += ('CapturesDir: ' + $env:CAPTURES_DIR); $bundle += ('Manifest: ' + $env:MANIFEST_FILE); $bundle += ('Summary: ' + $env:SUMMARY_LINE); $bundle += ('AiMd: ' + $env:AI_MD_FILE); $bundle += ('AiJson: ' + $env:AI_JSON_FILE); $bundle += ''; $bundle += '## Suggested Use'; $bundle += ''; $bundle += '1) Paste this entire file to your AI assistant'; $bundle += '2) Ask for: root cause hypotheses, endpoint error table, latency bottlenecks, next verification steps'; $bundle += ''; $bundle += '## AI_MD'; $bundle += ''; $bundle += (Get-Content -Raw $env:AI_MD_FILE); $bundle += ''; $bundle += '## AI_JSON'; $bundle += ''; $bundle += (Get-Content -Raw $env:AI_JSON_FILE); if (Test-Path $env:SUMMARY_FILE) { $bundle += ''; $bundle += '## SUMMARY_MD'; $bundle += ''; $bundle += (Get-Content -Raw $env:SUMMARY_FILE); }; Set-Content -Encoding UTF8 -LiteralPath $env:BUNDLE_TMP_FILE $bundle"
if errorlevel 1 (
    if exist "%BUNDLE_TMP_FILE%" del /q "%BUNDLE_TMP_FILE%" >nul 2>&1
    set "AI_BUNDLE_STATUS=failed"
    exit /b 1
)
move /y "%BUNDLE_TMP_FILE%" "%BUNDLE_FILE%" >nul
if errorlevel 1 (
    if exist "%BUNDLE_TMP_FILE%" del /q "%BUNDLE_TMP_FILE%" >nul 2>&1
    set "AI_BUNDLE_STATUS=failed"
    exit /b 1
)
if exist "%BUNDLE_TMP_FILE%" del /q "%BUNDLE_TMP_FILE%" >nul 2>&1
set "AI_BUNDLE_STATUS=ok"
exit /b 0

:write_manifest
set "STOPPED_AT="
if not "%STOP_STATUS%"=="" if /i not "%STOP_STATUS%"=="kill-failed" call :now_iso STOPPED_AT
set "MANIFEST_TMP_FILE=%MANIFEST_FILE%.tmp.%RANDOM%%RANDOM%"
if exist "%MANIFEST_TMP_FILE%" del /q "%MANIFEST_TMP_FILE%" >nul 2>&1
powershell -NoProfile -Command "$manifest = [ordered]@{ schemaVersion = '1'; runId = $env:RUN_ID; targetDir = $env:TARGET_DIR; capturesDir = $env:CAPTURES_DIR; startedAt = $env:STARTED_AT; stoppedAt = $env:STOPPED_AT; programMode = [bool]([int]$env:PROGRAM_MODE); listen = [ordered]@{ host = $env:LISTEN_HOST; port = [int]$env:LISTEN_PORT }; process = [ordered]@{ pid = $env:MITM_PID; launcher = 'mitmdump' }; files = [ordered]@{ flow = $env:FLOW_FILE; har = $env:HAR_FILE; log = $env:LOG_FILE; manifest = $env:MANIFEST_FILE; index = $env:INDEX_FILE; summary = $env:SUMMARY_FILE; aiJson = $env:AI_JSON_FILE; aiMd = $env:AI_MD_FILE; aiBundle = $env:BUNDLE_FILE; stateEnv = $env:ENV_FILE; winhttpSnapshot = $env:WINHTTP_DUMP_FILE }; status = [ordered]@{ stop = $env:STOP_STATUS; proxyRestore = $env:PROXY_STATUS; har = $env:HAR_STATUS; report = $env:REPORT_STATUS; aiBrief = $env:AI_BRIEF_STATUS; aiBundle = $env:AI_BUNDLE_STATUS; winhttpSnapshot = $env:WINHTTP_SNAPSHOT_STATUS }; rawDataPolicy = [ordered]@{ immutable = $true; description = 'Raw capture files are not modified by analysis artifacts' } }; $manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $env:MANIFEST_TMP_FILE"
if errorlevel 1 (
    if exist "%MANIFEST_TMP_FILE%" del /q "%MANIFEST_TMP_FILE%" >nul 2>&1
    exit /b 1
)
move /y "%MANIFEST_TMP_FILE%" "%MANIFEST_FILE%" >nul
if errorlevel 1 (
    if exist "%MANIFEST_TMP_FILE%" del /q "%MANIFEST_TMP_FILE%" >nul 2>&1
    exit /b 1
)
if exist "%MANIFEST_TMP_FILE%" del /q "%MANIFEST_TMP_FILE%" >nul 2>&1
exit /b 0

:bootstrap_cert_material
set "BOOTSTRAP_PID="
for /f %%I in ('powershell -NoProfile -Command "$p = Start-Process -FilePath $env:MITMDUMP_CMD -ArgumentList @(''-q'', ''--listen-host'', ''127.0.0.1'', ''--listen-port'', ''19090'') -PassThru -WindowStyle Hidden; Start-Sleep -Seconds 2; $p.Id"') do set "BOOTSTRAP_PID=%%I"
if defined BOOTSTRAP_PID taskkill /pid %BOOTSTRAP_PID% /t /f >nul 2>&1
exit /b 0

:copy_latest
if not exist "%~1" exit /b 1
set "COPY_LATEST_TMP=%~2.tmp.%RANDOM%%RANDOM%"
if exist "%COPY_LATEST_TMP%" del /q "%COPY_LATEST_TMP%" >nul 2>&1
copy /y "%~1" "%COPY_LATEST_TMP%" >nul
if errorlevel 1 (
    if exist "%COPY_LATEST_TMP%" del /q "%COPY_LATEST_TMP%" >nul 2>&1
    exit /b 1
)
move /y "%COPY_LATEST_TMP%" "%~2" >nul
if errorlevel 1 (
    if exist "%COPY_LATEST_TMP%" del /q "%COPY_LATEST_TMP%" >nul 2>&1
    exit /b 1
)
if exist "%COPY_LATEST_TMP%" del /q "%COPY_LATEST_TMP%" >nul 2>&1
exit /b 0

:stage_start_latest_outputs
call :stage_start_latest_output "%LATEST_FLOW_FILE%" "%START_LATEST_FLOW_BACKUP_FILE%"
call :stage_start_latest_output "%LATEST_HAR_FILE%" "%START_LATEST_HAR_BACKUP_FILE%"
call :stage_start_latest_output "%LATEST_LOG_FILE%" "%START_LATEST_LOG_BACKUP_FILE%"
call :stage_start_latest_output "%LATEST_INDEX_FILE%" "%START_LATEST_INDEX_BACKUP_FILE%"
call :stage_start_latest_output "%LATEST_SUMMARY_FILE%" "%START_LATEST_SUMMARY_BACKUP_FILE%"
call :stage_start_latest_output "%LATEST_AI_JSON_FILE%" "%START_LATEST_AI_JSON_BACKUP_FILE%"
call :stage_start_latest_output "%LATEST_AI_MD_FILE%" "%START_LATEST_AI_MD_BACKUP_FILE%"
call :stage_start_latest_output "%LATEST_AI_BUNDLE_FILE%" "%START_LATEST_AI_BUNDLE_BACKUP_FILE%"
exit /b 0

:stage_start_latest_output
if "%~1"=="" exit /b 0
if "%~2"=="" (
    set "LATEST_STATUS=failed"
    exit /b 0
)
if not exist "%~1" exit /b 0
if exist "%~2" del /q "%~2" >nul 2>&1
if exist "%~2" (
    set "LATEST_STATUS=failed"
    exit /b 0
)
move /y "%~1" "%~2" >nul
if errorlevel 1 set "LATEST_STATUS=failed"
if exist "%~1" set "LATEST_STATUS=failed"
if not exist "%~2" set "LATEST_STATUS=failed"
exit /b 0

:restore_start_latest_outputs
call :restore_start_latest_output "%START_LATEST_FLOW_BACKUP_FILE%" "%LATEST_FLOW_FILE%"
if errorlevel 1 exit /b 1
call :restore_start_latest_output "%START_LATEST_HAR_BACKUP_FILE%" "%LATEST_HAR_FILE%"
if errorlevel 1 exit /b 1
call :restore_start_latest_output "%START_LATEST_LOG_BACKUP_FILE%" "%LATEST_LOG_FILE%"
if errorlevel 1 exit /b 1
call :restore_start_latest_output "%START_LATEST_INDEX_BACKUP_FILE%" "%LATEST_INDEX_FILE%"
if errorlevel 1 exit /b 1
call :restore_start_latest_output "%START_LATEST_SUMMARY_BACKUP_FILE%" "%LATEST_SUMMARY_FILE%"
if errorlevel 1 exit /b 1
call :restore_start_latest_output "%START_LATEST_AI_JSON_BACKUP_FILE%" "%LATEST_AI_JSON_FILE%"
if errorlevel 1 exit /b 1
call :restore_start_latest_output "%START_LATEST_AI_MD_BACKUP_FILE%" "%LATEST_AI_MD_FILE%"
if errorlevel 1 exit /b 1
call :restore_start_latest_output "%START_LATEST_AI_BUNDLE_BACKUP_FILE%" "%LATEST_AI_BUNDLE_FILE%"
if errorlevel 1 exit /b 1
exit /b 0

:restore_start_latest_output
if "%~1"=="" exit /b 0
if "%~2"=="" exit /b 1
if not exist "%~1" exit /b 0
move /y "%~1" "%~2" >nul
if errorlevel 1 exit /b 1
if exist "%~1" exit /b 1
if not exist "%~2" exit /b 1
exit /b 0

:cleanup_start_latest_backups
call :delete_start_latest_backup "%START_LATEST_FLOW_BACKUP_FILE%"
call :delete_start_latest_backup "%START_LATEST_HAR_BACKUP_FILE%"
call :delete_start_latest_backup "%START_LATEST_LOG_BACKUP_FILE%"
call :delete_start_latest_backup "%START_LATEST_INDEX_BACKUP_FILE%"
call :delete_start_latest_backup "%START_LATEST_SUMMARY_BACKUP_FILE%"
call :delete_start_latest_backup "%START_LATEST_AI_JSON_BACKUP_FILE%"
call :delete_start_latest_backup "%START_LATEST_AI_MD_BACKUP_FILE%"
call :delete_start_latest_backup "%START_LATEST_AI_BUNDLE_BACKUP_FILE%"
exit /b 0

:delete_start_latest_backup
if "%~1"=="" exit /b 0
if exist "%~1" del /q "%~1" >nul 2>&1
exit /b 0

:clear_start_latest_outputs
if exist "%LATEST_FLOW_FILE%" del /q "%LATEST_FLOW_FILE%" >nul 2>&1
if exist "%LATEST_FLOW_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_HAR_FILE%" del /q "%LATEST_HAR_FILE%" >nul 2>&1
if exist "%LATEST_HAR_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_LOG_FILE%" del /q "%LATEST_LOG_FILE%" >nul 2>&1
if exist "%LATEST_LOG_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_INDEX_FILE%" del /q "%LATEST_INDEX_FILE%" >nul 2>&1
if exist "%LATEST_INDEX_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_SUMMARY_FILE%" del /q "%LATEST_SUMMARY_FILE%" >nul 2>&1
if exist "%LATEST_SUMMARY_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_AI_JSON_FILE%" del /q "%LATEST_AI_JSON_FILE%" >nul 2>&1
if exist "%LATEST_AI_JSON_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_AI_MD_FILE%" del /q "%LATEST_AI_MD_FILE%" >nul 2>&1
if exist "%LATEST_AI_MD_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_AI_BUNDLE_FILE%" del /q "%LATEST_AI_BUNDLE_FILE%" >nul 2>&1
if exist "%LATEST_AI_BUNDLE_FILE%" set "LATEST_STATUS=failed"
exit /b 0

:clear_latest_outputs
if exist "%LATEST_FLOW_FILE%" del /q "%LATEST_FLOW_FILE%" >nul 2>&1
if exist "%LATEST_FLOW_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_HAR_FILE%" del /q "%LATEST_HAR_FILE%" >nul 2>&1
if exist "%LATEST_HAR_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_LOG_FILE%" del /q "%LATEST_LOG_FILE%" >nul 2>&1
if exist "%LATEST_LOG_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_MANIFEST_FILE%" del /q "%LATEST_MANIFEST_FILE%" >nul 2>&1
if exist "%LATEST_MANIFEST_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_INDEX_FILE%" del /q "%LATEST_INDEX_FILE%" >nul 2>&1
if exist "%LATEST_INDEX_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_SUMMARY_FILE%" del /q "%LATEST_SUMMARY_FILE%" >nul 2>&1
if exist "%LATEST_SUMMARY_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_AI_JSON_FILE%" del /q "%LATEST_AI_JSON_FILE%" >nul 2>&1
if exist "%LATEST_AI_JSON_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_AI_MD_FILE%" del /q "%LATEST_AI_MD_FILE%" >nul 2>&1
if exist "%LATEST_AI_MD_FILE%" set "LATEST_STATUS=failed"
if exist "%LATEST_AI_BUNDLE_FILE%" del /q "%LATEST_AI_BUNDLE_FILE%" >nul 2>&1
if exist "%LATEST_AI_BUNDLE_FILE%" set "LATEST_STATUS=failed"
exit /b 0

:copy_latest_checked
if not exist "%~1" (
    if exist "%~2" (
        del /q "%~2" >nul 2>&1
        if exist "%~2" set "LATEST_STATUS=failed"
    )
    exit /b 0
)
set "COPY_LATEST_CHECKED_TMP=%~2.tmp.%RANDOM%%RANDOM%"
if exist "%COPY_LATEST_CHECKED_TMP%" del /q "%COPY_LATEST_CHECKED_TMP%" >nul 2>&1
copy /y "%~1" "%COPY_LATEST_CHECKED_TMP%" >nul
if errorlevel 1 (
    if exist "%COPY_LATEST_CHECKED_TMP%" del /q "%COPY_LATEST_CHECKED_TMP%" >nul 2>&1
    set "LATEST_STATUS=failed"
    exit /b 0
)
move /y "%COPY_LATEST_CHECKED_TMP%" "%~2" >nul
if errorlevel 1 (
    if exist "%COPY_LATEST_CHECKED_TMP%" del /q "%COPY_LATEST_CHECKED_TMP%" >nul 2>&1
    set "LATEST_STATUS=failed"
    exit /b 0
)
if exist "%COPY_LATEST_CHECKED_TMP%" del /q "%COPY_LATEST_CHECKED_TMP%" >nul 2>&1
exit /b 0

:pid_running_via_tasklist
tasklist /FI "PID eq %~1" | findstr /R /C:"[ ]%~1[ ]" >nul
exit /b %ERRORLEVEL%
