# -*- coding: utf-8 -*-
"""
katalog.py — OTOMATİK KEŞİF (Seviye 2)
--------------------------------------
Menü artık ELLE yazılmaz. Sistem kaynakca/ klasörünü tarar ve her .md
dosyasından öğeyi OTOMATİK üretir.

Yeni bir kişi/mekan/lezzet/doğa eklemek için:
  -> İlgili klasöre (kaynakca/kisiler, /mekanlar, /lezzetler, /doga)
     yeni bir .md dosyası koymak YETER. Kod veya katalog düzenlemek GEREKMEZ.

Her .md dosyasının üst kısmında şu meta yorumlar bulunur:
  # Görünen Uzun Başlık
  <!-- persona: kategori.persona_adi | kart: ... -->
  <!-- ad: Menüde Görünecek Kısa Ad -->
  <!-- karsilama: Sohbet açılışında botun ilk sözü -->

Bu meta'lar okunur; 'persona' zorunludur (yoksa dosya atlanır), 'ad' ve
'karsilama' yoksa başlıktan/ösablondan türetilir.
"""

import os
import re

KOK_DIZIN = os.path.dirname(os.path.abspath(__file__))
KAYNAKCA_DIZIN = os.path.join(KOK_DIZIN, "kaynakca")

# Klasör kodu -> menüde görünecek kategori adı ve sıra.
# (Yeni bir KLASÖR/kategori eklemek istersen buraya bir satır eklersin;
#  ama mevcut kategorilere ÖĞE eklemek için buraya dokunmana gerek yok.)
KATEGORI_ADLARI = {
    "kisiler":   {"ad": "Tarihi Kişiler",     "sira": 1},
    "mekanlar":  {"ad": "Tarihi Mekanlar",    "sira": 2},
    "lezzetler": {"ad": "Yöresel Lezzetler",  "sira": 3},
    "doga":      {"ad": "Doğal Güzellikler",  "sira": 4},
}


def _meta_oku(dosya_yolu):
    """Bir .md dosyasının üst yorumlarından meta bilgileri çıkarır."""
    with open(dosya_yolu, "r", encoding="utf-8") as f:
        # sadece ilk ~15 satır yeter (meta üstte)
        bas = "".join([next(f, "") for _ in range(15)])

    # başlık (# ...)
    m_baslik = re.search(r"^#\s+(.+)$", bas, re.M)
    baslik = m_baslik.group(1).strip() if m_baslik else None

    # persona: "kategori.persona_adi"
    m_persona = re.search(r"<!--\s*persona:\s*([a-zA-Z_]+)\.([a-zA-Z_]+)", bas)
    kategori = m_persona.group(1) if m_persona else None
    persona = m_persona.group(2) if m_persona else None

    # ad
    m_ad = re.search(r"<!--\s*ad:\s*(.+?)\s*-->", bas)
    ad = m_ad.group(1).strip() if m_ad else None

    # karsilama
    m_kar = re.search(r"<!--\s*karsilama:\s*(.+?)\s*-->", bas)
    karsilama = m_kar.group(1).strip() if m_kar else None

    # ad yoksa başlıktan türet (parantezli kısmı at)
    if not ad and baslik:
        ad = re.sub(r"\s*\(.*?\)\s*$", "", baslik).strip() or baslik

    return {
        "kategori": kategori,
        "persona": persona,
        "ad": ad,
        "karsilama": karsilama or (f"{ad} hakkında merak ettiğinizi sorabilirsiniz." if ad else ""),
    }


def _katalog_kur():
    """kaynakca/ klasörünü tarayıp KATALOG sözlüğünü otomatik üretir."""
    katalog = {}
    for klasor in sorted(os.listdir(KAYNAKCA_DIZIN)):
        kdir = os.path.join(KAYNAKCA_DIZIN, klasor)
        if not os.path.isdir(kdir):
            continue

        kat_ad = KATEGORI_ADLARI.get(klasor, {}).get("ad", klasor.capitalize())
        ogeler = {}

        for fn in sorted(os.listdir(kdir)):
            if not fn.endswith(".md"):
                continue
            dosya_kodu = fn[:-3]  # .md'yi at
            meta = _meta_oku(os.path.join(kdir, fn))

            if not meta["persona"]:
                # persona bulunamadıysa bu dosya menüye alınmaz (bozuk/eksik)
                continue

            ogeler[dosya_kodu] = {
                "ad": meta["ad"] or dosya_kodu,
                "persona": meta["persona"],
                "klasor": klasor,
                "dosya": dosya_kodu,
                "karsilama": meta["karsilama"],
            }

        if ogeler:
            katalog[klasor] = {"ad": kat_ad, "ogeler": ogeler}

    # kategorileri istenen sıraya diz
    sirali = dict(sorted(
        katalog.items(),
        key=lambda kv: KATEGORI_ADLARI.get(kv[0], {}).get("sira", 99)
    ))
    return sirali


# Uygulama açılışında bir kez taranır.
KATALOG = _katalog_kur()


def yeniden_yukle():
    """Çalışırken yeni .md eklendiyse kataloğu tazelemek için."""
    global KATALOG
    KATALOG = _katalog_kur()
    return KATALOG


def oge_getir(kategori, oge):
    """Kategori ve öğe koduna göre öğe sözlüğünü döndürür (yoksa None)."""
    return KATALOG.get(kategori, {}).get("ogeler", {}).get(oge)