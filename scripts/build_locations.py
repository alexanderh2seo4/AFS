"""Build the public finder from all GeoNames Germany postal-locality rows.

This script downloads public geography only and never reads the private store.
"""
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://download.geonames.org/export/zip/DE.zip"


def parse_locations(payload):
    rows = set()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for line in archive.read("DE.txt").decode("utf-8").splitlines():
            cells = line.split("\t")
            if len(cells) < 11 or cells[0] != "DE" or len(cells[1]) != 5 or not cells[1].isdigit():
                raise ValueError("Invalid Germany postal row")
            lat, lon = float(cells[9]), float(cells[10])
            if not cells[2] or not (47 <= lat <= 56 and 5 <= lon <= 16):
                raise ValueError("Invalid locality or coordinate")
            # County/state distinguish identically named towns; retain every
            # locality instead of truncating shared postcodes to two names.
            region = cells[7] or cells[5] or cells[3]
            rows.add((cells[1], cells[2], region, round(lat, 5), round(lon, 5)))
    if len(rows) < 10000:
        raise ValueError("Incomplete Germany locality download")
    return sorted(rows, key=lambda row: (row[1].casefold(), row[2], row[0]))


def main():
    request = Request(SOURCE, headers={"User-Agent": "AFS-public-location-index/1.0"})
    with urlopen(request, timeout=60) as response:
        payload = response.read(16 * 1024 * 1024 + 1)
    if len(payload) > 16 * 1024 * 1024:
        raise ValueError("Postal download too large")
    rows = parse_locations(payload)
    data = {
        "source": SOURCE,
        "license": "CC BY 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "columns": ["postalCode", "city", "region", "latitude", "longitude"],
        "counts": {"localities": len(rows), "postcodes": len({row[0] for row in rows})},
        "rows": rows,
    }
    output = ROOT / "docs/assets/locations-de.js"
    output.write_text("// Public GeoNames Germany postal localities (CC BY 4.0).\nexport default " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(json.dumps(data["counts"]))


if __name__ == "__main__":
    main()
