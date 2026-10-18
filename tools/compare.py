"""Yayındaki paketi (docs/) yeni üretilmiş bir paketle karşılaştırır; hiçbir dosyaya yazmaz.

Kullanım: python3 tools/compare.py docs data/yeni [--ornek 10]
Çıkış kodu: 0 aynı, 1 farklı.

Her iki klasörde de build_package.py çıktısı (manifest.json + il/) olmalıdır. Rapor:
  - sürüm, ilçe, kayıt ve bayt toplamları
  - türe göre kayıt sayıları
  - eklenen / çıkan ilçeler, en çok değişen iller ve ilçeler
  - OSM kimliğine göre eklenen, çıkan ve değişen öneriler (tür, ad, alan ya da 50 m'den fazla yer değişikliği)
Önerilerin kimliği OSM kimliğidir (ör. w177436492); aynı kimlik iki pakette varsa "aynı yer" sayılır.
"""
import argparse
import json
import math
import os
import sys
from collections import Counter

YER_ESIGI_M = 50


def yukle(klasor):
    with open(os.path.join(klasor, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    noktalar = {}
    for ilce in manifest["ilceler"]:
        with open(os.path.join(klasor, ilce["dosya"]), encoding="utf-8") as f:
            for ozellik in json.load(f)["features"]:
                lng, lat = ozellik["geometry"]["coordinates"]
                noktalar[ozellik["id"]] = dict(ozellik["properties"], lat=lat, lng=lng,
                                               il=ilce["il"], ilce=ilce["ilce"])
    return manifest, noktalar


def mesafe_m(a, b):
    k = math.cos(math.radians((a["lat"] + b["lat"]) / 2))
    return math.hypot((a["lat"] - b["lat"]) * 111_320, (a["lng"] - b["lng"]) * 111_320 * k)


def fark(eski, yeni):
    d = yeni - eski
    return f"{d:+,}".replace(",", ".") if d else "0"


def sayi(n):
    return f"{n:,}".replace(",", ".")


def tablo(baslik, satirlar):
    print(f"\n{baslik}")
    genislik = max((len(s[0]) for s in satirlar), default=10)
    print(f"  {'':{genislik}}  {'eski':>9}  {'yeni':>9}  {'fark':>8}")
    for ad, e, y in satirlar:
        print(f"  {ad:{genislik}}  {sayi(e):>9}  {sayi(y):>9}  {fark(e, y):>8}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("eski")
    ap.add_argument("yeni")
    ap.add_argument("--ornek", type=int, default=10, help="her listeden gösterilecek örnek sayısı")
    a = ap.parse_args()

    me, ne = yukle(a.eski)
    my, ny = yukle(a.yeni)

    print(f"Eski: {a.eski}  sürüm {me['surum']}  (en küçük alan {me['min_m2']} m²)")
    print(f"Yeni: {a.yeni}  sürüm {my['surum']}  (en küçük alan {my['min_m2']} m²)")
    if me["min_m2"] != my["min_m2"]:
        print("UYARI: en küçük alan eşiği farklı; sayılar doğrudan karşılaştırılamaz.")

    tablo("Toplam", [
        ("ilçe", len(me["ilceler"]), len(my["ilceler"])),
        ("kayıt", len(ne), len(ny)),
        ("bayt", sum(i["boyut"] for i in me["ilceler"]), sum(i["boyut"] for i in my["ilceler"])),
        ("adı olan kayıt", sum(1 for p in ne.values() if p["ad"]), sum(1 for p in ny.values() if p["ad"])),
    ])

    te, ty = Counter(p["tur"] for p in ne.values()), Counter(p["tur"] for p in ny.values())
    tablo("Türe göre", [(t, te[t], ty[t]) for t in sorted(set(te) | set(ty), key=lambda t: -ty[t])])

    ie = {(i["il"], i["ilce"]): i for i in me["ilceler"]}
    iy = {(i["il"], i["ilce"]): i for i in my["ilceler"]}
    eklenen_ilce, cikan_ilce = sorted(iy.keys() - ie.keys()), sorted(ie.keys() - iy.keys())
    ayni_dosya = sum(1 for k in ie.keys() & iy.keys() if ie[k]["sha256"] == iy[k]["sha256"])
    print(f"\nİlçe dosyaları: {sayi(ayni_dosya)} aynı, "
          f"{sayi(len(ie.keys() & iy.keys()) - ayni_dosya)} değişmiş, "
          f"{len(eklenen_ilce)} yeni, {len(cikan_ilce)} çıkan")
    for baslik, liste in (("Yeni ilçeler", eklenen_ilce), ("Çıkan ilçeler", cikan_ilce)):
        if liste:
            print(f"  {baslik}: " + ", ".join(f"{il}/{ilce}" for il, ilce in liste))

    ile, ily = Counter(p["il"] for p in ne.values()), Counter(p["il"] for p in ny.values())
    degisen_il = sorted(set(ile) | set(ily), key=lambda il: -abs(ily[il] - ile[il]))
    degisen_il = [il for il in degisen_il if ily[il] != ile[il]][:a.ornek]
    if degisen_il:
        tablo(f"En çok değişen iller (ilk {a.ornek})", [(il, ile[il], ily[il]) for il in degisen_il])

    eklenen = [k for k in ny if k not in ne]
    cikan = [k for k in ne if k not in ny]
    degisen = []
    for k in ne.keys() & ny.keys():
        e, y = ne[k], ny[k]
        nedenler = []
        if e["tur"] != y["tur"]:
            nedenler.append(f"tür {e['tur']} → {y['tur']}")
        if e["ad"] != y["ad"]:
            nedenler.append(f"ad {e['ad']!r} → {y['ad']!r}")
        if e["m2"] != y["m2"]:
            nedenler.append(f"alan {sayi(e['m2'])} → {sayi(y['m2'])} m²")
        m = mesafe_m(e, y)
        if m > YER_ESIGI_M:
            nedenler.append(f"yer {m:.0f} m kaydı")
        if nedenler:
            degisen.append((k, nedenler))

    ce, cy = Counter(), Counter()
    for k in cikan:
        ce[(ne[k]["il"], ne[k]["ilce"])] += 1
    for k in eklenen:
        cy[(ny[k]["il"], ny[k]["ilce"])] += 1
    print(f"\nÖneriler: {sayi(len(eklenen))} yeni, {sayi(len(cikan))} çıkan, {sayi(len(degisen))} değişmiş, "
          f"{sayi(len(ne.keys() & ny.keys()) - len(degisen))} aynı")
    hareket = sorted(set(ce) | set(cy), key=lambda x: -(ce[x] + cy[x]))[:a.ornek]
    if hareket:
        print(f"\nEn çok hareket olan ilçeler (ilk {a.ornek})")
        for il, ilce in hareket:
            print(f"  {il}/{ilce}: +{cy[(il, ilce)]} yeni, -{ce[(il, ilce)]} çıkan")

    def ornekle(baslik, kimlikler, kaynak):
        if not kimlikler:
            return
        print(f"\n{baslik} (örnek {min(a.ornek, len(kimlikler))})")
        for k in sorted(kimlikler, key=lambda k: -kaynak[k]["m2"])[:a.ornek]:
            p = kaynak[k]
            print(f"  {k:<14} {p['tur']:<12} {sayi(p['m2']):>9} m²  {p['il']}/{p['ilce']}  {p['ad'] or '(adsız)'}")

    ornekle("Yeni öneriler, en büyükler", eklenen, ny)
    ornekle("Çıkan öneriler, en büyükler", cikan, ne)
    if degisen:
        print(f"\nDeğişen öneriler (örnek {min(a.ornek, len(degisen))})")
        for k, nedenler in sorted(degisen, key=lambda x: -ny[x[0]]["m2"])[:a.ornek]:
            p = ny[k]
            print(f"  {k:<14} {p['il']}/{p['ilce']}: " + "; ".join(nedenler))

    if not eklenen and not cikan and not degisen and not eklenen_ilce and not cikan_ilce:
        print("\nSonuç: iki paket aynı öneri listesini içeriyor; yeniden yayımlamaya gerek yok.")
        return 0
    print("\nSonuç: paketler farklı.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
