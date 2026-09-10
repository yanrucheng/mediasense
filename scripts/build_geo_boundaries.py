"""Extract the pinned Natural Earth polygons; no network or runtime GIS dependency.

Usage: python scripts/build_geo_boundaries.py /path/to/ne_10m_admin_0_countries.zip
"""

import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

ARCHIVE_SHA256 = "ce1ac7036499a0edd641fbc093cd209a98f96a49d2eca8480aaacad35138a7f6"
DESTINATION = (
    Path(__file__).resolve().parents[1]
    / "src/mediasense/_resources/geo/ne-regions-5.1.1.json"
)


def build(archive):
    raw = Path(archive).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise ValueError(
            "Boundary archive differs from the reviewed Natural Earth 5.1.1 input"
        )
    with zipfile.ZipFile(archive) as z:
        dbf = z.read("ne_10m_admin_0_countries.dbf")
        shp = z.read("ne_10m_admin_0_countries.shp")
        assert z.read("ne_10m_admin_0_countries.VERSION.txt").strip() == b"5.1.1"
        assert b"GCS_WGS_1984" in z.read("ne_10m_admin_0_countries.prj")
    count, header_length, record_length = struct.unpack_from("<IHH", dbf, 4)
    fields = [
        (dbf[i : i + 11].split(b"\0")[0].decode(), dbf[i + 16])
        for i in range(32, header_length - 1, 32)
    ]
    labels = []
    for i in range(count):
        row = dbf[
            header_length + i * record_length : header_length + (i + 1) * record_length
        ]
        offset, values = 1, {}
        for name, length in fields:
            values[name] = row[offset : offset + length].decode("utf-8").strip(" \0")
            offset += length
        labels.append(values["ADM0_A3"])
    polygons = {}
    offset, index = 100, 0
    while offset < len(shp):
        number, length = struct.unpack_from(">2i", shp, offset)
        data = shp[offset + 8 : offset + 8 + length * 2]
        if labels[index] in {"CHN", "HKG", "MAC", "TWN"}:
            assert struct.unpack_from("<i", data)[0] == 5  # Polygon
            parts, points = struct.unpack_from("<2i", data, 36)
            starts = (*struct.unpack_from(f"<{parts}i", data, 44), points)
            coordinates = [
                list(struct.unpack_from("<2d", data, 44 + parts * 4 + j * 16))
                for j in range(points)
            ]
            polygons[labels[index]] = [
                [
                    [round(x, 6), round(y, 6)]
                    for x, y in coordinates[starts[j] : starts[j + 1]]
                ]
                for j in range(parts)
            ]
        offset += 8 + length * 2
        index += 1
    assert index == count and set(polygons) == {"CHN", "HKG", "MAC", "TWN"}
    value = {
        "source": "Natural Earth Admin-0 Countries 1:10m",
        "version": "5.1.1",
        "source_sha256": ARCHIVE_SHA256,
        "datum": "WGS84",
        "rings": polygons,
    }
    DESTINATION.write_text(
        json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n"
    )
    print(
        f"{DESTINATION}: {DESTINATION.stat().st_size} bytes; sha256={hashlib.sha256(DESTINATION.read_bytes()).hexdigest()}"
    )


if __name__ == "__main__":
    build(sys.argv[1])
