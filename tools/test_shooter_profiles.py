import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests
from bs4 import BeautifulSoup

from sync_shooter_profiles import merge_profiles, parse_profiles, sync


SOURCE = "https://sorlandskula.one/sammenlagt/2026/index?view=sammenlagt&klasse=ALLE"


class ShooterProfileTests(unittest.TestCase):
    def test_extracts_name_club_and_public_id(self):
        page = BeautifulSoup("""
            <details class="result-card">
              <span class="r-name">Test Skyttar</span>
              <div class="r-line2">Test Skytterlag, Kl. 5</div>
              <img src="https://skytterbilder.no/bilder/1234567.jpg">
            </details>
        """, "html.parser")
        self.assertEqual(parse_profiles(page, SOURCE), [{
            "shooter": "Test Skyttar", "club": "Test Skytterlag",
            "shooterId": "1234567", "source": SOURCE,
        }])

    def test_missing_cards_or_invalid_image_source_fails(self):
        for html in (
            "<html>No results</html>",
            '<div class="result-card"><span class="r-name">Test</span>'
            '<div class="r-line2">Test</div><img src="https://other.example/123.jpg"></div>',
        ):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_profiles(BeautifulSoup(html, "html.parser"), SOURCE)

    def test_merge_retains_verified_profiles_and_conflicting_ids(self):
        original = {"shooter": "Test Skyttar", "club": "Test", "shooterId": "123", "source": "verified"}
        same = {**original, "club": "TEST Skytterlag", "source": SOURCE}
        conflict = {**same, "shooterId": "456"}
        retained = {**original, "shooter": "Other", "shooterId": "789"}
        merged = merge_profiles([original, retained], [same, conflict])
        self.assertEqual(len(merged), 3)
        self.assertIn(retained, merged)
        self.assertEqual({p["shooterId"] for p in merged}, {"123", "456", "789"})

    def test_failed_fetch_preserves_existing_file(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "profiles.json"
            previous = '{"profiles": []}'
            output.write_text(previous, encoding="utf-8")
            with patch("sync_shooter_profiles.PROFILE_OUTPUT", output), patch(
                "sync_shooter_profiles.create_session"
            ) as session:
                session.return_value.__enter__.return_value.get.side_effect = requests.ConnectionError("Offline")
                with self.assertRaises(requests.ConnectionError):
                    sync()
            self.assertEqual(output.read_text(encoding="utf-8"), previous)


if __name__ == "__main__":
    unittest.main()
