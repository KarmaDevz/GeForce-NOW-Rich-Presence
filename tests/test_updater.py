import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.updater import (
    parse_version,
    get_file_sha256,
    parse_sha256sums,
    get_installed_build,
    save_installed_build,
    get_platform_asset,
    is_build_newer_or_different,
    verify_downloaded_checksum
)

class TestUpdaterChecksumAndMetadata(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_sha256sums(self):
        sample_sums = """
        # This is a comment
        e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  GeForceNOWRichPresence-Windows.zip
        4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 *GeForceNOWRichPresence-Linux.tar.gz
        
        ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad   GeForceNOWRichPresence-macOS.zip
        """
        parsed = parse_sha256sums(sample_sums)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed.get("GeForceNOWRichPresence-Windows.zip"), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(parsed.get("GeForceNOWRichPresence-Linux.tar.gz"), "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945")
        self.assertEqual(parsed.get("GeForceNOWRichPresence-macOS.zip"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        # Exact match test (no partial match)
        self.assertIsNone(parsed.get("GeForceNOWRichPresence"))
        self.assertIsNone(parsed.get("Windows.zip"))

    def test_get_file_sha256(self):
        test_file = self.test_dir / "sample.txt"
        test_file.write_bytes(b"hello world")
        # SHA256 of "hello world" is b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
        expected_hash = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        self.assertEqual(get_file_sha256(test_file), expected_hash)

    def test_save_and_get_installed_build_atomic(self):
        json_path = self.test_dir / "installed_build.json"
        data = {
            "version": "3.3.2",
            "asset_name": "GeForceNOWRichPresence-Windows.zip",
            "asset_id": 123456,
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "size": 1024,
            "updated_at": "2026-08-26T17:00:00Z"
        }
        success = save_installed_build(data, file_path=json_path)
        self.assertTrue(success)
        self.assertTrue(json_path.exists())

        loaded = get_installed_build(file_path=json_path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["version"], "3.3.2")
        self.assertEqual(loaded["sha256"], data["sha256"])

    def test_get_installed_build_corrupt_or_missing(self):
        # 1. Missing
        missing_path = self.test_dir / "does_not_exist.json"
        self.assertIsNone(get_installed_build(file_path=missing_path))

        # 2. Corrupt
        corrupt_path = self.test_dir / "corrupt.json"
        corrupt_path.write_text("{ this is invalid json !!!", encoding="utf-8")
        self.assertIsNone(get_installed_build(file_path=corrupt_path))

    def test_newer_version_triggers_update(self):
        release_data = {
            "tag_name": "v3.4.0",
            "assets": [{"name": "GeForceNOWRichPresence-Windows.zip", "id": 101, "updated_at": "2026-08-26T18:00:00Z"}]
        }
        platform_asset = release_data["assets"][0]
        should_update, reason = is_build_newer_or_different(
            current_version_str="v3.3.2",
            installed_build=None,
            release_data=release_data,
            platform_asset=platform_asset,
            remote_sha256="some_remote_hash"
        )
        self.assertTrue(should_update)
        self.assertEqual(reason, "newer_version")

    def test_same_version_same_sha_no_update(self):
        release_data = {
            "tag_name": "v3.3.2",
            "assets": [{"name": "GeForceNOWRichPresence-Windows.zip", "id": 101, "updated_at": "2026-08-26T18:00:00Z"}]
        }
        platform_asset = release_data["assets"][0]
        installed_build = {
            "version": "3.3.2",
            "asset_name": "GeForceNOWRichPresence-Windows.zip",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
        should_update, reason = is_build_newer_or_different(
            current_version_str="v3.3.2",
            installed_build=installed_build,
            release_data=release_data,
            platform_asset=platform_asset,
            remote_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        self.assertFalse(should_update)
        self.assertEqual(reason, "same_build")

    def test_same_version_different_sha_triggers_hotfix_update(self):
        release_data = {
            "tag_name": "v3.3.2",
            "assets": [{"name": "GeForceNOWRichPresence-Windows.zip", "id": 101, "updated_at": "2026-08-26T18:00:00Z"}]
        }
        platform_asset = release_data["assets"][0]
        installed_build = {
            "version": "3.3.2",
            "asset_name": "GeForceNOWRichPresence-Windows.zip",
            "sha256": "old_hash_111111111111111111111111111111111111111111111111111111111111"
        }
        new_remote_sha = "new_hash_222222222222222222222222222222222222222222222222222222222222"
        should_update, reason = is_build_newer_or_different(
            current_version_str="v3.3.2",
            installed_build=installed_build,
            release_data=release_data,
            platform_asset=platform_asset,
            remote_sha256=new_remote_sha
        )
        self.assertTrue(should_update)
        self.assertEqual(reason, "hotfix_hash_mismatch")

    def test_sha_priority_over_metadata(self):
        # Even if asset_id and updated_at match, a different SHA MUST trigger update
        release_data = {
            "tag_name": "v3.3.2",
            "assets": [{"name": "GeForceNOWRichPresence-Windows.zip", "id": 101, "updated_at": "2026-08-26T18:00:00Z"}]
        }
        platform_asset = release_data["assets"][0]
        installed_build = {
            "version": "3.3.2",
            "asset_name": "GeForceNOWRichPresence-Windows.zip",
            "asset_id": 101,
            "updated_at": "2026-08-26T18:00:00Z",
            "sha256": "old_hash_111111111111111111111111111111111111111111111111111111111111"
        }
        new_remote_sha = "new_hash_222222222222222222222222222222222222222222222222222222222222"
        should_update, reason = is_build_newer_or_different(
            current_version_str="v3.3.2",
            installed_build=installed_build,
            release_data=release_data,
            platform_asset=platform_asset,
            remote_sha256=new_remote_sha
        )
        self.assertTrue(should_update)
        self.assertEqual(reason, "hotfix_hash_mismatch")

    def test_metadata_fallback_when_sha_absent(self):
        # When remote_sha256 is None, compare metadata (id / updated_at)
        release_data = {
            "tag_name": "v3.3.2",
            "assets": [{"name": "GeForceNOWRichPresence-Windows.zip", "id": 202, "updated_at": "2026-08-26T20:00:00Z"}]
        }
        platform_asset = release_data["assets"][0]
        installed_build = {
            "version": "3.3.2",
            "asset_name": "GeForceNOWRichPresence-Windows.zip",
            "asset_id": 101,
            "updated_at": "2026-08-26T18:00:00Z"
        }
        should_update, reason = is_build_newer_or_different(
            current_version_str="v3.3.2",
            installed_build=installed_build,
            release_data=release_data,
            platform_asset=platform_asset,
            remote_sha256=None
        )
        self.assertTrue(should_update)
        self.assertEqual(reason, "metadata_changed")

    def test_metadata_fallback_no_change(self):
        release_data = {
            "tag_name": "v3.3.2",
            "assets": [{"name": "GeForceNOWRichPresence-Windows.zip", "id": 101, "updated_at": "2026-08-26T18:00:00Z"}]
        }
        platform_asset = release_data["assets"][0]
        installed_build = {
            "version": "3.3.2",
            "asset_name": "GeForceNOWRichPresence-Windows.zip",
            "asset_id": 101,
            "updated_at": "2026-08-26T18:00:00Z"
        }
        should_update, reason = is_build_newer_or_different(
            current_version_str="v3.3.2",
            installed_build=installed_build,
            release_data=release_data,
            platform_asset=platform_asset,
            remote_sha256=None
        )
        self.assertFalse(should_update)
        self.assertEqual(reason, "same_build")

    def test_verify_downloaded_checksum_valid_and_invalid(self):
        test_file = self.test_dir / "downloaded_test.zip"
        test_file.write_bytes(b"download content payload")
        actual_hash = get_file_sha256(test_file)

        # 1. Valid hash
        self.assertTrue(verify_downloaded_checksum(test_file, actual_hash))
        self.assertTrue(verify_downloaded_checksum(test_file, actual_hash.upper()))

        # 2. Invalid / corrupted hash
        self.assertFalse(verify_downloaded_checksum(test_file, "0000000000000000000000000000000000000000000000000000000000000000"))

        # 3. None / Empty expected hash (passes with warning)
        self.assertTrue(verify_downloaded_checksum(test_file, None))
        self.assertTrue(verify_downloaded_checksum(test_file, ""))

if __name__ == "__main__":
    unittest.main()
