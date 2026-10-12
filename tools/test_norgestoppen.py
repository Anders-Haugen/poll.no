import unittest

import requests
from bs4 import BeautifulSoup

from sync_norgestoppen import get_page, parse_results, result_events


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

    def test_live_published_result(self):
        url = "https://mittdfs.no/hovedside/aktuelt-na/resultater/?search=True&type=INNE&year=2026&includeLocal=True&eventId=262774&class=4"
        with requests.Session() as session:
            records = parse_results(get_page(session, url), {"id": "262774", "name": "Oktoberstevne 1 2026"})
        self.assertEqual(len(records), 4)
        main = next(record for record in records if record["shooter"] == "Jim R Aronsen" and record["exercise"] == "main")
        self.assertEqual((main["score"], main["inner"], main["class"]), (241, 7, "4"))


if __name__ == "__main__":
    unittest.main()