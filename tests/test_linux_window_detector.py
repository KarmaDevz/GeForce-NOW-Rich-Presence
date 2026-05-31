import unittest

from src.core.linux_window_detector import LinuxWindowDetector


class LinuxWindowDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = LinuxWindowDetector()

    def test_extract_suffix_title(self):
        self.assertEqual(self.detector.extract_game_name("Rocket League - GeForce NOW"), "Rocket League")

    def test_extract_prefix_title(self):
        self.assertEqual(self.detector.extract_game_name("GeForce NOW - Subnautica 2"), "Subnautica 2")

    def test_lobby_title_has_no_game(self):
        self.assertIsNone(self.detector.extract_game_name("GeForce NOW"))


if __name__ == "__main__":
    unittest.main()
