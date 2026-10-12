"use strict";

function rankResults(data, filters) {
  const events = new Map(data.events.map(event => [event.id, event]));
  const classes = filters.class ? filters.class.split(",") : [];
  const grouped = new Map();
  for (const result of data.results) {
    const event = events.get(result.eventId);
    if (!event || !["Inne", "Inne - ikke kl.sett"].includes(event.type)) continue;
    if (event.date < data.start || event.date > data.end || event.date < filters.from || event.date > filters.to) continue;
    if (result.exercise !== filters.exercise || (classes.length && !classes.includes(result.class))) continue;
    if (filters.club && result.club !== filters.club) continue;
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

if (typeof document !== "undefined") {
  const controls = Object.fromEntries(["exercise", "class", "club", "count", "from", "to", "search", "limit"].map(id => [id, document.getElementById(id)]));
  const status = document.getElementById("status");
  const tbody = document.getElementById("results");
  const refresh = document.getElementById("refresh");
  const number = new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 2 });
  const dateParts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Oslo", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date()).map(part => [part.type, part.value]));
  const today = `${dateParts.year}-${dateParts.month}-${dateParts.day}`;
  controls.to.value = today < controls.to.min ? controls.to.min : today > controls.to.max ? controls.to.max : today;
  controls.to.defaultValue = controls.to.value;
  let data;

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

  function render() {
    if (!data) return;
    controls.to.setCustomValidity(controls.to.value < controls.from.value ? "Til-dato må vere etter frå-dato." : "");
    if (!document.getElementById("filters").checkValidity()) {
      status.textContent = "Vel eit gyldig datointervall innanfor sesongen.";
      status.className = "error";
      tbody.replaceChildren();
      document.getElementById("empty").hidden = true;
      return;
    }
    const filters = Object.fromEntries(Object.entries(controls).map(([key, control]) => [key, control.value]));
    filters.count = Number(filters.count);
    filters.limit = Number(filters.limit);
    const rows = rankResults(data, filters);
    const fragment = document.createDocumentFragment();
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
    status.textContent = `${rows.length} skyttarar · ${data.events.length} innandørsstevne${data.complete ? "" : " · Ufullstendig datagrunnlag"}`;
  }

  async function load() {
    refresh.disabled = true;
    status.textContent = "Hentar resultat frå DFS...";
    status.className = "";
    try {
      const response = await fetch("data/norgestoppen2.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const loaded = await response.json();
      if (!Array.isArray(loaded.events) || !Array.isArray(loaded.results) || loaded.start !== "2026-10-01" || loaded.end !== "2027-10-01") throw new Error("Ugyldig sesongdata.");
      data = loaded;
      const previousClass = controls.class.value;
      const previousClub = controls.club.value;
      while (controls.class.options.length > 3) controls.class.remove(3);
      for (const value of [...new Set(data.results.map(result => result.class))].sort((first, second) => first.localeCompare(second, "nb", { numeric: true }))) {
        controls.class.add(new Option(value, value));
      }
      controls.class.value = previousClass;
      controls.club.replaceChildren(new Option("Alle skytterlag", ""));
      for (const club of [...new Set(data.results.map(result => result.club))].sort((first, second) => first.localeCompare(second, "nb"))) controls.club.add(new Option(club, club));
      controls.club.value = [...controls.club.options].some(option => option.value === previousClub) ? previousClub : "";
      document.getElementById("updated").textContent = `Oppdatert ${new Intl.DateTimeFormat("nb-NO", { dateStyle: "short", timeStyle: "short", timeZone: "Europe/Oslo" }).format(new Date(data.updatedAt))}`;
      render();
    } catch (error) {
      status.className = "error";
      status.textContent = data ? "Kunne ikkje hente ny liste. Viser sist innlasta resultat." : "Kunne ikkje hente resultatlista. Prøv igjen seinare.";
      console.error(error);
    } finally {
      refresh.disabled = false;
    }
  }

  document.getElementById("filters").addEventListener("submit", event => event.preventDefault());
  document.getElementById("filters").addEventListener("input", render);
  refresh.addEventListener("click", load);
  load();
}