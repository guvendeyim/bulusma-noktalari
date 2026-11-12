#!/bin/sh
# Geofabrik'in son Türkiye dökümünden paketi yeniden üretir, yayındaki docs/ ile karşılaştırır ve:
#   - fark varsa docs/ paketini yenisiyle değiştirir,
#   - fark yoksa yalnızca docs/manifest.json içindeki "kontrol" tarihini günceller.
# Her iki durumda da data/yeni/ silinir, rapor data/rapor-<tarih>.txt olarak kalır ve KONTROLLER.md'ye
# bir satır eklenir. Commit ve push elle yapılır.
#
# Kullanım: sh tools/check_update.sh            (son dökümü indirir)
#           sh tools/check_update.sh <dosya.pbf> (elde olan dökümü kullanır)
#           YAYIMLAMA=1 sh tools/check_update.sh (yalnızca karşılaştırır; docs/ ve data/yeni/ olduğu gibi kalır)
set -eu
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
URL=https://download.geofabrik.de/europe/turkey-latest.osm.pbf
OUT=data/yeni
mkdir -p "$OUT"

if [ $# -ge 1 ]; then
  PBF=$1
else
  PBF=$OUT/turkey-latest.osm.pbf
  curl -fL -o "$PBF" "$URL"
  curl -fsL -o "$PBF.md5" "$URL.md5"
  BEKLENEN=$(cut -d' ' -f1 "$PBF.md5")
  GELEN=$( (md5sum "$PBF" 2>/dev/null || md5 -r "$PBF") | cut -d' ' -f1)
  [ "$BEKLENEN" = "$GELEN" ] || { echo "MD5 tutmuyor: indirme bozuk" >&2; exit 1; }
fi

# Sürüm = dökümün OSM durum tarihi (dosya başlığındaki osmosis_replication_timestamp).
TARIH=$("$PY" -c 'import osmium, sys
h = osmium.io.Reader(sys.argv[1], osmium.osm.osm_entity_bits.NOTHING).header()
print(h.get("osmosis_replication_timestamp", "")[:10])' "$PBF")
[ -n "$TARIH" ] || TARIH=$(date +%F)
echo "Döküm tarihi: $TARIH"

"$PY" tools/osm_extract.py "$PBF" "$OUT/bulusma_onerileri.sqlite"
rm -rf "$OUT/paket"
python3 tools/build_package.py "$OUT/bulusma_onerileri.sqlite" "$OUT/paket" "$TARIH" \
  "$(python3 -c 'import json; print(json.load(open("docs/manifest.json"))["min_m2"])')"

RAPOR=data/rapor-$TARIH.txt
YAYIN=$(python3 -c 'import json; print(json.load(open("docs/manifest.json"))["surum"])')
python3 tools/compare.py docs "$OUT/paket" > "$RAPOR" && FARK=0 || FARK=$?
cat "$RAPOR"
[ "$FARK" -le 1 ] || { echo "Karşılaştırma başarısız" >&2; exit 1; }
[ "${YAYIMLAMA:-}" = 1 ] && { echo "YAYIMLAMA=1: docs/ değişmedi, paket $OUT/paket"; exit 0; }

BUGUN=$(date +%F)
if [ "$FARK" = 1 ]; then
  rm -rf docs/il
  cp -R "$OUT/paket/il" "$OUT/paket/manifest.json" docs/
  DURUM="güncellendi ($YAYIN → $TARIH)"
else
  python3 - "$BUGUN" <<'EOF'
import json, sys
p = "docs/manifest.json"
m = json.load(open(p, encoding="utf-8"))
m["kontrol"] = sys.argv[1]
json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
EOF
  DURUM="fark yok"
fi
rm -rf "$OUT"

# Kontrol geçmişi (git'te izlenir).
OZET=$(grep '^Öneriler:' "$RAPOR" | sed 's/^Öneriler: //')
[ -f KONTROLLER.md ] || printf '%s\n\n%s\n%s\n' "# Veri kontrolleri" \
  "| Kontrol | Döküm | Sonuç | Öneriler |" "|---|---|---|---|" > KONTROLLER.md
echo "| $BUGUN | $TARIH | $DURUM | $OZET |" >> KONTROLLER.md
echo "Sonuç: $DURUM. docs/ ve KONTROLLER.md commit edilmeli."
