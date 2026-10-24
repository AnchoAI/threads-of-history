"""Work out which countries share a land border, from Natural Earth's public-domain map.

Writes forecast/data/neighbours.json: {ISO3: [ISO3, ...]}, plus the source file's hash.
This is reference data for forecasting (neighbour effects), not a country-year table.

  .cache/venv/bin/python tools/importers/natural_earth_neighbours.py   (needs pyshp and shapely)

Two countries are neighbours if their land outlines touch, allowing a gap of about 5 km
(0.05 degrees) for the 1:50m map's simplified coastlines and rivers. Overseas territories
count as part of their country, as Natural Earth draws them (e.g. France borders Brazil via
French Guiana).
Codes: Natural Earth's ADM0_A3, with the non-ISO ones mapped below. Northern Cyprus and
Somaliland are merged into Cyprus and Somalia, matching the country-year tables.
"""
from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
URL = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
OUT = ROOT / "forecast" / "data" / "neighbours.json"
CODES = {"KOS": "XKX", "SDS": "SSD", "CYN": "CYP", "SOL": "SOM", "SAH": "ESH", "PSX": "PSE"}
GAP = 0.05


def main():
    import shapefile
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    cache = ROOT / ".cache" / "natural-earth" / Path(URL).name
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "threads-of-history importer"})
        cache.write_bytes(urllib.request.urlopen(req, timeout=300).read())
    raw = cache.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
        r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), shx=io.BytesIO(z.read(base + ".shx")),
                             dbf=io.BytesIO(z.read(base + ".dbf")))
        shapes = {}
        for rec, shp in zip(r.records(), r.shapes()):
            code = CODES.get(rec["ADM0_A3"], rec["ADM0_A3"])
            geom = shape(shp.__geo_interface__)
            shapes[code] = unary_union([shapes[code], geom]) if code in shapes else geom
    codes = sorted(shapes)
    geoms = [shapes[c].buffer(GAP / 2) for c in codes]
    tree = STRtree(geoms)
    out = {c: [] for c in codes}
    for i, c in enumerate(codes):
        for j in tree.query(geoms[i]):
            if j != i and geoms[i].intersects(geoms[j]):
                out[c].append(codes[j])
    out = {c: sorted(set(v)) for c, v in out.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": URL, "sha256": hashlib.sha256(raw).hexdigest(), "gap_degrees": GAP,
                               "neighbours": out}, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} countries, {sum(map(len, out.values())) // 2} borders")
    for c in ("SYR", "UKR", "RUS", "FRA", "AUS", "SRB"):
        print(c, out.get(c))


if __name__ == "__main__":
    main()
