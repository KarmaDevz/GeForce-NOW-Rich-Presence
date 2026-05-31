import tempfile
import unittest
from pathlib import Path

from src.core.linux_gfn_log import game_from_native_log, parse_native_log_text


START_ROCKET = "2026-05-31T11:49:56.467[I] GfnAppInfo.cpp:680  onStreamStart Inserted processInfo processId:100871611 name: type:0 parentProcessId:0 drsAppName:Rocket League® drsProfileName:Rocket League® shortName:rocket_league_egs cmsId:100871611 chromaName: isDistributor=0"
STOP_ROCKET = "2026-05-31T11:53:01.459[I] GfnAppInfo.cpp:692  onStreamStop processId:100871611 erased from processMap"
START_SUBNAUTICA = "2026-05-31T13:34:07.464[I] GfnAppInfo.cpp:680  onStreamStart Inserted processInfo processId:107647091 name: type:0 parentProcessId:0 drsAppName:Subnautica 2 drsProfileName:Subnautica 2 shortName:afba7bfc cmsId:107647091 chromaName: isDistributor=0"


class LinuxGfnLogTests(unittest.TestCase):
    def test_parse_active_stream(self):
        self.assertEqual(parse_native_log_text(START_ROCKET), ("100871611", "Rocket League®"))

    def test_parse_stopped_stream_returns_none(self):
        self.assertEqual(parse_native_log_text(START_ROCKET + "\n" + STOP_ROCKET), (None, None))

    def test_latest_active_stream_wins(self):
        text = START_ROCKET + "\n" + START_SUBNAUTICA
        self.assertEqual(parse_native_log_text(text), ("107647091", "Subnautica 2"))

    def test_game_from_native_log_prefers_mapped_name(self):
        games = {"Rocket League": {"cmsId": "100871611", "name": "Rocket League"}}
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "CxNative_GeForceNOW.log"
            log_path.write_text(START_ROCKET, encoding="utf-8")
            self.assertEqual(game_from_native_log(games, log_path), ("Rocket League", log_path))


if __name__ == "__main__":
    unittest.main()
