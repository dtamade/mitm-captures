from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "windows_cert_install.py"


class WindowsCertInstallHelperTest(unittest.TestCase):
    def test_helper_uses_system_store_api_and_pem_fallback(self):
        text = HELPER.read_text(encoding="utf-8")

        for token in [
            "CertOpenStore",
            "CertAddEncodedCertificateToStore",
            "CERT_SYSTEM_STORE_UNPROTECTED_FLAG",
            "CERT_STORE_PROV_SYSTEM_REGISTRY_W",
            "CERT_STORE_ADD_REPLACE_EXISTING",
            "ssl.PEM_cert_to_DER_cert",
            'sys.platform != "win32"',
            "certutil.exe",
            '"-f", "-user", "-addstore", "Root"',
            "certutil-user-addstore",
            "CertMgr.exe",
            "Windows Kits/10/bin",
            "--strategy",
            "Trying certificate import strategy",
            "pwsh.exe",
            "Import-Certificate -FilePath $env:MITM_CERT",
        ]:
            self.assertIn(token, text)
        self.assertNotIn('"-silent"', text)


if __name__ == "__main__":
    unittest.main()
