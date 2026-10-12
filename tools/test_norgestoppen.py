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

    def test_parses_prize_and_medal(self):
        page = BeautifulSoup("""
            <table>
              <tr><th>Skytter</th><th>Klasse</th><th>Skytterlag</th><th>Hoved (pl.)</th>
                  <th>Finale (pl.)</th><th>Medalje</th><th>Premie</th></tr>
              <tr><td>Anders Haugen</td><td>5</td><td>Lom og Skjåk</td><td>248 (2)</td>
                  <td>347 (2)</td><td>Sølv medalje</td><td>259 [+]</td></tr>
            </table>
        """, "html.parser")
        records = parse_results(page, {"id": "1", "name": "Høststevnet"})
        self.assertEqual(len(records), 2)
        main = next(record for record in records if record["exercise"] == "main")
        final = next(record for record in records if record["exercise"] == "final")
        self.assertEqual((main["prize"], main["medal"]), (259, "Sølv medalje"))
        self.assertNotIn("prize", final)
        self.assertNotIn("medal", final)


if __name__ == "__main__":
    unittest.main()