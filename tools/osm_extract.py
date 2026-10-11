"""Geofabrik Türkiye dökümünden önerilen buluşma noktalarını (açık alanlar) çıkarır.

Kullanım: .venv/bin/python tools/osm_extract.py data/turkey-latest.osm.pbf data/bulusma_onerileri.sqlite

Çıktı tablosu: nokta(osm_id, tur, oncelik, ad, lat, lng, alan_m2, il, ilce)
Bir parkın içinde kalan spor sahası ve oyun alanları ayrıca listelenmez.
Veri © OpenStreetMap katkıcıları (ODbL).
"""
import sqlite3
import sys
import time

import osmium
from pyproj import Geod
from shapely import STRtree
from shapely.geometry import shape

GEOD = Geod(ellps="WGS84")

# Öneri sırası: küçük sayı önce gösterilir.
ONCELIK = {"park": 1, "meydan": 1, "pazar_yeri": 2, "spor_sahasi": 3, "oyun_alani": 4}


def tur_of(tags):
    """OSM etiketlerinden modülün tür adını döndürür; kapsam dışıysa None."""
    if tags.get("access") in ("private", "no"):
        return None
    leisure = tags.get("leisure")
    if leisure == "park":
        return "park"
    if leisure == "playground":
        return "oyun_alani"
    if leisure == "pitch":
        return "spor_sahasi"
    if tags.get("place") == "square":
        return "meydan"
    if tags.get("amenity") == "marketplace":
        return "pazar_yeri"
    return None


def main(pbf, out):
    start = time.time()
    processor = (
        osmium.FileProcessor(pbf)
        .with_areas()
        .with_filter(osmium.filter.KeyFilter("leisure", "amenity", "place", "boundary"))
        .with_filter(osmium.filter.GeoInterfaceFilter())
    )

    iller, ilceler, noktalar, parklar = [], [], [], []
    for obj in processor:
        if not obj.is_area():
            continue
        tags = obj.tags
        if tags.get("boundary") == "administrative":
            level = tags.get("admin_level")
            if level in ("4", "6") and tags.get("name"):
                geom = shape(obj.__geo_interface__["geometry"])
                (iller if level == "4" else ilceler).append((tags["name"], geom))
            continue
        tur = tur_of(tags)
        if tur is None:
            continue
        geom = shape(obj.__geo_interface__["geometry"])
        if geom.is_empty:
            continue
        point = geom.representative_point()
        alan = abs(GEOD.geometry_area_perimeter(geom)[0])
        # Alan kimliği: yol için 2*id, ilişki için 2*id+1 (libosmium kuralı).
        osm_id = ("w" if obj.from_way() else "r") + str(obj.orig_id())
        noktalar.append((osm_id, tur, tags.get("name"), point.y, point.x, alan, point))
        if tur == "park":
            parklar.append(geom)

    print(f"okundu: {len(noktalar)} alan, {len(iller)} il, {len(ilceler)} ilçe, {time.time() - start:.0f} sn")

    def locator(bolgeler):
        tree = STRtree([g for _, g in bolgeler])

        def find(point):
            hits = tree.query(point, predicate="within")
            return bolgeler[hits[0]][0] if len(hits) else None

        return find

    il_bul, ilce_bul = locator(iller), locator(ilceler)

    park_tree = STRtree(parklar)
    onceki = len(noktalar)
    noktalar = [
        n for n in noktalar
        if n[1] not in ("spor_sahasi", "oyun_alani") or not len(park_tree.query(n[6], predicate="within"))
    ]
    print(f"park içinde kaldığı için atılan: {onceki - len(noktalar)}")

    db = sqlite3.connect(out)
    db.executescript(
        """
        DROP TABLE IF EXISTS nokta;
        CREATE TABLE nokta (
            osm_id TEXT PRIMARY KEY, tur TEXT NOT NULL, oncelik INTEGER NOT NULL, ad TEXT,
            lat REAL NOT NULL, lng REAL NOT NULL, alan_m2 REAL NOT NULL,
            il TEXT, ilce TEXT
        );
        """
    )
    db.executemany(
        "INSERT OR IGNORE INTO nokta VALUES (?,?,?,?,?,?,?,?,?)",
        [(i, t, ONCELIK[t], ad, lat, lng, round(alan, 1), il_bul(p), ilce_bul(p)) for i, t, ad, lat, lng, alan, p in noktalar],
    )
    db.execute("CREATE INDEX nokta_konum ON nokta (lat, lng)")
    db.execute("CREATE INDEX nokta_il ON nokta (il)")
    db.commit()
    print(f"yazıldı: {db.execute('SELECT count(*) FROM nokta').fetchone()[0]} kayıt, toplam {time.time() - start:.0f} sn")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
