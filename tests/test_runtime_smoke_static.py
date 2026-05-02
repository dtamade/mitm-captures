from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "tests" / "runtime_smoke.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class RuntimeSmokeStaticTest(unittest.TestCase):
    def test_runner_uses_file_backed_output_capture(self):
        text = SMOKE.read_text(encoding="utf-8")

        self.assertIn("subprocess.Popen", text)
        self.assertIn("stdout=stdout_file", text)
        self.assertIn("stderr=stderr_file", text)
        self.assertIn("terminate_process_tree(process)", text)
        self.assertIn("safe_unlink(stdout_path)", text)
        self.assertIn("ignore_cleanup_errors=True", text)
        self.assertNotIn("capture_output=True", text)

    def test_ci_runtime_step_has_hard_timeout_and_discovers_static_tests(self):
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("permissions:", text)
        self.assertIn("contents: read", text)
        self.assertIn("uses: actions/checkout@v6", text)
        self.assertIn("uses: actions/setup-python@v6", text)
        self.assertIn("python -m unittest discover -s tests", text)
        self.assertIn("timeout-minutes: 5", text)
        self.assertIn("python tests/runtime_smoke.py --entrypoint ${{ matrix.entrypoint }}", text)
