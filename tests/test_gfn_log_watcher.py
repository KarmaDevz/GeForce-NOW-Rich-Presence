import os
import tempfile
import unittest
from pathlib import Path

from src.core.gfn_log_watcher import GfnLogWatcher

TS = "2026-10-13 17:26:19.891"


def launch(name, glued=False):
    # glued=True reproduces GFN's byte-length truncation: no "]" and no newline
    line = f"{TS} INFO  ApplicationClass  Launch game {name} [c1c453f2-c853-4e7c-b703-76a44f0efd00"
    return line if glued else line + "] \n"


def state(name):
    return f"{TS} INFO  gfn/StreamerManagerService  Advancing to state: {name} \n"


class TestGfnLogWatcher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log = Path(self.temp_dir.name) / "console.log"
        self.watcher = GfnLogWatcher([self.log])

    def tearDown(self):
        self.temp_dir.cleanup()

    def append(self, text):
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(text)

    def test_missing_file(self):
        self.assertIsNone(self.watcher.active_title())

    def test_streaming_lifecycle(self):
        self.append(launch("American Truck Simulator") + state("Loading"))
        self.assertIsNone(self.watcher.active_title())

        self.append(state("Streaming"))
        self.assertEqual(self.watcher.active_title(), "American Truck Simulator")

        self.append(state("PostSessionConnection") + state("PostStreaming") + state("Done"))
        self.assertIsNone(self.watcher.active_title())

    def test_new_launch_replaces_previous_game(self):
        self.append(launch("Game A") + state("Streaming") + state("Done"))
        self.append(launch("Game B") + state("Loading") + state("Streaming"))
        self.assertEqual(self.watcher.active_title(), "Game B")

    def test_truncated_glued_line(self):
        self.append(launch("The Witcher® 3: Wild Hunt — Remastered", glued=True))
        self.append(f"{TS} INFO  ApplicationClass  User is Online \n")
        self.append(state("Loading") + state("Streaming"))
        self.assertEqual(self.watcher.active_title(), "The Witcher® 3: Wild Hunt — Remastered")

    def test_partial_line_between_polls(self):
        full = launch("Hades") + state("Streaming")
        split = full.index("Hades") + 2
        self.append(full[:split])
        self.assertIsNone(self.watcher.active_title())
        self.append(full[split:])
        self.assertEqual(self.watcher.active_title(), "Hades")

    def test_rotation_resets_state(self):
        self.append(launch("Old Game") + state("Streaming"))
        self.assertEqual(self.watcher.active_title(), "Old Game")

        # GFN restart: console.log is moved to .bak and a new file is created
        os.replace(self.log, self.log.with_suffix(".log.bak"))
        self.append("x" * 10 + "\n")
        self.assertIsNone(self.watcher.active_title())

    def test_truncation_resets_state(self):
        self.append(launch("Old Game") + state("Streaming"))
        self.assertEqual(self.watcher.active_title(), "Old Game")
        self.log.write_text("")
        self.assertIsNone(self.watcher.active_title())


if __name__ == "__main__":
    unittest.main()
