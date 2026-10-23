import unittest
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import requests
from bs4 import BeautifulSoup

from sync_norgestoppen import fetch_events, fetch_results, get_page, parse_results, result_events, update_archive


class ResultTests(unittest.TestCase):
    def test_season_and_indoor_type(self):
        rows = []
        for index, (event_date, event_type) in enumerate([
            ("30.09.26", "Inne"), ("01.10.26", "Inne"),
            ("01.10.27", "Inne"), ("02.10.27", "Inne"),
            ("10.10.26", "Bane"),
            ("10.10.26", "Inne - ikke kl.sett"),
        ]):
            rows.append(f'<tr><td></td><td>{event_date}</td><td><a href="?eventId={index}">Test</a></td><td>Lag</td><td>{event_type}</td><td>1</td><td></td></tr>')
        page = BeautifulSoup("<table>" + "".join(rows) + "</table>", "html.parser")
        self.assertEqual([event["id"] for event in result_events(page)], ["1", "2"])

    def test_fetch_excludes_internal_and_non_classifying_events_on_all_pages(self):
        initial = BeautifulSoup('<select name="uxddlYear"><option value="2026">2026</option></select>', "html.parser")
        first = BeautifulSoup(str(initial) + '<table><tr><td></td><td>10.10.26</td><td><a href="?eventId=1">Test</a></td><td>Lag</td><td>Inne</td><td>1</td><td></td></tr></table><a href="javascript:__doPostBack(\'pager\',\'next\')">Neste</a>', "html.parser")
        second = BeautifulSoup(str(initial) + '<table><tr><td></td><td>11.10.26</td><td><a href="?eventId=2">Test</a></td><td>Lag</td><td>Inne</td><td>1</td><td></td></tr></table>', "html.parser")
        with patch("sync_norgestoppen.get_page", side_effect=[initial, first]) as get, patch("sync_norgestoppen.submit_form", return_value=second) as submit:
            events = fetch_events(requests.Session(), date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual([event["id"] for event in events], ["1", "2"])
        query = parse_qs(urlsplit(get.call_args.args[1]).query)
        self.assertEqual(query["type"], ["INNE"])
        self.assertEqual(query["includeLocal"], ["False"])
        self.assertNotIn("ctl00$FullRegion$uxListView$uxIncludeLocalEvents", submit.call_args.args[3])

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

    def test_archive_removes_excluded_events_and_their_results(self):
        events = [
            {"id": "old", "date": "2025-10-10", "type": "Inne"},
            {"id": "internal", "date": "2026-10-10", "type": "Inne"},
            {"id": "non-classifying", "date": "2026-10-10", "type": "Inne - ikke kl.sett"},
            {"id": "allowed", "date": "2026-10-10", "type": "Inne"},
        ]
        results = [{"eventId": event["id"], "shooter": "Test", "clubId": "1", "class": "4", "exercise": "main"} for event in events]
        with TemporaryDirectory() as directory, patch("sync_norgestoppen.ARCHIVE_OUTPUT", Path(directory) / "archive.json"):
            path = Path(directory) / "archive.json"
            path.write_text(json.dumps({"start": "2025-10-01", "events": events, "results": results}), encoding="utf-8")
            update_archive([events[-1]], [results[-1]])
            archive = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([event["id"] for event in archive["events"]], ["old", "allowed"])
        self.assertEqual([result["eventId"] for result in archive["results"]], ["old", "allowed"])


if __name__ == "__main__":
    unittest.main()