# -*- coding: utf-8 -*-
"""
admin_motoru.py
----------------
Admin paneli için backend mantığı:
  - Basit kullanıcı adı/şifre girişi (env'den okunur), bellek içi token'lar.
  - Persona/bot: EKLE / GÜNCELLE / SİL — kaynakca/{kategori}/{kod}.md,
    gorseller/{kategori}/{kod}.{uzanti} ve OPSİYONEL anlatim/{kategori}/{kod}.md
    dosyalarını yönetir, katalog.yeniden_yukle() ile anında görünür kılar.
  - Rota Planlayıcı mekanı: EKLE / GÜNCELLE / SİL — mekanlar tablosu satırı ve
    OPSİYONEL rota_anlatim/{id}.md dosyasını yönetir. Güncellemede/silmede
    kategori önbelleği (rota_motoru._KATEGORI_ONBELLEK) da temizlenir ki
    açıklaması değişen/silinen bir mekan yanlış/eski kategoride kalmasın.

NOT: Bu basit bir "tek admin" modelidir; çoklu kullanıcı/rol yönetimi yoktur.
Token'lar RAM'de tutulur (sunucu yeniden başlarsa geçersiz olur) — sohbet
session'larıyla aynı, projede zaten kurulu olan desendir.
"""

import os
import re
import secrets
import sqlite3
from pathlib import Path

KOK_DIZIN = Path(__file__).parent
KAYNAKCA_DIZIN = KOK_DIZIN / "kaynakca"
GORSELLER_DIZIN = KOK_DIZIN / "gorseller"
ANLATIM_DIZIN = KOK_DIZIN / "anlatim"

GECERLI_GORSEL_UZANTILARI = {".jpg", ".jpeg", ".png", ".webp"}

# Admin eliyle eklenen içerikler için kategori -> kullanılacak persona adı.
KATEGORI_PERSONA = {
    "kisiler": "sahsiyet_rehberi",
    "mekanlar": "mekan_rehberi",
    "lezzetler": "asci",
    "doga": "doga_rehberi",
    "tescil": "tescil",
}

# Sadece kozmetik: .md dosyasının üstündeki "kart:" meta etiketi.
KATEGORI_KART_ETIKETI = {
    "kisiler": "Tarih ve Kültür",
    "mekanlar": "Tarih ve Kültür",
    "lezzetler": "Lezzet ve Doğa",
    "doga": "Lezzet ve Doğa",
    "tescil": "Tesciller",
}

_TR_HARITA = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i",
    "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u",
})


class AdminHatasi(Exception):
    """Admin işlemlerinde kullanıcıya gösterilecek anlaşılır hata."""
    pass


def _slugify(metin: str) -> str:
    metin = (metin or "").translate(_TR_HARITA).lower()
    metin = re.sub(r"[^a-z0-9]+", "_", metin).strip("_")
    return metin


def _katalogu_tazele():
    import katalog
    katalog.yeniden_yukle()


# --- Persona / içerik: TEK ÖĞE GETİR (düzenleme formunu ön-doldurmak için) ---

def persona_getir(kategori: str, kod: str) -> dict:
    if kategori not in KATEGORI_PERSONA:
        raise AdminHatasi(f"Geçersiz kategori: {kategori!r}")

    md_yolu = KAYNAKCA_DIZIN / kategori / f"{kod}.md"
    if not md_yolu.is_file():
        raise AdminHatasi(f"'{kod}' koduyla bir içerik bulunamadı.")
    metin = md_yolu.read_text(encoding="utf-8")

    m_ad = re.search(r"<!--\s*ad:\s*(.+?)\s*-->", metin)
    m_kar = re.search(r"<!--\s*karsilama:\s*(.+?)\s*-->", metin)
    ad = m_ad.group(1).strip() if m_ad else ""
    karsilama = m_kar.group(1).strip() if m_kar else ""

    # İçerik: metindeki SON meta yorumundan (<!-- ... -->) sonraki kısım.
    son_meta = None
    for eslesme in re.finditer(r"<!--.*?-->", metin, re.S):
        son_meta = eslesme
    icerik = metin[son_meta.end():].strip() if son_meta else metin.strip()

    anlatim_yolu = ANLATIM_DIZIN / kategori / f"{kod}.md"
    anlatim = anlatim_yolu.read_text(encoding="utf-8").strip() if anlatim_yolu.is_file() else None

    gorsel_var = any(
        (GORSELLER_DIZIN / kategori / f"{kod}{uzanti}").is_file()
        for uzanti in GECERLI_GORSEL_UZANTILARI
    )

    return {
        "kod": kod,
        "kategori": kategori,
        "ad": ad,
        "karsilama": karsilama,
        "icerik": icerik,
        "anlatim": anlatim,
        "gorsel_var": gorsel_var,
    }


# --- Kimlik doğrulama (basit, bellek içi token) ---

_GECERLI_TOKENLAR: set[str] = set()


def giris_yap(kullanici_adi: str, sifre: str) -> str:
    beklenen_kadi = os.environ.get("ADMIN_KULLANICI_ADI")
    beklenen_sifre = os.environ.get("ADMIN_SIFRE")
    if not beklenen_kadi or not beklenen_sifre:
        raise AdminHatasi(
            "Sunucuda ADMIN_KULLANICI_ADI / ADMIN_SIFRE tanımlı değil (.env dosyasını kontrol edin)."
        )
    if kullanici_adi != beklenen_kadi or sifre != beklenen_sifre:
        raise AdminHatasi("Kullanıcı adı veya şifre hatalı.")
    token = secrets.token_urlsafe(32)
    _GECERLI_TOKENLAR.add(token)
    return token


def token_gecerli_mi(token: str) -> bool:
    return token in _GECERLI_TOKENLAR


def cikis_yap(token: str) -> None:
    _GECERLI_TOKENLAR.discard(token)


# --- Persona / içerik: EKLE ---

def persona_ekle(
    kategori: str,
    ad: str,
    karsilama: str,
    icerik: str,
    kod: str | None,
    gorsel_bytes: bytes,
    gorsel_uzanti: str,
    anlatim: str | None = None,
) -> dict:
    if kategori not in KATEGORI_PERSONA:
        gecerli = ", ".join(KATEGORI_PERSONA.keys())
        raise AdminHatasi(f"Geçersiz kategori: {kategori!r}. Geçerli değerler: {gecerli}")

    ad = (ad or "").strip()
    karsilama = (karsilama or "").strip()
    icerik = (icerik or "").strip()
    if not ad or not karsilama or not icerik:
        raise AdminHatasi("'ad', 'karsilama' ve 'icerik' alanları boş olamaz.")

    if gorsel_uzanti.lower() not in GECERLI_GORSEL_UZANTILARI:
        raise AdminHatasi(
            f"Desteklenmeyen görsel uzantısı: {gorsel_uzanti!r}. "
            f"İzin verilenler: {', '.join(sorted(GECERLI_GORSEL_UZANTILARI))}"
        )
    if not gorsel_bytes:
        raise AdminHatasi("Görsel dosyası boş görünüyor.")

    dosya_kodu = _slugify(kod) if kod else _slugify(ad)
    if not dosya_kodu:
        raise AdminHatasi("Geçerli bir dosya kodu üretilemedi; farklı bir 'ad' deneyin.")

    kaynakca_klasoru = KAYNAKCA_DIZIN / kategori
    gorseller_klasoru = GORSELLER_DIZIN / kategori
    kaynakca_klasoru.mkdir(parents=True, exist_ok=True)
    gorseller_klasoru.mkdir(parents=True, exist_ok=True)

    md_yolu = kaynakca_klasoru / f"{dosya_kodu}.md"
    if md_yolu.exists():
        raise AdminHatasi(
            f"'{dosya_kodu}' koduyla bir içerik zaten var. Farklı bir ad/kod deneyin."
        )

    persona_adi = KATEGORI_PERSONA[kategori]
    kart_etiketi = KATEGORI_KART_ETIKETI[kategori]

    md_icerigi = (
        f"# {ad}\n\n"
        f"<!-- persona: {kategori}.{persona_adi} | kart: {kart_etiketi} -->\n"
        f"<!-- ad: {ad} -->\n"
        f"<!-- karsilama: {karsilama} -->\n\n"
        f"{icerik}\n"
    )
    md_yolu.write_text(md_icerigi, encoding="utf-8")

    gorsel_yolu = gorseller_klasoru / f"{dosya_kodu}{gorsel_uzanti.lower()}"
    gorsel_yolu.write_bytes(gorsel_bytes)

    anlatim_eklendi = False
    if anlatim and anlatim.strip():
        anlatim_klasoru = ANLATIM_DIZIN / kategori
        anlatim_klasoru.mkdir(parents=True, exist_ok=True)
        (anlatim_klasoru / f"{dosya_kodu}.md").write_text(anlatim.strip(), encoding="utf-8")
        anlatim_eklendi = True

    _katalogu_tazele()

    return {
        "kod": dosya_kodu,
        "kategori": kategori,
        "ad": ad,
        "anlatim_eklendi": anlatim_eklendi,
        "durum": "eklendi",
    }


# --- Persona / içerik: GÜNCELLE ---

def persona_guncelle(
    kategori: str,
    kod: str,
    ad: str,
    karsilama: str,
    icerik: str,
    anlatim: str,
    anlatim_kaldir: bool,
    gorsel_bytes: bytes | None,
    gorsel_uzanti: str | None,
) -> dict:
    """anlatim_kaldir=True -> anlatımı KALDIRIR (anlatim metninin içeriği
    ÖNEMSİZDİR, görmezden gelinir). anlatim_kaldir=False VE anlatim boşsa ->
    mevcut anlatıma DOKUNULMAZ (hem "alan hiç gönderilmedi" hem "boş
    gönderildi" durumu FastAPI/Starlette'in multipart form ayrıştırmasında
    AYIRT EDİLEMEDİĞİ için — ikisi de aynı şekilde "" olarak gelir — kaldırma
    niyeti SADECE bu ayrı bayrakla ifade edilir, boş string'e GÜVENİLMEZ).
    anlatim_kaldir=False VE anlatim doluysa -> yazılır/üzerine yazılır.
    gorsel_bytes=None -> mevcut görsele DOKUNMA."""
    if kategori not in KATEGORI_PERSONA:
        raise AdminHatasi(f"Geçersiz kategori: {kategori!r}")

    md_yolu = KAYNAKCA_DIZIN / kategori / f"{kod}.md"
    if not md_yolu.is_file():
        raise AdminHatasi(f"'{kod}' koduyla bir içerik bulunamadı; güncellemek için önce eklemelisiniz.")

    ad = (ad or "").strip()
    karsilama = (karsilama or "").strip()
    icerik = (icerik or "").strip()
    if not ad or not karsilama or not icerik:
        raise AdminHatasi("'ad', 'karsilama' ve 'icerik' alanları boş olamaz.")

    persona_adi = KATEGORI_PERSONA[kategori]
    kart_etiketi = KATEGORI_KART_ETIKETI[kategori]
    md_icerigi = (
        f"# {ad}\n\n"
        f"<!-- persona: {kategori}.{persona_adi} | kart: {kart_etiketi} -->\n"
        f"<!-- ad: {ad} -->\n"
        f"<!-- karsilama: {karsilama} -->\n\n"
        f"{icerik}\n"
    )
    md_yolu.write_text(md_icerigi, encoding="utf-8")

    if gorsel_bytes:
        if not gorsel_uzanti or gorsel_uzanti.lower() not in GECERLI_GORSEL_UZANTILARI:
            raise AdminHatasi(
                f"Desteklenmeyen görsel uzantısı: {gorsel_uzanti!r}. "
                f"İzin verilenler: {', '.join(sorted(GECERLI_GORSEL_UZANTILARI))}"
            )
        gorseller_klasoru = GORSELLER_DIZIN / kategori
        for uzanti in GECERLI_GORSEL_UZANTILARI:
            eski = gorseller_klasoru / f"{kod}{uzanti}"
            if eski.is_file():
                eski.unlink()
        (gorseller_klasoru / f"{kod}{gorsel_uzanti.lower()}").write_bytes(gorsel_bytes)

    anlatim_yolu = ANLATIM_DIZIN / kategori / f"{kod}.md"
    if anlatim_kaldir:
        if anlatim_yolu.is_file():
            anlatim_yolu.unlink()
    elif anlatim and anlatim.strip():
        anlatim_yolu.parent.mkdir(parents=True, exist_ok=True)
        anlatim_yolu.write_text(anlatim.strip(), encoding="utf-8")
    # else: anlatim_kaldir=False VE metin boş -> mevcut anlatıma DOKUNMA

    _katalogu_tazele()

    return {"kod": kod, "kategori": kategori, "ad": ad, "durum": "guncellendi"}


# --- Persona / içerik: SİL ---

def persona_sil(kategori: str, kod: str) -> dict:
    if kategori not in KATEGORI_PERSONA:
        raise AdminHatasi(f"Geçersiz kategori: {kategori!r}")

    md_yolu = KAYNAKCA_DIZIN / kategori / f"{kod}.md"
    if not md_yolu.is_file():
        raise AdminHatasi(f"'{kod}' koduyla bir içerik bulunamadı.")
    md_yolu.unlink()

    gorsel_silindi = False
    for uzanti in GECERLI_GORSEL_UZANTILARI:
        gorsel_yolu = GORSELLER_DIZIN / kategori / f"{kod}{uzanti}"
        if gorsel_yolu.is_file():
            gorsel_yolu.unlink()
            gorsel_silindi = True

    anlatim_silindi = False
    anlatim_yolu = ANLATIM_DIZIN / kategori / f"{kod}.md"
    if anlatim_yolu.is_file():
        anlatim_yolu.unlink()
        anlatim_silindi = True

    _katalogu_tazele()

    return {
        "kod": kod,
        "kategori": kategori,
        "gorsel_silindi": gorsel_silindi,
        "anlatim_silindi": anlatim_silindi,
        "durum": "silindi",
    }


# --- Rota Planlayıcı mekanı: TEK ÖĞE GETİR (anlatım METNİYLE birlikte —
#     /admin/rota-yerleri listesi anlatim_var bayrağı verir ama METNİ vermez) ---

def rota_yeri_getir(mekan_id: int) -> dict:
    from rota_motoru import DB_YOLU, ROTA_ANLATIM_DIZIN

    con = sqlite3.connect(DB_YOLU)
    con.row_factory = sqlite3.Row
    try:
        satir = con.execute("SELECT * FROM mekanlar WHERE id = ?", (mekan_id,)).fetchone()
    finally:
        con.close()
    if satir is None:
        raise AdminHatasi(f"id={mekan_id} ile bir mekan bulunamadı.")
    m = dict(satir)

    anlatim_yolu = ROTA_ANLATIM_DIZIN / f"{mekan_id}.md"
    anlatim = anlatim_yolu.read_text(encoding="utf-8").strip() if anlatim_yolu.is_file() else None

    return {
        "id": m["id"],
        "ad": m["ad"],
        "enlem": m["enlem"],
        "boylam": m["boylam"],
        "sure_dk": m["sure_dk"],
        "aciklama": m["aciklama"],
        "anlatim": anlatim,
    }


# --- Rota Planlayıcı mekanı: EKLE ---

def rota_yeri_ekle(
    ad: str,
    enlem: float,
    boylam: float,
    sure_dk: int,
    aciklama: str,
    anlatim: str | None = None,
) -> dict:
    ad = (ad or "").strip()
    aciklama = (aciklama or "").strip()
    if not ad or not aciklama:
        raise AdminHatasi("'ad' ve 'aciklama' alanları boş olamaz.")
    if sure_dk is None or sure_dk <= 0:
        raise AdminHatasi("'sure_dk' sıfırdan büyük bir sayı olmalı.")

    from rota_motoru import DB_YOLU, ROTA_ANLATIM_DIZIN

    con = sqlite3.connect(DB_YOLU)
    try:
        imlec = con.execute(
            "INSERT INTO mekanlar (ad, enlem, boylam, sure_dk, aciklama) VALUES (?, ?, ?, ?, ?)",
            (ad, enlem, boylam, sure_dk, aciklama),
        )
        con.commit()
        yeni_id = imlec.lastrowid
    finally:
        con.close()

    anlatim_eklendi = False
    if anlatim and anlatim.strip():
        ROTA_ANLATIM_DIZIN.mkdir(parents=True, exist_ok=True)
        (ROTA_ANLATIM_DIZIN / f"{yeni_id}.md").write_text(anlatim.strip(), encoding="utf-8")
        anlatim_eklendi = True

    return {"id": yeni_id, "anlatim_eklendi": anlatim_eklendi, "durum": "eklendi"}


# --- Rota Planlayıcı mekanı: GÜNCELLE ---

def rota_yeri_guncelle(
    mekan_id: int,
    ad: str,
    enlem: float,
    boylam: float,
    sure_dk: int,
    aciklama: str,
    anlatim: str | None,
) -> dict:
    """anlatim=None -> mevcut anlatıma dokunma. anlatim="" -> kaldır.
    anlatim="metin" -> yaz/üzerine yaz. aciklama değiştiği için kategori
    önbelleği temizlenir (bir sonraki rota isteğinde yeniden sınıflandırılır)."""
    ad = (ad or "").strip()
    aciklama = (aciklama or "").strip()
    if not ad or not aciklama:
        raise AdminHatasi("'ad' ve 'aciklama' alanları boş olamaz.")
    if sure_dk is None or sure_dk <= 0:
        raise AdminHatasi("'sure_dk' sıfırdan büyük bir sayı olmalı.")

    from rota_motoru import DB_YOLU, ROTA_ANLATIM_DIZIN, kategori_onbellegini_temizle

    con = sqlite3.connect(DB_YOLU)
    try:
        imlec = con.execute(
            "UPDATE mekanlar SET ad=?, enlem=?, boylam=?, sure_dk=?, aciklama=? WHERE id=?",
            (ad, enlem, boylam, sure_dk, aciklama, mekan_id),
        )
        con.commit()
        if imlec.rowcount == 0:
            raise AdminHatasi(f"id={mekan_id} ile bir mekan bulunamadı.")
    finally:
        con.close()

    kategori_onbellegini_temizle(mekan_id)

    anlatim_yolu = ROTA_ANLATIM_DIZIN / f"{mekan_id}.md"
    if anlatim is not None:
        if anlatim.strip():
            ROTA_ANLATIM_DIZIN.mkdir(parents=True, exist_ok=True)
            anlatim_yolu.write_text(anlatim.strip(), encoding="utf-8")
        elif anlatim_yolu.is_file():
            anlatim_yolu.unlink()

    return {"id": mekan_id, "durum": "guncellendi"}


# --- Rota Planlayıcı mekanı: SİL ---

def rota_yeri_sil(mekan_id: int) -> dict:
    from rota_motoru import DB_YOLU, ROTA_ANLATIM_DIZIN, kategori_onbellegini_temizle

    con = sqlite3.connect(DB_YOLU)
    try:
        imlec = con.execute("DELETE FROM mekanlar WHERE id = ?", (mekan_id,))
        con.commit()
        if imlec.rowcount == 0:
            raise AdminHatasi(f"id={mekan_id} ile bir mekan bulunamadı.")
    finally:
        con.close()

    kategori_onbellegini_temizle(mekan_id)

    anlatim_silindi = False
    anlatim_yolu = ROTA_ANLATIM_DIZIN / f"{mekan_id}.md"
    if anlatim_yolu.is_file():
        anlatim_yolu.unlink()
        anlatim_silindi = True

    return {"id": mekan_id, "anlatim_silindi": anlatim_silindi, "durum": "silindi"}