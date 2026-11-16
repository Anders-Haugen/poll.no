import json
import re
import unicodedata
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from sync_norgestoppen import create_session, write_payload, OUTPUT


PROFILE_OUTPUT = OUTPUT.with_name("shooter_profiles.json")
SOURCES = tuple(
    f"https://sorlandskula.one/sammenlagt/{year}/index?view=sammenlagt&klasse=ALLE"
    for year in (2024, 2025, 2026)
)


def profile_key(profile):
    name = " ".join(unicodedata.normalize("NFC", profile["shooter"]).lower().split())
    club = " ".join(unicodedata.normalize("NFC", profile["club"]).lower().split())
    return name, re.sub(r"\s+skytterlag$", "", club)


def parse_profiles(page, source):
    cards = page.select(".result-card")
    if not cards:
        raise ValueError(f"No shooter cards found at {source}")
    profiles = []
    for card in cards:
        name = card.select_one(".r-name")
        club = card.select_one(".r-line2")
        image = card.select_one('img[src*="skytterbilder.no/bilder/"]')
        match = re.fullmatch(r"https://skytterbilder\.no/bilder/([1-9]\d*)\.jpg", image["src"]) if image else None
        if name is None or club is None or match is None:
            raise ValueError(f"Incomplete shooter identity at {source}")
        club_name = club.get_text(" ", strip=True).rsplit(", Kl.", 1)[0].strip()
        shooter = name.get_text(" ", strip=True)
        if not shooter or not club_name:
            raise ValueError(f"Empty shooter name or club at {source}")
        profiles.append({
            "shooter": shooter,
            "club": club_name,
            "shooterId": match[1],
            "source": source,
        })
    return profiles


def merge_profiles(previous, incoming):
    profiles = {}
    for profile in [*previous, *incoming]:
        if not re.fullmatch(r"[1-9]\d*", profile["shooterId"]):
            raise ValueError("Invalid shooter ID")
        profiles[(*profile_key(profile), profile["shooterId"])] = profile
    return sorted(profiles.values(), key=lambda profile: (*profile_key(profile), profile["shooterId"]))


def sync():
    previous = json.loads(PROFILE_OUTPUT.read_text(encoding="utf-8"))["profiles"] if PROFILE_OUTPUT.exists() else []
    incoming = []
    with create_session() as session:
        for source in SOURCES:
            response = session.get(source, timeout=60)
            response.raise_for_status()
            incoming.extend(parse_profiles(BeautifulSoup(response.content, "html.parser"), source))
    profiles = merge_profiles(previous, incoming)
    write_payload(PROFILE_OUTPUT, {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "profiles": profiles,
    })
    identities = {}
    for profile in profiles:
        identities.setdefault(profile_key(profile), set()).add(profile["shooterId"])
    conflicts = sum(len(ids) > 1 for ids in identities.values())
    print(f"Published {len(profiles)} public shooter profiles; {conflicts} ambiguous identities (not linked)")


if __name__ == "__main__":
    sync()
