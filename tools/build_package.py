"""Önerilen buluşma noktalarını ilçe dosyalarına böler ve manifest üretir.

Kullanım: python3 tools/build_package.py data/bulusma_onerileri.sqlite docs 2026-10-08 [min_m2]

Çıktı:
  docs/manifest.json               sürüm, alan sırası, ilçe listesi (dosya, boyut, sha256, kayıt, kutu)
  docs/il/<il>/<ilce>.json         [[osm_id, tur, oncelik, ad, lat, lng, m2], ...]
Dosyalar düz JSON'dur; sıkıştırmayı sunucu (GitHub Pages) aktarım sırasında yapar.
Uygulama ilçeyi adından değil kutusundan (min_lat, min_lng, max_lat, max_lng) bulur: konumun
çevresindeki kutularla kesişen ilçe dosyalarını indirir; böylece ilçe sınırındaki kullanıcı komşu
ilçenin noktalarını da görür ve cihazda adres çözümleme gerekmez.
Veri © OpenStreetMap katkıcıları (ODbL).
"""
import hashlib
import json
import os
import sqlite3
import sys

ALANLAR = ["osm_id", "tur", "oncelik", "ad", "lat", "lng", "m2"]
ILCESIZ = "diger"


def slug(ad):
    return ad.translate(str.maketrans("çğıöşüâîûÇĞİÖŞÜÂÎÛ", "cgiosuaiuCGIOSUAIU")).lower().replace(" ", "-")


def main(db_path, out_dir, surum, min_m2=500):
    db = sqlite3.connect(db_path)
    gruplar = {}
    rows = db.execute(
        "SELECT il, ilce, osm_id, tur, oncelik, ad, round(lat, 5), round(lng, 5), cast(alan_m2 AS INTEGER)"
        " FROM nokta WHERE il IS NOT NULL AND alan_m2 >= ? ORDER BY il, ilce, oncelik, alan_m2 DESC",
        (min_m2,),
    )
    for il, ilce, *kayit in rows:
        gruplar.setdefault((il, ilce or ILCESIZ), []).append(kayit)

    ilceler = []
    for (il, ilce), kayitlar in gruplar.items():
        paket = json.dumps(kayitlar, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        dosya = f"il/{slug(il)}/{slug(ilce)}.json"
        hedef = os.path.join(out_dir, dosya)
        os.makedirs(os.path.dirname(hedef), exist_ok=True)
        with open(hedef, "wb") as f:
            f.write(paket)
        lats, lngs = [k[4] for k in kayitlar], [k[5] for k in kayitlar]
        ilceler.append({
            "il": il,
            "ilce": ilce,
            "dosya": dosya,
            "boyut": len(paket),
            "sha256": hashlib.sha256(paket).hexdigest(),
            "kayit": len(kayitlar),
            "kutu": [min(lats), min(lngs), max(lats), max(lngs)],
        })
    manifest = {
        "surum": surum,
        "min_m2": min_m2,
        "alanlar": ALANLAR,
        "atif": "© OpenStreetMap katkıcıları (ODbL)",
        "ilceler": ilceler,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(ilceler)} ilçe, {sum(i['kayit'] for i in ilceler)} kayıt, {sum(i['boyut'] for i in ilceler)} bayt")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], *(int(a) for a in sys.argv[4:5]))
