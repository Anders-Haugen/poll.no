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

`norgestoppen_cash.html` viser sesongsummer for premiering frå dei same
innandørsstevna. Vel mellom samla premiebeløp, medaljar totalt og gylte
medaljar. Premiesummen og medaljeteksten blir henta frå DFS-resultatlista.
Kvar skytter blir rekna éin gong per stevne, sjølv om resultatfila har både
hovud- og finalepost. DFS-lista gir ikkje skytter-ID, så identiteten er namn
og skytterlag; namn- eller lagsbyte kan derfor gi fleire oppføringar.

Framsida og toppmenyane viser Framsida, Norgestoppen2, Norgestoppen Cash,
350-sida og Memes.
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