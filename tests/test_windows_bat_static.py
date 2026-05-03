import re
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "mitm-captures.bat"
STATE_IMPORT = ROOT / "state_import.py"


def section_between(text: str, start_label: str, end_label: str) -> str:
    start = text.index(f"\n{start_label}\n") + 1
    end = text.index(f"\n{end_label}\n", start)
    return text[start:end]


def section_from(text: str, start_label: str) -> str:
    start = text.index(f"\n{start_label}\n") + 1
    return text[start:]


class WindowsBatchEntrypointTest(unittest.TestCase):
    def test_batch_entrypoint_declares_expected_commands(self):
        text = BAT.read_text(encoding="utf-8")

        for label in [
            ":cmd_install",
            ":cmd_start",
            ":cmd_stop",
            ":cmd_status",
            ":cmd_ai",
            ":cmd_cert",
            ":ensure_deps",
            ":set_windows_proxy",
            ":restore_windows_proxy",
        ]:
            self.assertIn(label, text)

        for command in ["install", "start", "stop", "status", "ai", "cert"]:
            self.assertRegex(text, rf"\b{re.escape(command)}\b")

    def test_batch_entrypoint_handles_dependencies_and_artifacts(self):
        text = BAT.read_text(encoding="utf-8").lower()

        for token in [
            "winget install",
            "mitmproxy.mitmproxy",
            "python.python.3",
            "pip install --user mitmproxy",
            "mitmdump",
            "flow2har.py",
            "flow_report.py",
            "ai_brief.py",
            "latest.flow",
            "latest.har",
            "latest.summary.md",
            "latest.ai.json",
            "latest.ai.md",
        ]:
            self.assertIn(token, text)

    def test_batch_entrypoint_preserves_and_restores_windows_proxy(self):
        text = BAT.read_text(encoding="utf-8").lower()

        for token in [
            r"hkcu\software\microsoft\windows\currentversion\internet settings",
            "proxyenable",
            "proxyserver",
            "proxyoverride",
            "netsh winhttp dump",
            "netsh winhttp set proxy",
            "netsh -f",
        ]:
            self.assertIn(token, text)

    def test_batch_entrypoint_tracks_capture_state_and_latest_outputs(self):
        text = BAT.read_text(encoding="utf-8").lower()

        for token in [
            "proxy_info.env",
            "mitm_pid=",
            "program_mode=",
            "listen_host=",
            "listen_port=",
            "started_at=",
            "latest.manifest.json",
            "latest.index.ndjson",
            "latest.ai.bundle.txt",
            "taskkill /pid",
            "copy /y",
        ]:
            self.assertIn(token, text)

    def test_cert_command_forces_noninteractive_store_install(self):
        text = BAT.read_text(encoding="utf-8").lower()
        cert_section = section_between(text, ":cmd_cert", ":run_with_capture_lock")

        self.assertIn(
            "powershell -noprofile -command \"$erroractionpreference = 'stop'; import-module microsoft.powershell.security; import-certificate -filepath $env:mitm_cert -certstorelocation 'microsoft.powershell.security\\certificate::currentuser\\root' | out-null\"",
            cert_section,
        )
        self.assertNotIn('certutil -user -addstore root "%mitm_cert%"', cert_section)

    def test_batch_entrypoint_validates_target_dir_and_serializes_capture_commands(self):
        text = BAT.read_text(encoding="utf-8").lower()
        prefix = text[:text.index("\n:usage\n")]
        lock_section = section_between(text, ":run_with_capture_lock", ":validate_target_dir")
        target_dir_section = section_between(text, ":validate_target_dir", ":ensure_deps")

        self.assertIn("test-path -literalpath $env:target_dir -pathtype container", target_dir_section)
        self.assertIn('target directory does not exist: %target_dir%', target_dir_section)
        self.assertIn(":merge_windows_log_streams", target_dir_section)
        self.assertIn('if not exist "%log_file%" (', target_dir_section)
        self.assertIn('move /y "%log_err_file%" "%log_file%" >nul', target_dir_section)
        self.assertIn('type "%log_err_file%" >> "%log_file%"', target_dir_section)
        self.assertIn('.capture.lock', text)

        for token in [
            'call :run_with_capture_lock cmd_start',
            'call :run_with_capture_lock cmd_stop',
            'call :run_with_capture_lock cmd_status',
            'call :run_with_capture_lock cmd_ai',
            'call :validate_target_dir || exit /b 1',
            ':run_with_capture_lock',
            ':acquire_capture_lock',
            ':release_capture_lock',
        ]:
            self.assertIn(token, prefix + lock_section)

        for token in [
            'mkdir "%capture_lock_dir%" >nul 2>&1',
            'rd "%capture_lock_dir%" >nul 2>&1',
            'another capture operation is running. please retry.',
        ]:
            self.assertIn(token, lock_section)

    def test_batch_entrypoint_validates_start_host_and_port_before_launch(self):
        text = BAT.read_text(encoding="utf-8").lower()
        prefix = text[:text.index("\n:usage\n")]
        validate_start_args_section = section_between(text, ":validate_start_args", ":ensure_deps")

        self.assertIn('call :validate_start_args || exit /b 1', prefix)
        self.assertIn('call :validate_target_dir || exit /b 1', prefix)
        self.assertLess(
            prefix.index('call :validate_start_args || exit /b 1'),
            prefix.index('call :run_with_capture_lock cmd_start'),
        )

        for token in [
            'if "%listen_host%"=="" (',
            'listen host cannot be empty',
            'echo(%listen_port%| findstr /r "^[0-9][0-9]*$" >nul',
            'invalid port: %listen_port%',
            'if %listen_port% lss 1 (',
            'if %listen_port% gtr 65535 (',
        ]:
            self.assertIn(token, validate_start_args_section)

    def test_batch_entrypoint_recovers_stale_capture_lock_using_owner_metadata(self):
        text = BAT.read_text(encoding="utf-8").lower()
        acquire_section = section_between(text, ":acquire_capture_lock", ":release_capture_lock")
        release_section = section_between(text, ":release_capture_lock", ":validate_target_dir")
        recover_section = section_between(text, ":recover_stale_capture_lock", ":read_capture_lock_owner_pid")
        read_owner_section = section_between(text, ":read_capture_lock_owner_pid", ":write_capture_lock_owner")
        write_owner_section = section_between(text, ":write_capture_lock_owner", ":resolve_current_cmd_pid")

        self.assertIn('capture_lock_owner_file=%capture_lock_dir%\\.owner.pid', text)
        for token in [
            ":recover_stale_capture_lock",
            ":read_capture_lock_owner_pid",
            ":write_capture_lock_owner",
            ":resolve_current_cmd_pid",
            'call :recover_stale_capture_lock',
            'if not errorlevel 1 goto :acquire_capture_lock_retry',
            'call :write_capture_lock_owner || (',
        ]:
            self.assertIn(token, text)

        for token in [
            'if not exist "%capture_lock_owner_file%" (',
            'if "%force_recover%"=="1" (',
            'call :sleep_one_second',
            'call :resolve_current_cmd_pid current_cmd_pid',
            'if defined capture_lock_owner_pid if defined current_cmd_pid if /i "%capture_lock_owner_pid%"=="%current_cmd_pid%" (',
            'call :pid_running "%capture_lock_owner_pid%"',
            'if not defined capture_lock_owner_pid if not "%force_recover%"=="1" exit /b 1',
            'call :release_capture_lock >nul 2>&1',
            'if exist "%capture_lock_dir%" exit /b 1',
        ]:
            self.assertIn(token, recover_section)

        for token in [
            'set /p capture_lock_owner_pid=<"%capture_lock_owner_file%"',
            'findstr /r "^[0-9][0-9]*$" >nul',
        ]:
            self.assertIn(token, read_owner_section)

        for token in [
            'call :resolve_current_cmd_pid capture_lock_owner_pid',
            '>"%capture_lock_owner_file%" echo %capture_lock_owner_pid%',
            'if not exist "%capture_lock_owner_file%" exit /b 1',
        ]:
            self.assertIn(token, write_owner_section)

        self.assertIn('if exist "%capture_lock_owner_file%" del /q "%capture_lock_owner_file%" >nul 2>&1', release_section)

    def test_batch_entrypoint_avoids_unsafe_state_echo_and_forf_loading(self):
        text = BAT.read_text(encoding="utf-8").lower()

        for token in [
            "echo target_dir=%target_dir%",
            "echo flow_file=%flow_file%",
            "echo prev_proxy_server=%prev_proxy_server%",
            'for /f "usebackq tokens=1* delims==" %%a in ("%env_file%") do set "%%a=%%b"',
        ]:
            self.assertNotIn(token, text)

        for token in [
            "$env:env_file",
            "$env:target_dir",
            "$env:flow_file",
        ]:
            self.assertIn(token, text)

    def test_batch_entrypoint_does_not_reset_winhttp_without_snapshot(self):
        text = BAT.read_text(encoding="utf-8").lower()

        self.assertNotIn("netsh winhttp reset proxy", text)
        self.assertIn("winhttp_snapshot_status", text)

    def test_batch_entrypoint_re_resolves_runtime_commands_after_install(self):
        text = BAT.read_text(encoding="utf-8").lower()
        mitmdump_section = section_between(text, ":resolve_mitmdump_cmd", ":validate_python_cmd")
        validate_mitmdump_section = section_between(text, ":validate_mitmdump_cmd", ":validate_python_cmd")

        for token in [
            ":resolve_python_cmd",
            ":resolve_mitmdump_cmd",
            "mitmdump_cmd",
            "python_cmd",
            "%mitmdump_cmd%",
            "%python_cmd%",
        ]:
            self.assertIn(token, text)

        self.assertIn(":validate_mitmdump_cmd", text)
        self.assertIn(
            'for /f "delims=" %%i in (\'where mitmdump 2^>nul\') do (',
            mitmdump_section,
        )
        self.assertIn('call :validate_mitmdump_cmd "%%i"', mitmdump_section)
        self.assertIn('if not errorlevel 1 set "mitmdump_cmd=%%i"', mitmdump_section)
        self.assertNotIn(
            'for /f "delims=" %%i in (\'where mitmdump 2^>nul\') do if not defined mitmdump_cmd set "mitmdump_cmd=%%i"',
            mitmdump_section,
        )
        self.assertNotIn("select-object -first 1", mitmdump_section)
        for token in [
            'for %%j in ("%mitmdump_validate_cmd%") do set "mitmdump_validate_name=%%~nxj"',
            'if /i not "%mitmdump_validate_name%"=="mitmdump.exe" exit /b 1',
        ]:
            self.assertIn(token, validate_mitmdump_section)

    def test_batch_entrypoint_uses_env_variables_inside_powershell(self):
        text = BAT.read_text(encoding="utf-8").lower()

        for token in [
            "$env:mitmdump_cmd",
            "$env:log_file",
            "$env:flow_file",
            "$env:ai_md_file",
            "$env:manifest_file",
        ]:
            self.assertIn(token, text)

        for token in [
            "''%flow_file%''",
            "''%log_file%''",
            "''%manifesT_file%''".lower(),
        ]:
            self.assertNotIn(token, text)

    def test_har_backend_rejects_invalid_values(self):
        text = BAT.read_text(encoding="utf-8").lower()
        prefix = text[:text.index("\nif /i \"%command%\"==\"install\" goto :dispatch_install\n".lower())]

        self.assertIn('if /i not "%har_backend%"=="auto" if /i not "%har_backend%"=="mitmdump" if /i not "%har_backend%"=="python" (', prefix)
        self.assertIn('set "arg_error=invalid --har-backend: %har_backend%"', prefix)

    def test_python_resolution_validates_real_interpreter_not_windowsapps_alias(self):
        text = BAT.read_text(encoding="utf-8").lower()
        section = section_between(text, ":resolve_python_cmd", ":resolve_mitmproxy_python_cmd")
        mitmproxy_section = section_between(text, ":resolve_mitmproxy_python_cmd", ":resolve_mitmdump_cmd")

        for token in [
            ":validate_python_cmd",
            ":validate_python_with_mitmproxy_cmd",
            ":python_cmd_from_mitmdump",
            "windowsapps\\python.exe",
            'import sys; print(sys.executable)',
            "call :validate_python_cmd",
        ]:
            self.assertIn(token, text)

        self.assertIn(
            'for /f "delims=" %%i in (\'where python 2^>nul\') do (',
            section,
        )
        self.assertIn('if defined mitmdump_cmd (', mitmproxy_section)
        self.assertIn('call :python_cmd_from_mitmdump "%mitmdump_cmd%"', mitmproxy_section)
        self.assertIn('call :validate_python_with_mitmproxy_cmd', mitmproxy_section)
        self.assertIn('import mitmproxy, sys; print(sys.executable)', text)
        self.assertIn('call :validate_python_cmd "%%i"', section)
        self.assertIn('if not errorlevel 1 set "python_cmd=%%i"', section)
        self.assertNotIn(
            'for /f "delims=" %%i in (\'where python 2^>nul\') do if not defined python_cmd set "python_cmd=%%i"',
            section,
        )
        self.assertNotIn("select-object -first 1", section)

    def test_load_state_escapes_single_percent_and_callers_fail_closed(self):
        text = BAT.read_text(encoding="utf-8").lower()
        load_state_section = section_between(text, ":load_state", ":reset_loaded_state_variables")

        self.assertIn("call :resolve_python_cmd", load_state_section)
        self.assertIn("state_import.py", load_state_section)
        self.assertIn('"%python_cmd%" "%script_dir%\\state_import.py" "%env_file%" "%state_import_file%"', load_state_section)
        self.assertIn("python is required to load capture state", load_state_section)
        self.assertNotIn("powershell -noprofile -command", load_state_section)
        self.assertGreaterEqual(text.count("call :load_state || exit /b 1"), 3)

    def test_load_state_rejects_unexpected_keys_before_importing_generated_cmd(self):
        text = BAT.read_text(encoding="utf-8").lower()
        load_state_section = section_between(text, ":load_state", ":reset_loaded_state_variables")

        self.assertIn("state_import.py", load_state_section)
        self.assertNotIn("$allowedstatekeys", load_state_section)
        self.assertNotIn("containskey($key)", load_state_section)
        self.assertNotIn(
            "$key = $matches.k",
            load_state_section,
        )

    def test_state_import_helper_escapes_percent_and_preserves_equals(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "proxy_info.env"
            import_file = Path(temp_dir) / "state.cmd"
            state_file.write_text(
                "MITM_PID=123\n"
                "FLOW_FILE=C:\\tmp\\100%\\capture=one.flow\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(STATE_IMPORT), str(state_file), str(import_file)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                import_file.read_text(encoding="utf-8"),
                'set "MITM_PID=123"\n'
                'set "FLOW_FILE=C:\\tmp\\100%%\\capture=one.flow"\n',
            )

    def test_state_import_helper_rejects_unexpected_keys_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "proxy_info.env"
            import_file = Path(temp_dir) / "state.cmd"
            state_file.write_text("MITM_PID=123\nBAD_KEY=value\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(STATE_IMPORT), str(state_file), str(import_file)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unexpected state key: BAD_KEY", result.stderr)
            self.assertFalse(import_file.exists())

    def test_start_rolls_back_process_when_state_persistence_fails(self):
        text = BAT.read_text(encoding="utf-8").lower()
        start_section = section_between(text, ":cmd_start", ":cmd_stop")
        rollback_section = section_between(text, ":rollback_failed_start", ":write_state")

        for token in [
            ":rollback_failed_start",
            'call :write_state || call :rollback_failed_start "state-write-failed"',
            'call :write_manifest || call :rollback_failed_start "manifest-write-failed"',
            'call :copy_latest "%manifest_file%" "%latest_manifest_file%" || call :rollback_failed_start "latest-manifest-write-failed"',
        ]:
            self.assertIn(token, text)

        self.assertIn(
            'call :set_windows_proxy "%listen_host%" "%listen_port%" || call :rollback_failed_start "windows-proxy-set-failed"',
            start_section,
        )
        self.assertLess(
            start_section.index('call :set_windows_proxy "%listen_host%" "%listen_port%" || call :rollback_failed_start "windows-proxy-set-failed"'),
            start_section.index('call :copy_latest "%manifest_file%" "%latest_manifest_file%" || call :rollback_failed_start "latest-manifest-write-failed"'),
        )
        self.assertIn('call :restore_windows_proxy >nul 2>&1', rollback_section)
        self.assertIn(
            'if /i not "%rollback_proxy_status%"=="restore-failed" if /i not "%rollback_latest_status%"=="restore-failed" if exist "%env_file%" del /q "%env_file%" >nul 2>&1',
            rollback_section,
        )
        self.assertIn(
            'if /i not "%rollback_proxy_status%"=="restore-failed" if /i not "%rollback_latest_status%"=="restore-failed" if exist "%manifest_file%" del /q "%manifest_file%" >nul 2>&1',
            rollback_section,
        )
        self.assertNotIn('if exist "%latest_manifest_file%" del /q "%latest_manifest_file%" >nul 2>&1', rollback_section)
        self.assertNotIn('\nif exist "%env_file%" del /q "%env_file%" >nul 2>&1', rollback_section)
        self.assertNotIn('\nif exist "%manifest_file%" del /q "%manifest_file%" >nul 2>&1', rollback_section)

    def test_write_state_publishes_proxy_info_env_atomically(self):
        text = BAT.read_text(encoding="utf-8").lower()
        state_section = section_between(text, ":write_state", ":save_windows_proxy_state")

        for token in [
            'set "state_write_tmp_file=%env_file%.tmp.%random%%random%"',
            "$env:state_write_tmp_file",
            'move /y "%state_write_tmp_file%" "%env_file%" >nul',
            'if exist "%state_write_tmp_file%" del /q "%state_write_tmp_file%" >nul 2>&1',
        ]:
            self.assertIn(token, state_section)

        self.assertNotIn(
            "set-content -encoding utf8 -literalpath $env:env_file $lines",
            state_section,
        )

    def test_start_waits_for_stable_process_window_before_persisting_state(self):
        text = BAT.read_text(encoding="utf-8").lower()
        start_section = section_between(text, ":cmd_start", ":cmd_stop")
        startup_probe_section = section_between(text, ":wait_for_startup_stability", ":handle_existing_state_before_start")

        self.assertIn('call :wait_for_startup_stability', start_section)
        self.assertLess(
            start_section.index('call :wait_for_startup_stability'),
            start_section.index('call :write_state || call :rollback_failed_start "state-write-failed"'),
        )
        self.assertNotIn('call :sleep_one_second\ncall :pid_running "%mitm_pid%"', start_section)

        for token in [
            'set "startup_wait_seconds=6"',
            'call :pid_running "%mitm_pid%"',
            'call :sleep_one_second',
            'set /a startup_wait_seconds-=1',
            'if "%startup_wait_seconds%"=="0" exit /b 0',
        ]:
            self.assertIn(token, startup_probe_section)

    def test_start_clears_stale_mitm_pid_before_spawn(self):
        text = BAT.read_text(encoding="utf-8").lower()
        start_section = section_between(text, ":cmd_start", ":cmd_stop")

        self.assertIn('set "mitm_pid="', start_section)
        self.assertLess(
            start_section.index('set "mitm_pid="'),
            start_section.index('start "" /b "%comspec%"'),
        )
        self.assertLess(
            start_section.index('set "mitm_pid="'),
            start_section.index('if not defined mitm_pid ('),
        )
        self.assertIn('start "" /b "%comspec%" /d /s /c ""%mitmdump_cmd%" -q --listen-host "%listen_host%"', start_section)
        self.assertIn('> "%log_file%" 2> "%log_err_file%"', start_section)
        self.assertIn('call :wait_for_spawned_capture_pid "%flow_file%" mitm_pid', start_section)
        self.assertNotIn("start-process -filepath $env:mitmdump_cmd", start_section)

    def test_start_discovers_real_mitmdump_pid_after_background_launch(self):
        text = BAT.read_text(encoding="utf-8").lower()
        wait_section = section_between(text, ":wait_for_spawned_capture_pid", ":handle_existing_state_before_start")
        find_section = section_between(text, ":find_capture_pid_by_flow", ":generate_har")

        for token in [
            'set "wait_pid_seconds=10"',
            'call :find_capture_pid_by_flow "%wait_pid_flow_file%" wait_pid_value',
            'if defined wait_pid_value (',
            'set "%wait_pid_var%=%wait_pid_value%"',
            'call :sleep_one_second',
        ]:
            self.assertIn(token, wait_section)

        for token in [
            "$env:process_find_flow_file",
            'set "process_find_pid="',
            "get-ciminstance win32_process",
            "name='mitmdump.exe'",
            "$matches = @(",
            "$matches.count -gt 0",
            "commandline.indexof($flow, [system.stringcomparison]::ordinalignorecase)",
            "sort-object processid -descending",
            'findstr /r "^[0-9][0-9]*$" >nul',
            'set "%~2=%process_find_pid%"',
        ]:
            self.assertIn(token, find_section)

    def test_start_clears_stale_latest_outputs_and_publishes_manifest_atomically(self):
        text = BAT.read_text(encoding="utf-8").lower()
        start_section = section_between(text, ":cmd_start", ":cmd_stop")
        copy_latest_section = section_between(text, ":copy_latest", ":clear_start_latest_outputs")
        start_latest_clear_section = section_between(text, ":clear_start_latest_outputs", ":clear_latest_outputs")

        self.assertIn('set "latest_status=ok"', start_section)
        self.assertIn('call :clear_start_latest_outputs', start_section)
        self.assertIn('if not "%latest_status%"=="ok" call :rollback_failed_start "latest-clear-failed"', start_section)
        self.assertLess(
            start_section.index('call :clear_start_latest_outputs'),
            start_section.index('call :copy_latest "%manifest_file%" "%latest_manifest_file%" || call :rollback_failed_start "latest-manifest-write-failed"'),
        )

        for token in [
            'if exist "%latest_flow_file%" del /q "%latest_flow_file%" >nul 2>&1',
            'if exist "%latest_har_file%" del /q "%latest_har_file%" >nul 2>&1',
            'if exist "%latest_summary_file%" del /q "%latest_summary_file%" >nul 2>&1',
            'if exist "%latest_ai_bundle_file%" del /q "%latest_ai_bundle_file%" >nul 2>&1',
        ]:
            self.assertIn(token, start_latest_clear_section)
        self.assertNotIn('if exist "%latest_manifest_file%" del /q "%latest_manifest_file%" >nul 2>&1', start_latest_clear_section)

        for token in [
            'set "copy_latest_tmp=%~2.tmp.%random%%random%"',
            'copy /y "%~1" "%copy_latest_tmp%" >nul',
            'move /y "%copy_latest_tmp%" "%~2" >nul',
            'if exist "%copy_latest_tmp%" del /q "%copy_latest_tmp%" >nul 2>&1',
        ]:
            self.assertIn(token, copy_latest_section)

    def test_auto_har_backend_prefers_python_before_mitmdump_on_windows(self):
        text = BAT.read_text(encoding="utf-8").lower()
        generate_har_section = section_between(text, ":generate_har", ":build_ai_bundle")

        self.assertIn('if /i "%har_backend%"=="auto" (', generate_har_section)
        self.assertIn('"%python_cmd%" "%script_dir%\\flow2har.py" "%flow_file%" "%har_file%"', generate_har_section)
        self.assertIn('"%mitmdump_cmd%" -q -nr "%flow_file%" -s "%script_dir%\\.har_addon.py" >nul 2>&1', generate_har_section)
        self.assertLess(
            generate_har_section.index('"%python_cmd%" "%script_dir%\\flow2har.py" "%flow_file%" "%har_file%"'),
            generate_har_section.index('"%mitmdump_cmd%" -q -nr "%flow_file%" -s "%script_dir%\\.har_addon.py" >nul 2>&1'),
        )

    def test_start_restores_previous_latest_outputs_when_prepublish_refresh_aborts(self):
        text = BAT.read_text(encoding="utf-8").lower()
        start_section = section_between(text, ":cmd_start", ":cmd_stop")
        rollback_section = section_between(text, ":rollback_failed_start", ":write_state")
        restore_latest_section = section_between(text, ":restore_start_latest_outputs", ":restore_start_latest_output")
        restore_latest_one_section = section_between(text, ":restore_start_latest_output", ":cleanup_start_latest_backups")
        state_section = section_between(text, ":write_state", ":save_windows_proxy_state")
        existing_state_section = section_between(text, ":handle_existing_state_before_start", ":load_state")

        for token in [
            ":stage_start_latest_outputs",
            ":restore_start_latest_outputs",
            ":cleanup_start_latest_backups",
            'call :stage_start_latest_outputs',
            'if not "%latest_status%"=="ok" call :rollback_failed_start "latest-stage-failed"',
            'call :cleanup_start_latest_backups',
            'set "rollback_latest_status=skipped"',
            'call :restore_start_latest_outputs',
        ]:
            self.assertIn(token, text)

        self.assertLess(
            start_section.index('call :stage_start_latest_outputs'),
            start_section.index('call :copy_latest "%manifest_file%" "%latest_manifest_file%" || call :rollback_failed_start "latest-manifest-write-failed"'),
        )
        self.assertLess(
            start_section.index('call :copy_latest "%manifest_file%" "%latest_manifest_file%" || call :rollback_failed_start "latest-manifest-write-failed"'),
            start_section.index('call :cleanup_start_latest_backups'),
        )
        self.assertIn('call :restore_start_latest_outputs', rollback_section)
        self.assertNotIn('call :restore_start_latest_outputs >nul 2>&1', rollback_section)
        self.assertIn('if errorlevel 1 (', rollback_section)
        self.assertIn('set "rollback_latest_status=restore-failed"', rollback_section)
        self.assertIn('set "rollback_latest_status=restore-ok"', rollback_section)
        self.assertIn(
            'if /i not "%rollback_proxy_status%"=="restore-failed" if /i not "%rollback_latest_status%"=="restore-failed" if exist "%env_file%" del /q "%env_file%" >nul 2>&1',
            rollback_section,
        )
        self.assertIn(
            'if /i not "%rollback_proxy_status%"=="restore-failed" if /i not "%rollback_latest_status%"=="restore-failed" if exist "%manifest_file%" del /q "%manifest_file%" >nul 2>&1',
            rollback_section,
        )
        self.assertIn('call :restore_start_latest_output "%start_latest_flow_backup_file%" "%latest_flow_file%"', restore_latest_section)
        self.assertIn('move /y "%~1" "%~2" >nul', restore_latest_one_section)
        self.assertIn('if errorlevel 1 exit /b 1', restore_latest_one_section)
        self.assertIn('if exist "%~1" exit /b 1', restore_latest_one_section)
        self.assertIn('if not exist "%~2" exit /b 1', restore_latest_one_section)
        for token in [
            "start_latest_flow_backup_file",
            "start_latest_har_backup_file",
            "start_latest_log_backup_file",
            "start_latest_index_backup_file",
            "start_latest_summary_backup_file",
            "start_latest_ai_json_backup_file",
            "start_latest_ai_md_backup_file",
            "start_latest_ai_bundle_backup_file",
        ]:
            self.assertIn(token, state_section)
        self.assertIn('call :cleanup_start_latest_backups >nul 2>&1', existing_state_section)
        self.assertLess(
            existing_state_section.index('call :cleanup_start_latest_backups >nul 2>&1'),
            existing_state_section.index('del /q "%env_file%" >nul 2>&1'),
        )

    def test_stop_refuses_proxy_restore_when_loaded_state_is_incomplete(self):
        text = BAT.read_text(encoding="utf-8").lower()
        stop_section = section_between(text, ":cmd_stop", ":cmd_status")
        load_state_section = section_between(text, ":load_state", ":rollback_failed_start")
        reset_section = section_between(text, ":reset_loaded_state_variables", ":validate_loaded_state")
        validate_state_section = section_between(text, ":validate_loaded_state", ":validate_proxy_restore_state")
        validate_proxy_restore_section = section_between(text, ":validate_proxy_restore_state", ":rollback_failed_start")
        restore_section = section_between(text, ":restore_windows_proxy", ":refresh_proxy_settings")

        self.assertIn('call :reset_loaded_state_variables', load_state_section)
        for token in [
            'set "program_mode="',
            'set "flow_file="',
            'set "listen_host="',
            'set "listen_port="',
            'set "prev_proxy_enable="',
            'set "winhttp_snapshot_status="',
        ]:
            self.assertIn(token, reset_section)

        for token in [
            'if not defined mitm_pid (',
            'invalid state file: missing mitm_pid',
            'echo(%mitm_pid%| findstr /r "^[0-9][0-9]*$" >nul',
            'invalid state file: invalid mitm_pid=%mitm_pid%',
            'if not defined program_mode (',
            'invalid state file: missing program_mode',
            'if not "%program_mode%"=="0" if not "%program_mode%"=="1" (',
            'invalid state file: unsupported program_mode=%program_mode%',
            'if not defined flow_file (',
            'invalid state file: missing flow_file',
            'if not defined listen_host (',
            'invalid state file: missing listen_host',
            'if not defined listen_port (',
            'invalid state file: missing listen_port',
            'echo(%listen_port%| findstr /r "^[0-9][0-9]*$" >nul',
            'invalid state file: invalid listen_port=%listen_port%',
            'if %listen_port% lss 1 (',
            'if %listen_port% gtr 65535 (',
        ]:
            self.assertIn(token, validate_state_section)

        for token in [
            'if "%program_mode%"=="1" exit /b 0',
            'if not defined prev_proxy_enable (',
            'invalid state file: missing prev_proxy_enable',
            'if /i not "%prev_proxy_enable%"=="__unset__" (',
            'echo(%prev_proxy_enable%| findstr /r /i /c:"^0x[01]$" /c:"^[01]$" >nul',
            'invalid state file: invalid prev_proxy_enable=%prev_proxy_enable%',
            'if not defined prev_proxy_server (',
            'invalid state file: missing prev_proxy_server',
            'if not defined prev_proxy_override (',
            'invalid state file: missing prev_proxy_override',
            'if not defined winhttp_dump_file (',
            'invalid state file: missing winhttp_dump_file',
            'if /i not "%winhttp_snapshot_status%"=="ok" (',
            'invalid state file: missing winhttp proxy snapshot status',
        ]:
            self.assertIn(token, validate_proxy_restore_section)

        self.assertIn('call :validate_loaded_state || exit /b 1', stop_section)
        self.assertIn('call :validate_proxy_restore_state || exit /b 1', stop_section)
        self.assertLess(
            stop_section.index('call :validate_loaded_state || exit /b 1'),
            stop_section.index('call :validate_proxy_restore_state || exit /b 1'),
        )
        self.assertLess(
            stop_section.index('call :validate_proxy_restore_state || exit /b 1'),
            stop_section.index('if defined mitm_pid ('),
        )
        self.assertLess(
            stop_section.index('call :validate_proxy_restore_state || exit /b 1'),
            stop_section.index('call :restore_windows_proxy'),
        )
        self.assertIn('        )\n    )\n)\nif not "%program_mode%"=="1" (', stop_section)

        self.assertIn('if not defined winhttp_dump_file (', restore_section)
        self.assertIn('if /i not "%winhttp_snapshot_status%"=="ok" (', restore_section)
        self.assertIn('if not exist "%winhttp_dump_file%" (', restore_section)
        self.assertLess(
            restore_section.index('if /i not "%winhttp_snapshot_status%"=="ok" ('),
            restore_section.index('reg add "hkcu\\software\\microsoft\\windows\\currentversion\\internet settings" /v proxyenable /t reg_dword /d 0 /f >nul'),
        )
        self.assertLess(
            restore_section.index('if not exist "%winhttp_dump_file%" ('),
            restore_section.index('reg add "hkcu\\software\\microsoft\\windows\\currentversion\\internet settings" /v proxyenable /t reg_dword /d 0 /f >nul'),
        )

    def test_loaded_state_pid_must_match_capture_command_line_before_stop_or_reuse(self):
        text = BAT.read_text(encoding="utf-8").lower()
        stop_section = section_between(text, ":cmd_stop", ":cmd_status")
        status_section = section_between(text, ":cmd_status", ":cmd_ai")
        existing_state_section = section_between(text, ":handle_existing_state_before_start", ":load_state")
        pid_section = section_between(text, ":pid_running", ":generate_har")
        capture_section = section_between(text, ":capture_pid_matches_state", ":generate_har")
        mismatch_recover_section = existing_state_section[
            existing_state_section.index('if errorlevel 2 ('):
            existing_state_section.index('if not errorlevel 1 (')
        ]
        stop_mismatch_section = stop_section[
            stop_section.index('if errorlevel 2 ('):
            stop_section.index('if errorlevel 1 (')
        ]

        for token in [
            ":capture_pid_matches_state",
            'call :capture_pid_matches_state "%mitm_pid%" "%flow_file%"',
            "$env:process_match_pid",
            "$env:process_match_flow_file",
            "get-ciminstance win32_process",
            "commandline",
            "mitmdump.exe",
            "$nameok = $p.name -and $p.name -ieq 'mitmdump.exe'",
            "$writeflagpos = $cmd.indexof(' -w ', [system.stringcomparison]::ordinalignorecase)",
            "$flowpos = $cmd.indexof($env:process_match_flow_file, [system.stringcomparison]::ordinalignorecase)",
            "if ($nameok -and $writeflagpos -ge 0 -and $flowpos -gt $writeflagpos) { 'ok' }",
        ]:
            self.assertIn(token, text)

        self.assertIn('call :capture_pid_matches_state "%mitm_pid%" "%flow_file%"', stop_section)
        self.assertIn('call :capture_pid_matches_state "%mitm_pid%" "%flow_file%"', status_section)
        self.assertIn('call :capture_pid_matches_state "%mitm_pid%" "%flow_file%"', existing_state_section)
        self.assertNotIn('tasklist /fi "pid eq %~1" | findstr /r /c:"[ ]%~1[ ]" >nul', pid_section)
        self.assertIn('tasklist /fi "pid eq %~1" | findstr /r /c:"[ ]%~1[ ]" >nul', text)

        self.assertIn('if "%process_match_flow_file%"=="" exit /b 2', capture_section)
        self.assertIn('call :pid_running "%process_match_pid%"', capture_section)
        self.assertIn('if errorlevel 1 exit /b 1', capture_section)
        self.assertIn('if /i not "%process_match_result%"=="ok" exit /b 2', capture_section)

        for section in [stop_section, status_section, existing_state_section]:
            self.assertIn('if errorlevel 2 (', section)
            self.assertIn('active pid no longer matches capture state: %mitm_pid%', section)

        self.assertLess(
            stop_section.index('if errorlevel 2 ('),
            stop_section.index('if errorlevel 1 ('),
        )
        self.assertLess(
            status_section.index('if errorlevel 2 ('),
            status_section.index('if not errorlevel 1 set "running=yes"'),
        )
        self.assertLess(
            existing_state_section.index('if errorlevel 2 ('),
            existing_state_section.index('if "%force_recover%"=="1" ('),
        )
        self.assertIn('if "%force_recover%"=="1" (', mismatch_recover_section)
        self.assertIn('call :cleanup_start_latest_backups >nul 2>&1', mismatch_recover_section)
        self.assertIn('del /q "%env_file%" >nul 2>&1', mismatch_recover_section)
        self.assertLess(
            mismatch_recover_section.index('if "%force_recover%"=="1" ('),
            mismatch_recover_section.index('active pid no longer matches capture state: %mitm_pid%'),
        )
        self.assertIn('if "%force_recover%"=="1" (', stop_mismatch_section)
        self.assertIn('set "stop_status=already-exited"', stop_mismatch_section)
        self.assertLess(
            stop_mismatch_section.index('if "%force_recover%"=="1" ('),
            stop_mismatch_section.index('active pid no longer matches capture state: %mitm_pid%'),
        )

    def test_stop_fails_closed_when_manifest_or_latest_persistence_fails(self):
        text = BAT.read_text(encoding="utf-8").lower()
        section = section_between(text, ":cmd_stop", ":cmd_status")
        latest_helper_section = section_from(text, ":copy_latest_checked")
        latest_clear_section = section_between(text, ":clear_latest_outputs", ":copy_latest_checked")
        manifest_section = section_between(text, ":write_manifest", ":bootstrap_cert_material")

        self.assertNotIn('call :ensure_deps || exit /b 1', section)
        self.assertIn('call :resolve_mitmproxy_python_cmd >nul 2>&1', section)
        self.assertIn('call :resolve_mitmdump_cmd >nul 2>&1', section)

        for token in [
            'set "manifest_status=skipped"',
            'set "latest_status=ok"',
            'call :write_manifest',
            'set "manifest_status=failed"',
            'set "manifest_status=ok"',
            'call :copy_latest_checked "%flow_file%" "%latest_flow_file%"',
            'call :copy_latest_checked "%har_file%" "%latest_har_file%"',
            'call :copy_latest_checked "%log_file%" "%latest_log_file%"',
            'call :copy_latest_checked "%index_file%" "%latest_index_file%"',
            'call :copy_latest_checked "%summary_file%" "%latest_summary_file%"',
            'call :copy_latest_checked "%ai_json_file%" "%latest_ai_json_file%"',
            'call :copy_latest_checked "%ai_md_file%" "%latest_ai_md_file%"',
            'call :copy_latest_checked "%bundle_file%" "%latest_ai_bundle_file%"',
            'set "stop_exit_code=0"',
            'if "%manifest_status%"=="failed" set "stop_exit_code=2"',
            'if "%latest_status%"=="failed" set "stop_exit_code=2"',
            'exit /b %stop_exit_code%',
        ]:
            self.assertIn(token, section)

        self.assertIn(
            'if not "%manifest_status%"=="failed" call :copy_latest_checked "%manifest_file%" "%latest_manifest_file%"',
            section,
        )
        self.assertIn('call :clear_latest_outputs', section)
        self.assertLess(
            section.index('call :clear_latest_outputs'),
            section.index('call :copy_latest_checked "%flow_file%" "%latest_flow_file%"'),
        )
        self.assertIn('if "%manifest_status%"=="failed" set "latest_status=failed"', section)
        self.assertIn('if not "%latest_status%"=="ok" call :clear_latest_outputs', section)
        self.assertIn(":copy_latest_checked", text)
        self.assertIn(":clear_latest_outputs", text)
        self.assertIn(
            'if not "%keep_env%"=="1" if "%stop_exit_code%"=="0" del /q "%env_file%" >nul 2>&1',
            section,
        )
        self.assertNotIn(
            'if not "%keep_env%"=="1" del /q "%env_file%" >nul 2>&1',
            section,
        )
        self.assertGreaterEqual(section.count('call :write_manifest'), 2)
        self.assertLess(
            section.index('call :write_manifest'),
            section.index('"%python_cmd%" "%script_dir%\\ai_brief.py" "%manifest_file%" "%index_file%" "%ai_json_file%" "%ai_md_file%"'),
        )
        self.assertIn('if /i not "%stop_status%"=="kill-failed" (', section)
        self.assertIn('if "%stop_status%"=="kill-failed" set "har_status=blocked-by-active-capture"', section)
        self.assertIn('if "%stop_status%"=="kill-failed" set "report_status=blocked-by-active-capture"', section)
        self.assertIn('if "%stop_status%"=="kill-failed" set "ai_brief_status=blocked-by-active-capture"', section)
        self.assertIn('if "%stop_status%"=="kill-failed" set "ai_bundle_status=blocked-by-active-capture"', section)
        self.assertIn('if /i "%stop_status%"=="kill-failed" (\n    call :write_manifest', section)
        self.assertIn('if /i not "%stop_status%"=="kill-failed" call :now_iso stopped_at', manifest_section)

        for token in [
            'if exist "%latest_flow_file%" del /q "%latest_flow_file%" >nul 2>&1',
            'if exist "%latest_manifest_file%" del /q "%latest_manifest_file%" >nul 2>&1',
            'if exist "%latest_ai_bundle_file%" del /q "%latest_ai_bundle_file%" >nul 2>&1',
            'if not exist "%~1" (',
            'if exist "%~2" (',
            'del /q "%~2" >nul 2>&1',
            'if exist "%~2" set "latest_status=failed"',
            'set "copy_latest_checked_tmp=%~2.tmp.%random%%random%"',
            'copy /y "%~1" "%copy_latest_checked_tmp%" >nul',
            'move /y "%copy_latest_checked_tmp%" "%~2" >nul',
            'if exist "%copy_latest_checked_tmp%" del /q "%copy_latest_checked_tmp%" >nul 2>&1',
        ]:
            self.assertIn(token, latest_clear_section + latest_helper_section)
        self.assertNotIn('call :copy_latest "%~1" "%~2"', latest_helper_section)
        self.assertNotIn('copy /y "%~1" "%~2" >nul', latest_helper_section)

    def test_ai_stdout_flag_is_opt_in(self):
        text = BAT.read_text(encoding="utf-8").lower()
        prefix = text[:text.index("\n:parse_args\n")]
        parse_args_section = section_between(text, ":parse_args", ":cmd_install")
        ai_section = section_between(text, ":cmd_ai", ":cmd_cert")

        self.assertIn('set "print_stdout=0"', prefix)
        self.assertNotIn('set "print_stdout=1"', prefix)
        self.assertIn('if /i "%~1"=="--stdout" (', parse_args_section)
        self.assertIn('set "print_stdout=1"', parse_args_section)
        self.assertIn('if "%print_stdout%"=="1" type "%latest_ai_bundle_file%"', ai_section)

    def test_batch_entrypoint_forwards_shifted_args_into_parse_args(self):
        text = BAT.read_text(encoding="utf-8").lower()
        prefix = text[:text.index("\n:usage\n")]

        self.assertIn('set "command=%~1"', prefix)
        self.assertIn("shift /1", prefix)
        self.assertIn("call :parse_args %1 %2 %3 %4 %5 %6 %7 %8 %9", prefix)
        self.assertNotIn("call :parse_args %*", prefix)
        self.assertLess(prefix.index("shift /1"), prefix.index("call :parse_args %1 %2 %3 %4 %5 %6 %7 %8 %9"))

    def test_manifest_and_ai_bundle_publish_atomically(self):
        text = BAT.read_text(encoding="utf-8").lower()
        manifest_section = section_between(text, ":write_manifest", ":bootstrap_cert_material")
        bundle_section = section_between(text, ":build_ai_bundle", ":write_manifest")

        for token in [
            'set "manifest_tmp_file=%manifest_file%.tmp.%random%%random%"',
            "$env:manifest_tmp_file",
            'move /y "%manifest_tmp_file%" "%manifest_file%" >nul',
            'if exist "%manifest_tmp_file%" del /q "%manifest_tmp_file%" >nul 2>&1',
            "utf8encoding($false)",
        ]:
            self.assertIn(token, manifest_section)

        self.assertIn("utf8encoding($false)", bundle_section)
        self.assertNotIn("set-content -encoding utf8 -literalpath $env:bundle_tmp_file $bundle", bundle_section)
        self.assertNotIn("set-content -encoding utf8 -literalpath $env:manifest_tmp_file", manifest_section)

        for token in [
            'set "bundle_tmp_file=%bundle_file%.tmp.%random%%random%"',
            "$env:bundle_tmp_file",
            'move /y "%bundle_tmp_file%" "%bundle_file%" >nul',
            'if exist "%bundle_tmp_file%" del /q "%bundle_tmp_file%" >nul 2>&1',
        ]:
            self.assertIn(token, bundle_section)

        self.assertNotIn(
            "set-content -encoding utf8 $env:manifest_file",
            manifest_section,
        )
        self.assertNotIn(
            "set-content -encoding utf8 $env:bundle_file $bundle",
            bundle_section,
        )

    def test_proxy_snapshot_preserves_empty_registry_values(self):
        text = BAT.read_text(encoding="utf-8").lower()
        read_reg_section = section_between(text, ":read_reg_value", ":set_windows_proxy")
        restore_section = section_between(text, ":restore_windows_proxy", ":refresh_proxy_settings")

        for token in [
            'set "%~2=__empty__"',
            'if /i "%%a"=="%~1" set "%~2=__empty__"',
            'if /i "%%a"=="%~1" if not "%%c"=="" set "%~2=%%c"',
            'if /i "%prev_proxy_server%"=="__empty__" (',
            'reg add "hkcu\\software\\microsoft\\windows\\currentversion\\internet settings" /v proxyserver /t reg_sz /d "" /f >nul',
            'if /i "%prev_proxy_override%"=="__empty__" (',
            'reg add "hkcu\\software\\microsoft\\windows\\currentversion\\internet settings" /v proxyoverride /t reg_sz /d "" /f >nul',
        ]:
            self.assertIn(token, read_reg_section + restore_section)


if __name__ == "__main__":
    unittest.main()
