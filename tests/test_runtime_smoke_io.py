from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "tests" / "runtime_smoke.py"
SPEC = importlib.util.spec_from_file_location("runtime_smoke_module", SMOKE_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNTIME_SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME_SMOKE)


class Cp1252Stream:
    encoding = "cp1252"

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, text: str) -> int:
        payload = text.encode(self.encoding)
        self.buffer.write(payload)
        return len(text)

    def flush(self) -> None:
        return


class RuntimeSmokeIoTest(unittest.TestCase):
    def test_emit_text_strips_utf8_bom_before_console_write(self):
        stream = Cp1252Stream()

        RUNTIME_SMOKE.emit_text(stream, "Bundle written\n\ufeff# AI Analysis Bundle\n")

        self.assertEqual(
            stream.buffer.getvalue().decode("cp1252"),
            "Bundle written\n# AI Analysis Bundle\n",
        )
