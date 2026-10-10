import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fixtures import NORD, toml

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "bin" / "swaysweeper"


def run(*args):
    return subprocess.run([str(LAUNCHER), *args], capture_output=True, text=True, timeout=30)


class CheckColors(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "colors.gen.toml"

    def tearDown(self):
        self.dir.cleanup()

    def test_good_file_exits_zero(self):
        self.path.write_text(toml(NORD))
        r = run("--check-colors", str(self.path))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_bad_file_exits_one_naming_the_slot(self):
        self.path.write_text(toml(dict(NORD, num3="#bf616a")))
        r = run("--check-colors", str(self.path))
        self.assertEqual(r.returncode, 1)
        self.assertIn("num3", r.stderr)

    def test_missing_argument_is_a_usage_error(self):
        self.assertEqual(run("--check-colors").returncode, 2)

    def test_check_never_imports_gi(self):
        self.path.write_text(toml(NORD))
        code = ("import sys; sys.modules['gi'] = None; "
                "from swaysweeper.cli import main; "
                f"sys.exit(main(['--check-colors', {str(self.path)!r}]))")
        r = subprocess.run(["/usr/bin/python3", "-c", code], cwd=ROOT,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
