import unittest
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests
from bs4 import BeautifulSoup

from sync_norgestoppen import fetch_results, get_page, parse_results, result_events, update_archive


class ResultTests(unittest.TestCase):
    def test_season_and_indoor_type(self):
        rows = []
        for index, (event_date, event_type) in enumerate([
            ("30.09.26", "Inne"), ("01.10.26", "Inne"),
            ("01.10.27", "Inne - ikke kl.sett"), ("02.10.27", "Inne"),
            ("10.10.26", "Bane"),
        ]):
            rows.append(f'<tr><td></td><td>{event_date}</td><td><a href="?eventId={index}">Test</a></td><td>Lag</td><td>{event_type}</td><td>1</td><td></td></tr>')
        page = BeautifulSoup("<table>" + "".join(rows) + "</table>", "html.parser")
        self.assertEqual([event["id"] for event in result_events(page)], ["1", "2"])

    def test_historical_date_range(self):
        rows = []
        for index, event_date in enumerate(("01.10.24", "01.10.25", "01.10.26")):
            rows.append(f'<tr><td></td><td>{event_date}</td><td><a href="?eventId={index}">Test</a></td><td>Lag</td><td>Inne</td><td>1</td><td></td></tr>')
        page = BeautifulSoup("<table>" + "".join(rows) + "</table>", "html.parser")
        events = result_events(page, date(2025, 10, 1), date(2026, 10, 1))
        self.assertEqual([event["id"] for event in events], ["1", "2"])

    def test_event_without_class_links_has_no_results(self):
        with patch("sync_norgestoppen.get_page", return_value=BeautifulSoup("<html></html>", "html.parser")):
            self.assertEqual(fetch_results(requests.Session(), {"id": "123", "name": "Test", "url": "https://mittdfs.no"}), [])

    def test_regular_sync_marks_archive_complete_from_current_season(self):
        event = {"id": "123", "date": "2026-10-01", "type": "Inne", "name": "Test"}
        result = {"eventId": "123", "shooter": "Test", "clubId": "1", "class": "4", "exercise": "main"}
        with TemporaryDirectory() as directory, patch("sync_norgestoppen.ARCHIVE_OUTPUT", Path(directory) / "archive.json"):
            update_archive([event], [result])
            archive = json.loads((Path(directory) / "archive.json").read_text(encoding="utf-8"))
        self.assertEqual(archive["start"], "2026-10-01")
        self.assertTrue(archive["complete"])

    def test_live_published_result(self):
        url = "https://mittdfs.no/hovedside/aktuelt-na/resultater/?search=True&type=INNE&year=2026&includeLocal=True&eventId=262774&class=4"
        with requests.Session() as session:
            records = parse_results(get_page(session, url), {"id": "262774", "name": "Oktoberstevne 1 2026"})
        self.assertEqual(len(records), 4)
        main = next(record for record in records if record["shooter"] == "Jim R Aronsen" and record["exercise"] == "main")
        self.assertEqual((main["score"], main["inner"], main["class"]), (241, 7, "4"))


if __name__ == "__main__":
    unittest.main()