"use strict";

const SERIES = [
  { id: "final", label: "35-skudd", exercise: "final", scoreField: "score", countInner: true },
  { id: "main", label: "25-skudd", exercise: "main", scoreField: "score", countInner: true },
  { id: "series15", label: "15-skuddserie", exercise: "main", scoreField: "series15", countInner: false },
  { id: "series10", label: "10-skuddserie", exercise: "main", scoreField: "series10", countInner: false },
];

function shooterIdentity(result) {
  return `${result.shooter}\u0000${result.clubId || result.club || ""}`;
}

function compareShooters(data, first, second, series) {
  const events = new Map(data.events.filter(event => event.type === "Inne").map(event => [event.id, event]));
  const scores = new Map([[first.id, new Map()], [second.id, new Map()]]);

  for (const result of data.results) {
    const score = result[series.scoreField];
    if (result.exercise !== series.exercise || !Number.isFinite(score)) continue;
    const athleteScores = scores.get(shooterIdentity(result));
    const event = events.get(result.eventId);
    if (!athleteScores || !event) continue;
    const previous = athleteScores.get(event.id);
    const inner = series.countInner ? result.inner : null;
    if (!previous || score > previous.score ||
      (score === previous.score && Number.isInteger(inner) && inner > (previous.inner ?? -1))) {
      athleteScores.set(event.id, { ...result, score, inner, event });
    }
  }

  const firstScores = scores.get(first.id);
  const secondScores = scores.get(second.id);
  const results = [...firstScores.keys()]
    .filter(eventId => secondScores.has(eventId))
    .map(eventId => {
      const firstResult = firstScores.get(eventId);
      const secondResult = secondScores.get(eventId);
      const winner = firstResult.score !== secondResult.score
        ? firstResult.score > secondResult.score ? "first" : "second"
        : Number.isInteger(firstResult.inner) && Number.isInteger(secondResult.inner) && firstResult.inner !== secondResult.inner
          ? firstResult.inner > secondResult.inner ? "first" : "second"
          : "draw";
      return { event: firstResult.event, first: firstResult, second: secondResult, winner };
    });

  return {
    results,
    firstWins: results.filter(result => result.winner === "first").length,
    draws: results.filter(result => result.winner === "draw").length,
    secondWins: results.filter(result => result.winner === "second").length,
  };
}

if (typeof document !== "undefined") {
  const form = document.getElementById("duell-form");
  const firstInput = document.getElementById("first-shooter");
  const secondInput = document.getElementById("second-shooter");
  const suggestions = document.getElementById("shooters");
  const status = document.getElementById("status");
  const submit = document.getElementById("compare");
  const comparison = document.getElementById("comparison");
  const updated = document.getElementById("updated");
  const coverage = document.getElementById("coverage");
  const number = new Intl.NumberFormat("nb-NO");
  let data;
  let shootersByLabel = new Map();
  let archiveStatus = "";

  function makeShooterList(results) {
    const shooters = new Map();
    for (const result of results) {
      if (!result.shooter) continue;
      const id = shooterIdentity(result);
      if (!shooters.has(id)) {
        shooters.set(id, {
          id,
          name: result.shooter,
          club: result.club || "Ukjent skytterlag",
          clubId: result.clubId || "",
        });
      }
    }
    const entries = [...shooters.values()];
    const labelCounts = new Map();
    for (const shooter of entries) {
      shooter.label = `${shooter.name} · ${shooter.club}`;
      labelCounts.set(shooter.label, (labelCounts.get(shooter.label) || 0) + 1);
    }
    for (const shooter of entries) {
      if (labelCounts.get(shooter.label) > 1) shooter.label += ` · ${shooter.clubId || "ukjent lags-ID"}`;
    }
    return entries.sort((a, b) => a.label.localeCompare(b.label, "nb"));
  }

  function shooterCard(target, shooter) {
    target.replaceChildren();
    const initials = shooter.name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toLocaleUpperCase("nb");
    const avatar = document.createElement("div");
    avatar.className = "duell-avatar";
    avatar.setAttribute("role", "img");
    avatar.setAttribute("aria-label", `Avatar for ${shooter.name}, shown with initials`);
    avatar.textContent = initials;
    const name = document.createElement("span");
    name.className = "shooter-name";
    name.textContent = shooter.name;
    const club = document.createElement("span");
    club.className = "shooter-club";
    club.textContent = shooter.club;
    const search = document.createElement("a");
    search.className = "shooter-search";
    search.href = `https://lsres.no/search/?s=${encodeURIComponent(shooter.name)}`;
    search.target = "_blank";
    search.rel = "noopener noreferrer";
    search.textContent = "Sjå i Results";
    target.append(avatar, name, club, search);
  }

  function seriesRow(first, second, series, result) {
    const row = document.createElement("article");
    row.className = "series-row";
    const heading = document.createElement("div");
    heading.className = "series-heading";
    const title = document.createElement("h4");
    title.textContent = series.label;
    const shared = document.createElement("span");
    shared.textContent = `${number.format(result.results.length)} felles stevner`;
    heading.append(title, shared);

    const labels = document.createElement("div");
    labels.className = "series-labels";
    const firstLabel = document.createElement("span");
    firstLabel.className = "series-first-label";
    firstLabel.textContent = `${first.name}: ${number.format(result.firstWins)}`;
    const secondLabel = document.createElement("span");
    secondLabel.className = "series-second-label";
    secondLabel.textContent = `${second.name}: ${number.format(result.secondWins)}`;
    labels.append(firstLabel, secondLabel);

    const total = result.results.length;
    const bar = document.createElement("div");
    bar.className = "winbar";
    bar.setAttribute("role", "img");
    bar.setAttribute("aria-label", `${series.label}: ${first.name} vann ${result.firstWins}, uavgjort ${result.draws}, ${second.name} vann ${result.secondWins}`);
    for (const [className, wins] of [
      ["winbar-first", result.firstWins],
      ["winbar-draw", result.draws],
      ["winbar-second", result.secondWins],
    ]) {
      const segment = document.createElement("span");
      segment.className = className;
      segment.style.width = total ? `${wins / total * 100}%` : "0";
      bar.append(segment);
    }

    const draws = document.createElement("span");
    draws.className = "series-draws";
    draws.textContent = result.draws ? `${number.format(result.draws)} uavgjort` : "";
    row.append(heading, labels, bar, draws);
    return row;
  }

  function renderComparison(first, second) {
    shooterCard(document.getElementById("first-card"), first);
    shooterCard(document.getElementById("second-card"), second);
    const container = document.getElementById("series-results");
    const output = document.createDocumentFragment();
    const results = SERIES.map(series => ({
      series,
      result: compareShooters(data, first, second, series),
    }));
    for (const item of results) output.append(seriesRow(first, second, item.series, item.result));
    container.replaceChildren(output);
    document.getElementById("no-shared-events").hidden = results.some(item => item.result.results.length > 0);
    comparison.hidden = false;
  }

  async function load() {
    status.textContent = "Hentar resultat frå DFS-arkivet...";
    status.className = "";
    submit.disabled = true;
    try {
      let response = await fetch("data/norgestoppen_archive.json", { cache: "no-store" });
      const archiveAvailable = response.ok;
      if (!archiveAvailable) response = await fetch("data/norgestoppen2.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const loaded = await response.json();
      if (!Array.isArray(loaded.events) || !Array.isArray(loaded.results) || !loaded.start || !loaded.end) {
        throw new Error("Ugyldig arkivdata.");
      }
      data = loaded;
      shootersByLabel = new Map(makeShooterList(data.results).map(shooter => [shooter.label, shooter]));
      suggestions.replaceChildren();
      for (const shooter of shootersByLabel.values()) {
        const option = document.createElement("option");
        option.value = shooter.label;
        suggestions.append(option);
      }
      coverage.textContent = `${loaded.start.split("-").reverse().join(".")}–${loaded.end.split("-").reverse().join(".")}`;
      updated.textContent = `Oppdatert ${new Intl.DateTimeFormat("nb-NO", { dateStyle: "short", timeStyle: "short", timeZone: "Europe/Oslo" }).format(new Date(loaded.updatedAt))}`;
      archiveStatus = `Søk blant ${number.format(shootersByLabel.size)} skyttarar · ${number.format(loaded.events.length)} innandørsstevner i arkivet${archiveAvailable && loaded.complete ? "" : " · Ufullstendig arkiv"}`;
      status.textContent = archiveStatus;
      submit.disabled = false;
    } catch (error) {
      status.className = "error";
      status.textContent = "Kunne ikkje hente arkivet. Prøv igjen seinare.";
      console.error(error);
    }
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    const first = shootersByLabel.get(firstInput.value);
    const second = shootersByLabel.get(secondInput.value);
    if (!first || !second) {
      comparison.hidden = true;
      status.className = "error";
      status.textContent = "Vel begge skyttarane frå søkjeforslaga.";
      return;
    }
    if (first.id === second.id) {
      comparison.hidden = true;
      status.className = "error";
      status.textContent = "Vel to ulike skyttarar.";
      return;
    }
    status.className = "";
    status.textContent = archiveStatus;
    renderComparison(first, second);
  });

  load();
}
