# 3D-dingser pa poll.no

Ny struktur for 3D-produkt:

- `3d-dingser.html`: kundesida som les katalogen fra JSON
- `admin-3d-dingser.html`: admin-side for aa redigere produktinfo og generere JSON
- `data/3d-products/index.json`: indeks over produktfiler
- `data/3d-products/products/<slug>/product.json`: metadata for eitt produkt
- `data/3d-products/products/<slug>/images/`: produktbilder
- `data/3d-products/products/<slug>/models/`: STL-filer
- `backup/3d-dingser-2026-05-29/`: backup av gammal side og gamle bilde

## Legge til nytt produkt

1. Opne `admin-3d-dingser.html`.
2. Trykk `Nytt produkt`.
3. Fyll ut felta, spesielt `id`, `slug`, `category`, `images` og `stlFile`.
4. Last ned `product.json` og `index.json` fra admin-sida.
5. Opprett mappe manuelt i repo:
   - `data/3d-products/products/<slug>/`
   - `data/3d-products/products/<slug>/images/`
   - `data/3d-products/products/<slug>/models/`
6. Legg inn bilder og STL-filer i mappene.
7. Erstatt filene i repo med nedlasta JSON og commit.

## Viktig

Admin-sida er statisk og kan ikkje automatisk opprette mapper/filer i GitHub. Ho hjelper deg med ferdig JSON og korrekt mappestruktur som du committe manuelt.

## Automatisk synk av bilder og STL

For aa sleppe manuell linking i `product.json`, bruk synk-scriptet:

```bash
python tools/sync_3d_products.py
```

Scriptet gjer dette for alle produkt i `data/3d-products/index.json`:

- Fyller `images` med filer funne i `images/`
- Fyller `stl.file` med fyrste `.stl` funne i `models/`
- Setter `stl.units` til `mm` om feltet manglar
- Oppdaterer `updatedAt` i `index.json`

Kjoer dette etter du har lagt inn nye filer i produktmappene, før commit/deploy.

## Norgestoppen2

`norgestoppen2.html` viser ei uoffisiell rangering av publiserte DFS-resultat.
Sesongen er fast avgrensa til 1. oktober 2026 til og med 1. oktober 2027.
Berre stevnetypane `INNE` og `INIK` er med, inkludert interne stevner.
Avgrensinga bruker stevnedato, ikkje innsendingsdato.

Oppdater datagrunnlaget lokalt:

```bash
pip install -r tools/norgestoppen_requirements.txt
python tools/test_norgestoppen.py
python tools/sync_norgestoppen.py
```

Innhentinga les alle sider i DFS sitt resultatsok for 2026 og 2027, naar
aarstalet er tilgjengeleg. Ho les kvar publisert klasse og hentar poeng og
innertreff for hovudskyting og finale. Ved feil blir eksisterande datafil
bevart; ei delvis innhenting skal ikkje erstatte den komplette lista.
`--limit` er berre for feilsoking og markerer data som ufullstendige.

Lista sorterer paa poeng, deretter innertreff. Like resultat deler plass.
Ved fleire resultat per skyttar blir summen av dei N beste brukt, og berre
skyttarar med minst N resultat er med. Ukjende innertreff blir viste som `?`
og rangerte etter kjende innertreff ved lik poengsum. Skyttaridentiteten er
namn + skytterlag, sidan DFS si offentlege liste ikkje gir skytter-ID.
Namnendring eller byte av lag kan derfor gi fleire oppforingar.
Tellande stevner kan utvidast i lista for aa vise kvart enkelt resultat.
Til-dato er som standard dagens dato i norsk tid, avgrensa til sesongen.

## 1 mot 1

`1vs1.html` samanliknar to skyttarar på felles innandørsstevner i
`data/norgestoppen_archive.json`. Sida viser duellstatistikk for 35 skot,
25 skot, 15-skotserie og 10-skotserie. Eit stevne tel ein gong per øving;
høgast poengsum vinn, og for 25- og 35-skot tel innertreff ved like poeng.
Namn og skytterlag blir brukte som identitet. `data/shooter_profiles.json`
koplar namn og lag til offentlege skytter-ID-ar frå Sørlandskula 2024–2026,
Norgescupen 2026 og manuelt stadfesta Results-profilar. Berre eintydige treff på både namn
og lag blir kopla; avsluttande «Skytterlag»/«Skyttarlag» og ulik bokstavstorleik blir
ignorerte. Historiske lagsbyte og namnendringar blir ikkje gjetta.
ID-en blir vist under namnet, og bileta blir lasta direkte frå
`https://skytterbilder.no/bilder/<skytter-id>.jpg`, med DFS som fotokjelde.
Manglande ID eller bilete gir initialar og ei forklaring. Samanlikninga
fungerer også dersom profilregisteret ikkje kan lastast.

Oppdater profilregisteret med `python tools/sync_shooter_profiles.py`.
Scriptet hentar dei tre offentlege «Vis alle deltakere»-listene utan
innlogging og bevarer eksisterande koplingar, inkludert manuelt stadfesta
oppføringar med kjelde-URL. Feil under innhenting bevarer eksisterande fil.
Oppføringane frå Norgescupen er eit manuelt innhenta uttrekk av offentleg
viste namn, lag og bilete-ID-ar frå bane-samanlagtlista (klasse 3–5 og veteranar).
Søkefilteret viser bilete også for skyttarar utanfor dei første 50 i totallista.
Desse koplingane blir bevarte ved synk, men Norgescupen blir ikkje henta
automatisk av scriptet. Manglande bilete eller ID-ar i kjelda blir ikkje gjetta.
Motstridande ID-ar blir bevarte som tvitydige og ikkje kopla på sida.
Dette dekkjer ikkje alle skyttarar i DFS-arkivet. Ingen bilete blir kopierte
til repoet, og ingen Results-token blir brukte.

Test profilinnhenting med `python tools/test_shooter_profiles.py` og
namn-/lagkopling med `node --test tools/test_1vs1.cjs`.

Framsida og toppmenyane viser Framsida, Norgestoppen2, 1 mot 1, 350-sida og Memes.
Arbeidsprosjekta er framleis tilgjengelege via direkte URL; skjulte lenkjer
er ikkje tilgangskontroll.

Nettlesaren les `data/norgestoppen2.json` fraa same nettside, ikkje direkte
fraa DFS. Knappen paa sida lastar inn siste publiserte datafil paa nytt.
GitHub Actions oppdaterer fila dagleg kl. 05:17 UTC etter at workflowen er
pusha og ligg paa standardbranchen. Han kan ogsaa startast manuelt med
`workflow_dispatch`. Workflowen treng skrivetilgang; branch-reglar kan
krevje ei anna publiseringsloysing. Ei Pages-loysing som berre byggjer paa
push, blir ikkje trigga av bot-commit med `GITHUB_TOKEN`; aktiver Pages
bygging med GitHub Actions eller publiser oppdateringa separat.

For lokal visning, bruk `python -m http.server 8000` og opne
`http://localhost:8000/norgestoppen2.html`. Direkte filopning stoettar ikkje
JSON-henting i alle nettlesarar. Berre innsendte resultat er med; oversikta
er ikkje ein garanti for at alle gjennomfoerte stevner har levert resultat.
DFS oppgir at kommersiell bruk av innhaldet krev samtykke.