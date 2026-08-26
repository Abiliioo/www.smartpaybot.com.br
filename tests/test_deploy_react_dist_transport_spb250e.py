from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "deploy-production.ps1"


class DeployReactDistTransportSPB250ETest(unittest.TestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8")

    def test_react_dist_wrapper_is_normalized_to_lf_before_base64_encoding(self):
        self.assertIn("function ConvertTo-LfText", self.script)
        self.assertIn('$remoteWrapperLf = ConvertTo-LfText $remoteWrapper', self.script)
        self.assertIn("[System.Text.Encoding]::UTF8.GetBytes($remoteWrapperLf)", self.script)
        self.assertNotIn("[System.Text.Encoding]::UTF8.GetBytes($remoteWrapper))", self.script)

    def test_react_dist_transport_security_options_are_preserved(self):
        self.assertIn("-ValidateReactDistOnly", self.script)
        self.assertIn('"BatchMode=yes"', self.script)
        self.assertIn('"ConnectTimeout=15"', self.script)
        self.assertIn('"StrictHostKeyChecking=yes"', self.script)
        self.assertNotIn("StrictHostKeyChecking=no", self.script)
        self.assertNotIn('"-o", "UserKnownHostsFile=/dev/null"', self.script)
