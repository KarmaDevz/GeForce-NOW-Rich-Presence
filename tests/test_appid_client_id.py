import unittest
from types import SimpleNamespace

from src.core.presence_manager import PresenceManager

WITCHER_ID = "359510249486417920"


def find(games_map, title, appid):
    return PresenceManager._find_client_id_by_appid(SimpleNamespace(games_map=games_map), title, appid)


class TestFindClientIdByAppid(unittest.TestCase):

    def setUp(self):
        self.games_map = {
            "The Witcher 3: Wild Hunt": {"steam_appid": 292030, "client_id": WITCHER_ID},
            "The Witcher 3 REDkit": {"steam_appid": None, "client_id": "1327290894918877259"},
            "Dark Souls: Prepare to Die Edition": {"steam_appid": 211420, "client_id": "1"},
        }

    def test_edition_suffix_reuses_known_client_id(self):
        # find_steam_appid_by_name returns the AppID as a string
        self.assertEqual(find(self.games_map, "The Witcher 3: Wild Hunt — Remastered", "292030"), WITCHER_ID)

    def test_different_appid_is_not_reused(self):
        # Dark Souls Remastered is a separate Steam app
        self.assertIsNone(find(self.games_map, "DARK SOULS: REMASTERED", "570940"))

    def test_wrong_appid_with_unrelated_name_is_not_reused(self):
        self.assertIsNone(find(self.games_map, "Some Other Game", "292030"))

    def test_no_appid(self):
        self.assertIsNone(find(self.games_map, "The Witcher 3: Wild Hunt — Remastered", None))

    def test_entry_without_client_id_is_skipped(self):
        self.games_map["The Witcher 3: Wild Hunt"].pop("client_id")
        self.assertIsNone(find(self.games_map, "The Witcher 3: Wild Hunt — Remastered", "292030"))


if __name__ == "__main__":
    unittest.main()
