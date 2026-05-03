from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "tests" / "runtime_smoke.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
START_CAPTURE = ROOT / "startCaptures.sh"
STOP_CAPTURE = ROOT / "stopCaptures.sh"


def section_between(text: str, start_token: str, end_token: str) -> str:
    return text.split(start_token, 1)[1].split(end_token, 1)[0]


class RuntimeSmokeStaticTest(unittest.TestCase):
    def test_runner_uses_file_backed_output_capture(self):
        text = SMOKE.read_text(encoding="utf-8")
        runner_section = text.split("def run_command(", 1)[1].split("\ndef run_checked(", 1)[0]

        self.assertIn("subprocess.Popen", runner_section)
        self.assertIn("stdout=stdout_file", runner_section)
        self.assertIn("stderr=stderr_file", runner_section)
        self.assertIn("terminate_process_tree(process)", runner_section)
        self.assertIn("safe_unlink(stdout_path)", runner_section)
        self.assertNotIn("capture_output=True", runner_section)
        self.assertIn("ignore_cleanup_errors=True", text)

    def test_ci_runtime_step_has_hard_timeout_and_discovers_static_tests(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("permissions:", text)
        self.assertIn("contents: read", text)
        self.assertIn("uses: actions/checkout@v6", text)
        self.assertIn("uses: actions/setup-python@v6", text)
        self.assertIn("python -m unittest discover -s tests", text)
        self.assertIn("timeout-minutes: 5", text)
        self.assertIn("smoke_run:", text)
        self.assertIn("--proxy-mode system", text)
        self.assertIn("--exercise-install --exercise-cert", text)
        self.assertIn("Install GNOME proxy runtime dependencies", text)
        self.assertIn("gsettings-desktop-schemas", text)
        self.assertIn("dconf-gsettings-backend", text)
        self.assertIn("dbus-run-session -- python tests/runtime_smoke.py --entrypoint shell --proxy-mode system", text)

    def test_shell_proxy_restore_replays_saved_fields_even_outside_manual_mode(self):
        start_section = section_between(
            START_CAPTURE.read_text(encoding="utf-8"),
            "restore_gnome_proxy() {",
            "\nPROGRAM_MODE=false",
        )
        stop_section = section_between(
            STOP_CAPTURE.read_text(encoding="utf-8"),
            "restore_gnome_proxy() {",
            "\nstop_pid() {",
        )

        for section in (start_section, stop_section):
            self.assertIn('gsettings set org.gnome.system.proxy.http host "$http_host"', section)
            self.assertIn('gsettings set org.gnome.system.proxy.http port "$http_port"', section)
            self.assertIn('gsettings set org.gnome.system.proxy.https host "$https_host"', section)
            self.assertIn('gsettings set org.gnome.system.proxy.https port "$https_port"', section)
            self.assertNotIn('if [[ "$effective_mode" == "manual" ]]', section)
