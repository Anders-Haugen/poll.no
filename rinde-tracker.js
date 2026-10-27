"use strict";

function rankRindeResults(data, year) {
  const firstDay = `${year}-01-01`;
  const lastDay = `${year}-12-31`;
  const events = new Map(data.events
    .filter(event => event.date >= firstDay && event.date <= lastDay)
    .map(event => [event.id, event]));
  const shooters = new Map();

  for (const result of data.results) {
    const event = events.get(result.eventId);
    if (!event || !result.shooter) continue;
    const identity = `${result.shooter}\u0000${result.clubId || result.club || ""}`;
    if (!shooters.has(identity)) {
      shooters.set(identity, { shooter: result.shooter, club: result.club || "", eventIds: new Set() });
    }
    shooters.get(identity).eventIds.add(event.id);
  }

  return [...shooters.values()]
    .map(shooter => ({ ...shooter, count: shooter.eventIds.size }))
    .sort((first, second) => second.count - first.count || first.shooter.localeCompare(second.shooter, "nb"))
    .slice(0, 10);
}

if (typeof document !== "undefined") {
  const list = document.getElementById("riders");
  const status = document.getElementById("status");
  const updated = document.getElementById("updated");
  const coverage = document.getElementById("coverage");
  const yearLabel = document.getElementById("year-label");
  const year = Number(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Oslo", year: "numeric",
  }).format(new Date()));

  function formatDate(date) {
    return new Intl.DateTimeFormat("nb-NO", { dateStyle: "short", timeZone: "Europe/Oslo" }).format(new Date(`${date}T12:00:00`));
  }

  function render(data) {
    const yearEvents = data.events.filter(event => event.date.startsWith(`${year}-`));
    const eventDates = yearEvents.map(event => event.date).sort();
    const riders = rankRindeResults(data, year);
    const maxCount = Math.max(1, ...riders.map(rider => rider.count));
    yearLabel.textContent = String(year);
    coverage.textContent = eventDates.length
      ? `Arkivet: ${formatDate(eventDates[0])}–${formatDate(eventDates[eventDates.length - 1])}`
      : `Ingen stevne registrert i ${year}`;

    if (!riders.length) {
      list.innerHTML = '<li class="race-message">Ingen skyttarar med stevner i arkivet for dette året.</li>';
    } else {
      const fragment = document.createDocumentFragment();
      for (const [index, rider] of riders.entries()) {
        const row = document.createElement("li");
        row.className = "race-row";
        const progress = 3 + (rider.count / maxCount) * 86;
        row.innerHTML = `<span class="race-place">${index + 1}.</span><span class="race-shooter"><span class="race-name"></span><span class="race-club"></span></span><span class="race-track"><span class="race-horse" style="--distance: ${progress}%" aria-hidden="true">🏇</span></span><span class="race-count">${rider.count}<small>${rider.count === 1 ? "stevne" : "stevner"}</small></span>`;
        row.querySelector(".race-name").textContent = rider.shooter;
        row.querySelector(".race-club").textContent = rider.club;
        fragment.append(row);
      }
      list.replaceChildren(fragment);
      requestAnimationFrame(() => list.querySelectorAll(".race-row").forEach(row => row.classList.add("is-racing")));
    }

    status.className = data.complete ? "" : "error";
    const eventLabel = yearEvents.length === 1 ? "stevne" : "stevner";
    status.textContent = `${riders.length} skyttarar i topp 10 · ${yearEvents.length} ${eventLabel} i arkivet${data.complete ? "" : " · Ufullstendig arkiv"}`;
    updated.textContent = data.updatedAt
      ? `Oppdatert ${new Intl.DateTimeFormat("nb-NO", { dateStyle: "short", timeStyle: "short", timeZone: "Europe/Oslo" }).format(new Date(data.updatedAt))}`
      : "";
  }

  async function load() {
    status.textContent = "Hentar resultat frå DFS-arkivet...";
    try {
      let response = await fetch("data/norgestoppen_archive.json", { cache: "no-store" });
      const archiveAvailable = response.ok;
      if (!archiveAvailable) response = await fetch("data/norgestoppen2.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data.events) || !Array.isArray(data.results)) throw new Error("Ugyldig arkivdata.");
      if (!archiveAvailable) data.complete = false;
      render(data);
    } catch (error) {
      status.className = "error";
      status.textContent = "Kunne ikkje hente arkivet. Prøv igjen seinare.";
      list.innerHTML = '<li class="race-message">Resultatlista er ikkje tilgjengeleg akkurat no.</li>';
      console.error(error);
    }
  }

  load();
}