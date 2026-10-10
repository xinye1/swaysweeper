import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.fixtures import NORD, toml

ROOT = Path(__file__).resolve().parent.parent
ID = "io.github.xinye1.swaysweeper"


class Install(unittest.TestCase):
    def test_install_into_a_fake_home(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            subprocess.run(["make", "-C", str(ROOT), "install"], env=env, check=True,
                           capture_output=True, text=True)
            desktop = Path(home, ".local/share/applications", f"{ID}.desktop").read_text()
            exec_line = next(l for l in desktop.splitlines() if l.startswith("Exec="))
            self.assertEqual(exec_line, f"Exec={home}/.local/bin/swaysweeper")
            self.assertIn("Categories=Game;LogicGame;", desktop)
            self.assertIn("Keywords=minesweeper;mines;game;", desktop)

            # The installed launcher runs from outside the repo, from its own copy.
            colours = Path(home, "c.toml")
            colours.write_text(toml(NORD))
            r = subprocess.run([f"{home}/.local/bin/swaysweeper", "--check-colors", str(colours)],
                               env=env, cwd=home, capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)

            subprocess.run(["make", "-C", str(ROOT), "uninstall"], env=env, check=True,
                           capture_output=True)
            self.assertFalse(Path(home, ".local/bin/swaysweeper").exists())
            self.assertFalse(Path(home, ".local/share/swaysweeper").exists())


if __name__ == "__main__":
    unittest.main()
