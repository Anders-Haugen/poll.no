"use strict";

function selectedRindeEvents(data, year, filters) {
  const firstDay = `${year}-01-01`;
  const lastDay = `${year}-12-31`;
  const official = data.events.filter(event => event.date >= firstDay && event.date <= lastDay);
  const optional = (data.trackerEvents || []).filter(event => {
    const internal = event.internal && filters.includeInternal;
    const nonClassifying = event.classifying === false && filters.includeNonClassifying;
    return (internal || nonClassifying) && event.date >= firstDay && event.date <= lastDay;
  });
  return [...official, ...optional];
}

function rankRindeResults(data, year, filters) {
  const events = new Map(selectedRindeEvents(data, year, filters).map(event => [event.id, event]));
  const shooters = new Map();

  for (const result of [...data.results, ...(data.trackerResults || [])]) {
    const event = events.get(result.eventId);
    if (!event || !result.shooter) continue;
    const identity = `${result.shooter}\u0000${result.clubId || result.club || ""}`;
    if (!shooters.has(identity)) {
      shooters.set(identity, { shooter: result.shooter, club: result.club || "", eventIds: new Set() });
    }
    shooters.get(identity).eventIds.add(event.id);
  }

  const ranked = [...shooters.values()]
    .map(shooter => ({ ...shooter, count: shooter.eventIds.size }))
    .sort((first, second) => second.count - first.count || first.shooter.localeCompare(second.shooter, "nb"));
  ranked.forEach((rider, index) => {
    const previous = ranked[index - 1];
    rider.rank = previous && previous.count === rider.count ? previous.rank : index + 1;
  });
  return ranked.filter(rider => rider.rank <= 10);
}

if (typeof document !== "undefined") {
  const list = document.getElementById("riders");
  const status = document.getElementById("status");
  const updated = document.getElementById("updated");
  const coverage = document.getElementById("coverage");
  const yearLabel = document.getElementById("year-label");
  const includeInternal = document.getElementById("include-internal");
  const includeNonClassifying = document.getElementById("include-non-classifying");
  let data;
  const year = Number(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Oslo", year: "numeric",
  }).format(new Date()));

  function formatDate(date) {
    return new Intl.DateTimeFormat("nb-NO", { dateStyle: "short", timeZone: "Europe/Oslo" }).format(new Date(`${date}T12:00:00`));
  }

  function render(data) {
    const filters = { includeInternal: includeInternal.checked, includeNonClassifying: includeNonClassifying.checked };
    const yearEvents = selectedRindeEvents(data, year, filters);
    const eventDates = yearEvents.map(event => event.date).sort();
    const riders = rankRindeResults(data, year, filters);
    const maxCount = Math.max(1, ...riders.map(rider => rider.count));
    yearLabel.textContent = String(year);
    coverage.textContent = eventDates.length
      ? `Arkivet: ${formatDate(eventDates[0])}–${formatDate(eventDates[eventDates.length - 1])}`
      : `Ingen stevne registrert i ${year}`;

    if (!riders.length) {
      list.innerHTML = '<li class="race-message">Ingen skyttarar med stevner i arkivet for dette året.</li>';
    } else {
      const fragment = document.createDocumentFragment();
      for (const rider of riders) {
        const row = document.createElement("li");
        row.className = "race-row";
        const progress = 3 + (rider.count / maxCount) * 93;
        row.innerHTML = `<span class="race-place">${rider.rank}.</span><span class="race-shooter"><span class="race-name"></span><span class="race-club"></span></span><span class="race-track"><span class="race-bullet" style="--distance: ${progress}%" aria-hidden="true"><svg viewBox="0 0 54 18" focusable="false"><path d="M3 4Q3 2 6 2H31Q36 2 40 5L52 9 40 13Q36 16 31 16H6Q3 16 3 14Z" fill="#b96643" stroke="#572f24" stroke-width="1"/><path d="M6 4h23q5 0 8 3" fill="none" stroke="#f1b08a" stroke-width="1"/><path d="M6 14h25q4 0 7-2" fill="none" stroke="#79422e" stroke-width="1"/></svg></span></span><span class="race-count">${rider.count}<small>${rider.count === 1 ? "stevne" : "stevner"}</small></span>`;
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
      data = await response.json();
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

  includeInternal.addEventListener("change", () => { if (data) render(data); });
  includeNonClassifying.addEventListener("change", () => { if (data) render(data); });
  load();
}