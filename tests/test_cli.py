import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "bin" / "swaysweeper"


class Arguments(unittest.TestCase):
    def test_any_argument_is_a_usage_error(self):
        for args in (["--check-colors", "x.toml"], ["--help"]):
            r = subprocess.run([str(LAUNCHER), *args], capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn("usage", r.stderr)


if __name__ == "__main__":
    unittest.main()
