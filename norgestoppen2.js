"use strict";

function rankResults(data, filters) {
  const events = new Map(data.events.map(event => [event.id, event]));
  const classes = filters.class ? filters.class.split(",") : [];
  const grouped = new Map();
  for (const result of data.results) {
    const event = events.get(result.eventId);
    if (!event || event.type !== "Inne") continue;
    if (event.date < data.start || event.date > data.end || event.date < filters.from || event.date > filters.to) continue;
    if (result.exercise !== filters.exercise || (classes.length && !classes.includes(result.class))) continue;
    if ((filters.samlag && result.samlag !== filters.samlag) || (filters.club && result.club !== filters.club)) continue;
    const identity = `${result.shooter}\u0000${result.clubId || result.club}`;
    if (!grouped.has(identity)) grouped.set(identity, []);
    grouped.get(identity).push({ ...result, event });
  }
  const rows = [];
  for (const results of grouped.values()) {
    results.sort((first, second) => second.score - first.score || (second.inner ?? -1) - (first.inner ?? -1) || first.event.date.localeCompare(second.event.date));
    const unique = results.filter((result, index) => results.findIndex(other => other.eventId === result.eventId) === index);
    if (unique.length < filters.count) continue;
    const best = unique.slice(0, filters.count);
    const row = {
      shooter: best[0].shooter, club: best[0].club,
      classes: [...new Set(best.map(result => result.class))].join(", "),
      score: best.reduce((total, result) => total + result.score, 0),
      inner: best.every(result => Number.isInteger(result.inner)) ? best.reduce((total, result) => total + result.inner, 0) : null,
      best,
    };
    rows.push(row);
  }
  rows.sort((first, second) => second.score - first.score || (second.inner ?? -1) - (first.inner ?? -1) || first.shooter.localeCompare(second.shooter, "nb"));
  rows.forEach((row, index) => {
    const previous = rows[index - 1];
    row.rank = previous && previous.score === row.score && previous.inner === row.inner ? previous.rank : index + 1;
  });
  const search = filters.search.trim().toLocaleLowerCase("nb");
  return rows.filter(row => (!filters.limit || row.rank <= filters.limit) && (!search || [row.shooter, row.club, ...row.best.map(result => result.event.name)].join(" ").toLocaleLowerCase("nb").includes(search)));
}

function rankCashResults(data, filters) {
  const events = new Map(data.events.map(event => [event.id, event]));
  const classes = filters.class ? filters.class.split(",") : [];
  const grouped = new Map();
  for (const result of data.results) {
    if (result.exercise !== "main") continue;
    const event = events.get(result.eventId);
    if (!event || !["Inne", "Inne - ikke kl.sett"].includes(event.type)) continue;
    if (event.date < data.start || event.date > data.end || event.date < filters.from || event.date > filters.to) continue;
    if (classes.length && !classes.includes(result.class)) continue;
    if (filters.club && result.club !== filters.club) continue;
    const identity = `${result.shooter}\u0000${result.clubId || result.club}`;
    if (!grouped.has(identity)) grouped.set(identity, new Map());
    const awards = grouped.get(identity);
    if (awards.has(result.eventId)) continue;
    awards.set(result.eventId, { ...result, event });
  }
  const rows = [];
  for (const awards of grouped.values()) {
    const best = [...awards.values()].sort((first, second) => first.event.date.localeCompare(second.event.date));
    const totals = {
      money: best.reduce((total, result) => total + (Number(result.prize) || 0), 0),
      medals: best.filter(result => result.medal).length,
      gold: best.filter(result => result.medal?.toLocaleLowerCase("nb").includes("gylt")).length,
    };
    const total = filters.mode === "money" && filters.hourly
      ? totals.money / (awards.size * 40 / 60)
      : totals[filters.mode];
    if (!total) continue;
    rows.push({
      shooter: best[0].shooter,
      club: best[0].club,
      classes: [...new Set(best.map(result => result.class))].join(", "),
      total,
      best: best.filter(result => filters.mode === "money" ? Number(result.prize) > 0 : filters.mode === "gold" ? result.medal?.toLocaleLowerCase("nb").includes("gylt") : Boolean(result.medal)),
    });
  }
  rows.sort((first, second) => second.total - first.total || first.shooter.localeCompare(second.shooter, "nb"));
  rows.forEach((row, index) => {
    const previous = rows[index - 1];
    row.rank = previous && previous.total === row.total ? previous.rank : index + 1;
  });
  const search = filters.search.trim().toLocaleLowerCase("nb");
  return rows.filter(row => (!filters.limit || row.rank <= filters.limit) && (!search || [row.shooter, row.club, ...row.best.map(result => result.event.name)].join(" ").toLocaleLowerCase("nb").includes(search)));
}

if (typeof module !== "undefined") module.exports = { rankResults, rankCashResults };

if (typeof document !== "undefined") {
  const controls = Object.fromEntries(["mode", "hourly", "exercise", "class", "club", "samlag", "count", "from", "to", "search", "limit"].map(id => [id, document.getElementById(id)]));
  const status = document.getElementById("status");
  const tbody = document.getElementById("results");
  const refresh = document.getElementById("refresh");
  const number = new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 2 });
  const dateParts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Oslo", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date()).map(part => [part.type, part.value]));
  const today = `${dateParts.year}-${dateParts.month}-${dateParts.day}`;
  let data;

  function readStoredSamlag() {
    try {
      return localStorage.getItem("norgestoppen2.samlag") || "";
    } catch {
      return "";
    }
  }

  function storeSamlag(value) {
    try {
      localStorage.setItem("norgestoppen2.samlag", value);
    } catch {
      // Storage may be unavailable in private browsing contexts.
    }
  }

  function addCell(row, text) {
    const cell = row.insertCell();
    cell.textContent = text;
    return cell;
  }

  function eventLink(result) {
    const paragraph = document.createElement("p");
    const link = document.createElement("a");
    const url = new URL(result.event.url);
    if (url.protocol !== "https:" || url.hostname !== "mittdfs.no") throw new Error("Ugyldig DFS-lenkje.");
    url.searchParams.set("class", result.class);
    link.href = url.href;
    link.textContent = result.event.name;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    paragraph.append(link);
    const detail = document.createElement("small");
    detail.textContent = `${result.event.date.split("-").reverse().join(".")} · ${result.score} poeng · ${result.inner ?? "?"} innertreff`;
    paragraph.append(detail);
    return paragraph;
  }

  function awardEventLink(result) {
    const paragraph = document.createElement("p");
    const link = document.createElement("a");
    const url = new URL(result.event.url);
    if (url.protocol !== "https:" || url.hostname !== "mittdfs.no") throw new Error("Ugyldig DFS-lenkje.");
    url.searchParams.set("class", result.class);
    link.href = url.href;
    link.textContent = result.event.name;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    paragraph.append(link);
    const detail = document.createElement("small");
    const currency = new Intl.NumberFormat("nb-NO", { style: "currency", currency: "NOK", maximumFractionDigits: 0 });
    const award = controls.mode.value === "money" ? currency.format(Number(result.prize) || 0) : result.medal;
    detail.textContent = `${result.event.date.split("-").reverse().join(".")} · ${award}`;
    paragraph.append(detail);
    return paragraph;
  }

  function render() {
    if (!data) return;
    controls.to.setCustomValidity(controls.to.value < controls.from.value ? "Til-dato må vere etter frå-dato." : "");
    if (!document.getElementById("filters").checkValidity()) {
      status.textContent = "Vel eit gyldig datointervall innanfor arkivet.";
      status.className = "error";
      tbody.replaceChildren();
      document.getElementById("empty").hidden = true;
      return;
    }
    const filters = Object.fromEntries(Object.entries(controls).map(([key, control]) => [key, control.value]));
    filters.count = Number(filters.count);
    filters.limit = Number(filters.limit);
    filters.hourly = controls.hourly.checked;
    const pointsMode = filters.mode === "points";
    document.getElementById("exercise-filter").hidden = !pointsMode;
    document.getElementById("count-filter").hidden = !pointsMode;
    document.getElementById("samlag-filter").hidden = !pointsMode || document.getElementById("samlag").options.length <= 1;
    document.getElementById("hourly-filter").hidden = pointsMode || filters.mode !== "money";
    const fragment = document.createDocumentFragment();

    if (!pointsMode) {
      const rows = rankCashResults(data, filters);
      const integer = new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 0 });
      const hourlyRate = new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 1 });
      const currency = new Intl.NumberFormat("nb-NO", { style: "currency", currency: "NOK", maximumFractionDigits: 0 });
      for (const result of rows) {
        const row = document.createElement("tr");
        addCell(row, result.rank);
        addCell(row, result.shooter);
        addCell(row, result.classes);
        addCell(row, result.club);
        const eventCell = addCell(row, "");
        if (result.best.length === 1) eventCell.append(awardEventLink(result.best[0]));
        else {
          const details = document.createElement("details");
          const summary = document.createElement("summary");
          summary.textContent = `${result.best.length} stevne`;
          details.append(summary, ...result.best.map(awardEventLink));
          eventCell.append(details);
        }
        addCell(row, filters.mode === "money"
          ? filters.hourly ? `${hourlyRate.format(result.total)} kr/h` : currency.format(result.total)
          : integer.format(result.total));
        fragment.append(row);
      }
      tbody.replaceChildren(fragment);
      document.getElementById("score-heading").textContent = filters.mode === "money"
        ? filters.hourly ? "Timesbetaling (kr/h)" : "Premiepengar"
        : filters.mode === "gold" ? "Gylte medaljar" : "Medaljar";
      document.getElementById("inner-heading").hidden = true;
      document.getElementById("empty").hidden = rows.length > 0;
      document.getElementById("empty").textContent = "Ingen premier eller medaljar passar til filteret.";
      status.className = "";
      const eventIds = new Set(data.events.filter(event => event.date >= filters.from && event.date <= filters.to).map(event => event.id));
      const resultEventIds = new Set(data.results.filter(result => result.exercise === "main" && eventIds.has(result.eventId)).map(result => result.eventId));
      status.textContent = `${rows.length} skyttarar · ${resultEventIds.size}/${eventIds.size} stevne med resultat${data.complete ? "" : " · Ufullstendig arkiv"}`;
      return;
    }

    document.getElementById("empty").textContent = "Ingen resultat passar til filteret.";
    document.getElementById("inner-heading").hidden = false;
    const rows = rankResults(data, filters);
    for (const result of rows) {
      const row = document.createElement("tr");
      addCell(row, result.rank);
      addCell(row, result.shooter);
      addCell(row, result.classes);
      addCell(row, result.club);
      const eventCell = addCell(row, "");
      if (result.best.length === 1) eventCell.append(eventLink(result.best[0]));
      else {
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = `${result.best.length} stevne`;
        details.append(summary, ...result.best.map(eventLink));
        eventCell.append(details);
      }
      addCell(row, number.format(result.score));
      addCell(row, result.inner === null ? "?" : number.format(result.inner));
      fragment.append(row);
    }
    tbody.replaceChildren(fragment);
    document.getElementById("score-heading").textContent = "Sum";
    document.getElementById("empty").hidden = rows.length > 0;
    status.className = "";
    const eventIds = new Set(data.events.filter(event => event.type === "Inne" && event.date >= filters.from && event.date <= filters.to).map(event => event.id));
    const resultEventIds = new Set(data.results.filter(result => result.exercise === filters.exercise && eventIds.has(result.eventId)).map(result => result.eventId));
    status.textContent = `${rows.length} skyttarar · ${resultEventIds.size}/${eventIds.size} stevne med resultat${data.complete ? "" : " · Ufullstendig arkiv"}`;
  }

  async function load() {
    refresh.disabled = true;
    status.textContent = "Hentar resultat frå DFS...";
    status.className = "";
    try {
      let response = await fetch("data/norgestoppen_archive.json", { cache: "no-store" });
      const archiveAvailable = response.ok;
      if (!archiveAvailable) response = await fetch("data/norgestoppen2.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const loaded = await response.json();
      if (!Array.isArray(loaded.events) || !Array.isArray(loaded.results) || !loaded.start || !loaded.end) throw new Error("Ugyldig arkivdata.");
      if (!archiveAvailable) loaded.complete = false;
      data = loaded;
      const archiveEnd = loaded.end < today ? loaded.end : today;
      const previousFrom = controls.from.value;
      const previousTo = controls.to.value;
      controls.from.min = loaded.start;
      controls.from.max = archiveEnd;
      controls.to.min = loaded.start;
      controls.to.max = archiveEnd;
      controls.from.value = previousFrom && previousFrom >= loaded.start && previousFrom <= archiveEnd
        ? previousFrom : ("2026-10-01" >= loaded.start ? "2026-10-01" : loaded.start);
      controls.to.value = previousTo && previousTo >= loaded.start && previousTo <= archiveEnd ? previousTo : archiveEnd;
      const previousClass = controls.class.value;
      const previousClub = controls.club.value;
      const previousSamlag = controls.samlag.value || readStoredSamlag();
      while (controls.class.options.length > 3) controls.class.remove(3);
      for (const value of [...new Set(data.results.map(result => result.class))].sort((first, second) => first.localeCompare(second, "nb", { numeric: true }))) {
        controls.class.add(new Option(value, value));
      }
      controls.class.value = previousClass;
      controls.club.replaceChildren(new Option("Alle skytterlag", ""));
      for (const club of [...new Set(data.results.map(result => result.club))].sort((first, second) => first.localeCompare(second, "nb"))) controls.club.add(new Option(club, club));
      controls.club.value = [...controls.club.options].some(option => option.value === previousClub) ? previousClub : "";
      const samlagValues = [...new Set(data.results.map(result => result.samlag).filter(Boolean))].sort((first, second) => first.localeCompare(second, "nb"));
      controls.samlag.replaceChildren(new Option("Alle skyttersamlag", ""));
      for (const samlag of samlagValues) controls.samlag.add(new Option(samlag, samlag));
      document.getElementById("samlag-filter").hidden = samlagValues.length === 0;
      controls.samlag.value = samlagValues.includes(previousSamlag) ? previousSamlag : "";
      storeSamlag(controls.samlag.value);
      document.getElementById("updated").textContent = `Oppdatert ${new Intl.DateTimeFormat("nb-NO", { dateStyle: "short", timeStyle: "short", timeZone: "Europe/Oslo" }).format(new Date(data.updatedAt))}`;
      render();
    } catch (error) {
      status.className = "error";
      status.textContent = data ? "Kunne ikkje hente nytt arkiv. Viser sist innlasta resultat." : "Kunne ikkje hente arkivet. Prøv igjen seinare.";
      console.error(error);
    } finally {
      refresh.disabled = false;
    }
  }

  document.getElementById("filters").addEventListener("submit", event => event.preventDefault());
  document.getElementById("filters").addEventListener("input", render);
  refresh.addEventListener("click", load);
  controls.samlag.addEventListener("change", () => storeSamlag(controls.samlag.value));
  load();
}