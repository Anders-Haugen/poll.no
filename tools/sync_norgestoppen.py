import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://mittdfs.no"
RESULTS_URL = BASE_URL + "/hovedside/aktuelt-na/resultater/"
START = date(2026, 10, 1)
END = date(2027, 10, 1)
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "norgestoppen2.json"
ARCHIVE_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "norgestoppen_archive.json"


def get_page(session, url):
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def submit_form(session, url, page, overrides):
    fields = {}
    for field in page.select("input[name], select[name]"):
        if field.get("type") in {"submit", "button", "radio", "checkbox"}:
            continue
        selected = field.select_one("option[selected]") or field.select_one("option")
        fields[field["name"]] = selected.get("value", "") if selected else field.get("value", "")
    fields.update(overrides)
    response = session.post(url, data=fields, timeout=120)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def result_events(page, start=START, end=END):
    events = {}
    for row in page.select("table tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 7 or cells[4].get_text(strip=True) != "Inne":
            continue
        event_date = datetime.strptime(cells[1].get_text(strip=True), "%d.%m.%y").date()
        anchor = cells[2].find("a", href=True)
        if anchor and start <= event_date <= end:
            event_id = parse_qs(urlsplit(anchor["href"]).query)["eventId"][0]
            events[event_id] = {
                "id": event_id,
                "name": anchor.get_text(strip=True),
                "date": event_date.isoformat(),
                "type": cells[4].get_text(strip=True),
                "url": urljoin(BASE_URL, anchor["href"]),
            }
    return list(events.values())


def fetch_events(session, start=START, end=END):
    initial = get_page(session, RESULTS_URL)
    years = {option["value"] for option in initial.select("select[name$='uxddlYear'] option")}
    if not years:
        raise ValueError("DFS year filter was not found; refusing to publish an empty dataset")
    events = {}
    for year in range(start.year, min(end.year, date.today().year) + 1):
        if str(year) not in years:
            raise ValueError(f"DFS does not offer results for {year}")
        for event_type in ("INNE",):
            url = RESULTS_URL + "?" + urlencode({
                "search": "True", "registered": "", "type": event_type,
                "region": "", "year": year, "includeLocal": "False", "querystring": "",
            })
            page = get_page(session, url)
            seen_pages = set()
            while True:
                fingerprint = str(page.select("table"))
                if fingerprint in seen_pages:
                    raise ValueError("DFS pagination repeated a page")
                seen_pages.add(fingerprint)
                if not page.select_one("select[name$='uxddlYear']"):
                    raise ValueError("DFS result overview was not found")
                for event in result_events(page, start, end):
                    events[event["id"]] = event
                next_link = next((anchor for anchor in page.select("a[href]")
                                  if anchor.get_text(strip=True) == "Neste"), None)
                if next_link is None:
                    break
                postback = re.search(r"__doPostBack\('([^']*)','([^']*)'\)", next_link["href"])
                if not postback:
                    raise ValueError("Unrecognized DFS pagination")
                page = submit_form(session, url, page, {
                    "__EVENTTARGET": postback[1], "__EVENTARGUMENT": postback[2],
                })
    return list(events.values())


def parse_results(page, event):
    records = []
    table = next((table for table in page.select("table")
                  if "Skytter" in [cell.get_text(strip=True) for cell in table.select("tr:first-child > th")]), None)
    if table is None:
        raise ValueError(f"Missing result table for {event['name']}")
    rows = table.find_all("tr", recursive=False)
    if not rows:
        rows = table.select(":scope > tbody > tr")
    headings = [cell.get_text(" ", strip=True) for cell in rows[0].find_all("th", recursive=False)]
    for row in rows[1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) != len(headings):
            continue
        values = dict(zip(headings, cells))
        details = row.find_next_sibling("tr")
        inner = {}
        if details and "expandedInfo" in details.get("class", []):
            for detail in details.select("table tr"):
                text = detail.get_text(" ", strip=True)
                match = re.search(r"inner:\s*(\d+)", text)
                if match:
                    for exercise, label in (("main", "25 skudd"), ("final", "35 skudd")):
                        if label in text:
                            inner[exercise] = int(match[1])
        team_anchor = values["Skytterlag"].find("a", href=True)
        team_id = parse_qs(urlsplit(team_anchor["href"]).query).get("openTeam", [""])[0] if team_anchor else ""
        prize_cell = values.get("Premie")
        prize_match = re.match(r"\s*(\d[\d\s.]*)", prize_cell.get_text(" ", strip=True)) if prize_cell else None
        prize = int(re.sub(r"\D", "", prize_match[1])) if prize_match else 0
        medal_cell = values.get("Medalje")
        medal = medal_cell.get_text(" ", strip=True) if medal_cell else ""
        for exercise, heading in (("main", "Hoved (pl.)"), ("final", "Finale (pl.)")):
            cell = values.get(heading)
            score = re.match(r"\d+", cell.get_text(strip=True)) if cell else None
            if score and int(score[0]) > 0:
                record = {
                    "shooter": values["Skytter"].get_text(" ", strip=True),
                    "club": values["Skytterlag"].get_text(" ", strip=True),
                    "clubId": team_id,
                    "class": values["Klasse"].get_text(strip=True),
                    "exercise": exercise, "score": int(score[0]),
                    "inner": inner.get(exercise), "eventId": event["id"],
                }
                if exercise == "main":
                    record.update({"prize": prize, "medal": medal})
                records.append(record)
    return records


def fetch_results(session, event):
    page = get_page(session, event["url"])
    class_links = {}
    for anchor in page.select("a[href]"):
        query = parse_qs(urlsplit(anchor["href"]).query)
        classes = query.get("class", [""])[0]
        if query.get("eventId") == [event["id"]] and classes and "," not in classes and "sortby" not in query:
            class_links[classes] = urljoin(BASE_URL, anchor["href"])
    if not class_links:
        return []
    records = []
    for url in class_links.values():
        records.extend(parse_results(get_page(session, url), event))
    return records


def write_payload(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def update_archive(events, records):
    if ARCHIVE_OUTPUT.exists():
        previous = json.loads(ARCHIVE_OUTPUT.read_text(encoding="utf-8"))
        archived_events = {
            event["id"]: event for event in previous["events"]
            if event["type"] == "Inne" and not START.isoformat() <= event["date"] <= END.isoformat()
        }
        archived_results = {
            (result["eventId"], result["shooter"], result["clubId"], result["class"], result["exercise"]): result
            for result in previous["results"] if result["eventId"] in archived_events
        }
        complete = previous.get("complete", False)
        start = previous["start"]
        if start == START.isoformat():
            complete = True
    else:
        archived_events = {}
        archived_results = {}
        complete = True
        start = START.isoformat()
    archived_events.update({event["id"]: event for event in events})
    for result in records:
        key = (result["eventId"], result["shooter"], result["clubId"], result["class"], result["exercise"])
        archived_results[key] = result
    payload = {
        "start": start, "end": date.today().isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": RESULTS_URL, "complete": complete,
        "events": list(archived_events.values()), "results": list(archived_results.values()),
    }
    write_payload(ARCHIVE_OUTPUT, payload)


def sync(limit=None):
    with requests.Session() as session:
        session.headers["User-Agent"] = "poll.no Norgestoppen2 result index (non-commercial)"
        events = fetch_events(session, START, END)
        if limit is not None:
            events = events[:limit]
        records = []
        for index, event in enumerate(events, 1):
            print(f"{index}/{len(events)}: {event['date']} {event['name']}", flush=True)
            records.extend(fetch_results(session, event))
    season_events = [event for event in events if START.isoformat() <= event["date"] <= END.isoformat()]
    season_ids = {event["id"] for event in season_events}
    season_records = [record for record in records if record["eventId"] in season_ids]
    payload = {
        "start": START.isoformat(), "end": END.isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": RESULTS_URL, "complete": limit is None,
        "events": season_events, "results": season_records,
    }
    write_payload(OUTPUT, payload)
    if limit is None:
        update_archive(events, records)
    print(f"Published {len(season_records)} season results from {len(season_events)} events")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    sync(args.limit)