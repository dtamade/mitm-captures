from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "windows_cert_install.py"


class WindowsCertInstallHelperTest(unittest.TestCase):
    def test_helper_uses_system_store_api_and_pem_fallback(self):
        text = HELPER.read_text(encoding="utf-8")

        for token in [
            "CertAddEncodedCertificateToSystemStoreA",
            'b"ROOT"',
            "ssl.PEM_cert_to_DER_cert",
            'sys.platform != "win32"',
        ]:
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
