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