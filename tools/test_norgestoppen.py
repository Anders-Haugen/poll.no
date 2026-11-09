import unittest
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import requests
from bs4 import BeautifulSoup

from sync_norgestoppen import apply_samlag, fetch_events, fetch_results, fetch_tracker_events, get_page, parse_results, parse_samlag_clubs, refresh_samlag, result_events, update_archive


class ResultTests(unittest.TestCase):
    def test_samlag_directory_maps_official_club_numbers(self):
        page = BeautifulSoup("""
            <h1>Akershus Skyttersamlag</h1>
            <table><tr><th>Nummer</th><th>Skytterlag</th><th>Leder</th></tr>
            <tr><td>10077</td><td>Blaker</td><td>Navn</td></tr>
            <tr><td>10078</td><td>Eidsvoll Verk</td><td>Navn</td></tr></table>
        """, "html.parser")
        self.assertEqual(parse_samlag_clubs(page), {"10077": "Akershus", "10078": "Akershus"})

    def test_samlag_is_added_to_results_by_club_id(self):
        records = [{"clubId": "10077"}, {"clubId": "unknown", "samlag": "Old value"}]
        apply_samlag(records, {"10077": "Akershus"})
        self.assertEqual(records, [{"clubId": "10077", "samlag": "Akershus"}, {"clubId": "unknown"}])

    def test_refresh_samlag_updates_existing_payloads(self):
        import sync_norgestoppen

        with TemporaryDirectory() as directory:
            current = Path(directory) / "current.json"
            archive = Path(directory) / "archive.json"
            for path in (current, archive):
                path.write_text(json.dumps({
                    "results": [{"clubId": "10077"}],
                    "trackerResults": [{"clubId": "10078"}],
                }), encoding="utf-8")
            with patch("sync_norgestoppen.OUTPUT", current), patch(
                "sync_norgestoppen.ARCHIVE_OUTPUT", archive
            ), patch("sync_norgestoppen.fetch_samlag_clubs", return_value={
                "10077": "Akershus", "10078": "Opland",
            }):
                refresh_samlag()
            payload = json.loads(archive.read_text(encoding="utf-8"))
        self.assertEqual(payload["results"][0]["samlag"], "Akershus")
        self.assertEqual(payload["trackerResults"][0]["samlag"], "Opland")

    def test_session_retries_transient_errors_for_get_and_pagination_post(self):
        import sync_norgestoppen
        from urllib3.exceptions import ReadTimeoutError

        with sync_norgestoppen.create_session() as session:
            self.assertIn("poll.no", session.headers["User-Agent"])
            retries = session.get_adapter("https://mittdfs.no").max_retries
            for method in ("GET", "POST"):
                self.assertIn(method, retries.allowed_methods)
                self.assertTrue(retries.is_retry(method, 503))
                remaining = retries.increment(method, "/", error=ReadTimeoutError(None, "/", "timed out"))
                self.assertEqual(remaining.total, retries.total - 1)
            self.assertFalse(retries.is_retry("GET", 404))
            self.assertGreater(retries.total, 0)
            self.assertLessEqual(retries.total, 3)

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
        self.assertEqual([event["id"] for event in result_events(page, event_type="INIK")], ["5"])

    def test_internal_non_classifying_filter_survives_pagination(self):
        initial = BeautifulSoup('<select name="uxddlYear"><option value="2026">2026</option></select>', "html.parser")
        first = BeautifulSoup(str(initial) + '<table><tr><td></td><td>10.10.26</td><td><a href="?eventId=1">Test</a></td><td>Lag</td><td>Inne - ikke kl.sett</td><td>1</td><td></td></tr></table><a href="javascript:__doPostBack(\'pager\',\'next\')">Neste</a>', "html.parser")
        second = BeautifulSoup(str(initial) + '<table><tr><td></td><td>11.10.26</td><td><a href="?eventId=2">Test</a></td><td>Lag</td><td>Inne - ikke kl.sett</td><td>1</td><td></td></tr></table>', "html.parser")
        with patch("sync_norgestoppen.get_page", side_effect=[initial, first]) as get, patch("sync_norgestoppen.submit_form", return_value=second) as submit:
            events = fetch_events(requests.Session(), date(2026, 10, 1), date(2026, 10, 31), "INIK", True)
        self.assertEqual([event["id"] for event in events], ["1", "2"])
        query = parse_qs(urlsplit(get.call_args.args[1]).query)
        self.assertEqual(query["type"], ["INIK"])
        self.assertEqual(query["includeLocal"], ["True"])
        self.assertEqual(submit.call_args.args[3]["ctl00$FullRegion$uxListView$uxIncludeLocalEvents"], "on")

    def test_tracker_event_flags_cover_internal_and_non_classifying_overlap(self):
        official = [{"id": "official"}]
        internal = {"id": "internal", "type": "Inne"}
        non_classifying = {"id": "non-classifying", "type": "Inne - ikke kl.sett"}
        internal_non_classifying = {"id": "internal-non-classifying", "type": "Inne - ikke kl.sett"}
        with patch("sync_norgestoppen.fetch_events", side_effect=[
            [*official, internal],
            [non_classifying],
            [non_classifying, internal_non_classifying],
        ]):
            events = fetch_tracker_events(requests.Session(), official)
        self.assertEqual(
            {event["id"]: (event["internal"], event["classifying"]) for event in events},
            {
                "internal": (True, True),
                "non-classifying": (False, False),
                "internal-non-classifying": (True, False),
            },
        )

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

    def test_fetch_selects_indoor_when_unknown_exercise_is_default(self):
        event = {"id": "123", "name": "Test", "url": "https://mittdfs.no/?eventId=123"}
        initial = BeautifulSoup('<a href="?eventId=123&class=5">Klasse 5</a>', "html.parser")
        unknown = BeautifulSoup('<select name="details$uxddlExercises"><option selected value="None">Ukjent</option><option value="Innendors">Innend</option></select>', "html.parser")
        indoor = BeautifulSoup('<table id="indoor"></table>', "html.parser")
        with patch("sync_norgestoppen.get_page", side_effect=[initial, unknown]), patch(
            "sync_norgestoppen.submit_form", return_value=indoor
        ) as submit, patch("sync_norgestoppen.parse_results", return_value=[{"score": 250}]) as parse:
            records = fetch_results(requests.Session(), event)
        self.assertEqual(records, [{"score": 250}])
        self.assertEqual(submit.call_args.args[3], {
            "__EVENTTARGET": "details$uxddlExercises", "details$uxddlExercises": "Innendors",
        })
        self.assertIs(submit.call_args.args[2], unknown)
        self.assertIs(parse.call_args.args[0], indoor)

    def test_fetch_does_not_resubmit_selected_indoor_exercise(self):
        event = {"id": "123", "name": "Test", "url": "https://mittdfs.no/?eventId=123"}
        initial = BeautifulSoup('<a href="?eventId=123&class=5">Klasse 5</a>', "html.parser")
        indoor = BeautifulSoup('<select name="details$uxddlExercises"><option selected value="Innendors">Innend</option></select>', "html.parser")
        with patch("sync_norgestoppen.get_page", side_effect=[initial, indoor]), patch(
            "sync_norgestoppen.submit_form"
        ) as submit, patch("sync_norgestoppen.parse_results", return_value=[]):
            self.assertEqual(fetch_results(requests.Session(), event), [])
        submit.assert_not_called()

    def test_missing_result_table_still_fails(self):
        with self.assertRaisesRegex(ValueError, "Missing result table"):
            parse_results(BeautifulSoup("<html>Unexpected response</html>", "html.parser"), {"name": "Test"})

    def test_failed_sync_does_not_publish_partial_data(self):
        import sync_norgestoppen

        event = {"id": "123", "date": "2026-10-10", "name": "Test"}
        with patch("sync_norgestoppen.fetch_events", return_value=[event]), patch(
            "sync_norgestoppen.fetch_results", side_effect=requests.exceptions.Timeout("DFS timeout")
        ), patch("sync_norgestoppen.write_payload") as write, patch("sync_norgestoppen.update_archive") as archive:
            with self.assertRaises(requests.exceptions.Timeout):
                sync_norgestoppen.sync()
        write.assert_not_called()
        archive.assert_not_called()

    def test_regular_sync_marks_archive_complete_from_current_season(self):
        event = {"id": "123", "date": "2026-10-01", "type": "Inne", "name": "Test"}
        result = {"eventId": "123", "shooter": "Test", "clubId": "1", "class": "4", "exercise": "main"}
        with TemporaryDirectory() as directory, patch("sync_norgestoppen.ARCHIVE_OUTPUT", Path(directory) / "archive.json"):
            update_archive([event], [result])
            archive = json.loads((Path(directory) / "archive.json").read_text(encoding="utf-8"))
        self.assertEqual(archive["start"], "2026-10-01")
        self.assertTrue(archive["complete"])

    def test_tracker_events_are_stored_separately_from_official_archive(self):
        official = {"id": "official", "date": "2026-10-10", "type": "Inne", "name": "Official"}
        optional = {"id": "optional", "date": "2026-10-10", "type": "Inne - ikke kl.sett", "name": "Internal", "internal": True, "classifying": False}
        official_result = {"eventId": "official", "shooter": "Test", "clubId": "1", "class": "4", "exercise": "main"}
        optional_result = {"eventId": "optional", "shooter": "Test", "clubId": "1", "class": "4", "exercise": "main"}
        with TemporaryDirectory() as directory, patch("sync_norgestoppen.ARCHIVE_OUTPUT", Path(directory) / "archive.json"):
            path = Path(directory) / "archive.json"
            update_archive([official], [official_result], [optional], [optional_result])
            archive = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([event["id"] for event in archive["events"]], ["official"])
        self.assertEqual([result["eventId"] for result in archive["results"]], ["official"])
        self.assertEqual([event["id"] for event in archive["trackerEvents"]], ["optional"])
        self.assertEqual([result["eventId"] for result in archive["trackerResults"]], ["optional"])

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