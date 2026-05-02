import json
import tempfile
from pathlib import Path
import unittest

import ai_brief


class AiBriefTest(unittest.TestCase):
    def test_main_accepts_utf8_bom_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "capture.manifest.json"
            index_path = root / "capture.index.ndjson"
            ai_json_path = root / "capture.ai.json"
            ai_md_path = root / "capture.ai.md"

            manifest_path.write_text(
                json.dumps(
                    {
                        "runId": "run-1",
                        "startedAt": "2026-05-02T23:37:44Z",
                        "stoppedAt": "2026-05-02T23:37:58Z",
                        "programMode": True,
                        "listen": {"host": "127.0.0.1", "port": 18080},
                        "files": {
                            "flow": "capture.flow",
                            "har": "capture.har",
                            "index": "capture.index.ndjson",
                            "summary": "capture.summary.md",
                            "manifest": "capture.manifest.json",
                        },
                    }
                ),
                encoding="utf-8-sig",
            )
            index_path.write_text(
                json.dumps(
                    {
                        "id": 1,
                        "method": "GET",
                        "host": "127.0.0.1",
                        "path": "/ci-smoke?answer=42",
                        "status": 200,
                        "durationMs": 3,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            rc = ai_brief.main(
                [
                    "ai_brief.py",
                    str(manifest_path),
                    str(index_path),
                    str(ai_json_path),
                    str(ai_md_path),
                ]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(ai_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["capture"]["runId"], "run-1")
            self.assertEqual(payload["files"]["manifest"], "capture.manifest.json")
            self.assertIn("/ci-smoke", ai_md_path.read_text(encoding="utf-8"))
