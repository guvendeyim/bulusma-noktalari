# Buluşma Noktası Önerileri

Güvendeyim uygulamasının "buluşma noktası" modülü için açık alan önerileri: Türkiye genelinde park, meydan, pazar yeri, spor sahası ve oyun alanları.

- Sayfa: https://guvendeyim.github.io/bulusma-noktalari/
- Veri: https://guvendeyim.github.io/bulusma-noktalari/manifest.json

Bu liste OpenStreetMap verisinden otomatik üretilmiş **öneridir**; resmi bir belirleme ya da güvenlik garantisi değildir.

## Veri biçimi

`docs/manifest.json`

| Alan | Açıklama |
|---|---|
| `surum` | Kaynak OSM dökümünün tarihi |
| `min_m2` | Pakete alınan en küçük alan |
| `bicim` | `geojson` |
| `ilceler[]` | `il`, `ilce`, `dosya`, `boyut`, `sha256`, `kayit`, `kutu` |

`kutu` = `[min_lat, min_lng, max_lat, max_lng]` (WGS84). Uygulama, konumun çevresindeki kutularla kesişen ilçe dosyalarını indirir.

`docs/il/<il>/<ilce>.geojson` — GeoJSON `FeatureCollection`; her öneri bir `Point`:

```json
{"type":"Feature","id":"w177436492",
 "geometry":{"type":"Point","coordinates":[29.05642,40.97931]},
 "properties":{"tur":"park","oncelik":1,"ad":"Özgürlük Parkı","m2":102081}}
```

Koordinat sırası GeoJSON kuralıyla **boylam, enlem**dir. `ad` boş (`null`) olabilir. Türler ve öncelik: `park` 1, `meydan` 1, `pazar_yeri` 2, `spor_sahasi` 3, `oyun_alani` 4. Bir parkın içinde kalan spor sahası ve oyun alanları ayrıca listelenmez. Dosyada öneriler önceliğe, sonra alana göre sıralıdır.

## Yeniden üretme

```bash
python3 -m venv .venv && .venv/bin/pip install osmium shapely pyproj
mkdir -p data && curl -L -o data/turkey-latest.osm.pbf https://download.geofabrik.de/europe/turkey-latest.osm.pbf
.venv/bin/python tools/osm_extract.py data/turkey-latest.osm.pbf data/bulusma_onerileri.sqlite
python3 tools/build_package.py data/bulusma_onerileri.sqlite docs <dokum-tarihi>
```

## Lisans ve atıf

Veri © [OpenStreetMap katkıcıları](https://www.openstreetmap.org/copyright), [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/) ile sunulur. Bu depodaki türetilmiş veri de ODbL kapsamındadır. Kullanan uygulama ve sayfalar "© OpenStreetMap katkıcıları" atfını göstermelidir.
