# -*- coding: utf-8 -*-
"""
admin_motoru.py
----------------
Admin paneli için backend mantığı:
  - Basit kullanıcı adı/şifre girişi (env'den okunur), bellek içi token'lar.
  - Yeni persona/bot ekleme: kaynakca/{kategori}/{kod}.md + gorseller/{kategori}/{kod}.{uzanti}
    dosyalarını oluşturur, katalog.yeniden_yukle() ile anında görünür kılar.
  - Rota Planlayıcı için yeni gezilecek yer ekleme: mekanlar tablosuna satır ekler.

NOT: Bu basit bir "tek admin" modelidir; çoklu kullanıcı/rol yönetimi yoktur.
Token'lar RAM'de tutulur (sunucu yeniden başlarsa geçersiz olur) — bu, sohbet
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

GECERLI_GORSEL_UZANTILARI = {".jpg", ".jpeg", ".png", ".webp"}

# Admin eliyle eklenen içerikler için kategori -> kullanılacak persona adı.
# (Diyojen, Katip Kadir gibi özel/elle yazılmış personalar buraya dahil değildir;
#  admin panelinden eklenen içerikler her zaman o kategorinin GENEL rehberini kullanır.)
KATEGORI_PERSONA = {
    "kisiler": "sahsiyet_rehberi",
    "mekanlar": "mekan_rehberi",
    "lezzetler": "asci",
    "doga": "doga_rehberi",
    "tescil": "tescil",
}

# Sadece kozmetik: .md dosyasının üstündeki "kart:" meta etiketi (katalog.py
# bunu işlevsel olarak kullanmaz, yalnızca dosya içinde belgeleyici bilgidir).
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
    """'İ. Alaaddin Keykubat' -> 'i_alaaddin_keykubat' gibi dosya-adı-uyumlu
    bir koda çevirir."""
    metin = (metin or "").translate(_TR_HARITA).lower()
    metin = re.sub(r"[^a-z0-9]+", "_", metin).strip("_")
    return metin


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


# --- Persona / içerik ekleme ---

def persona_ekle(
    kategori: str,
    ad: str,
    karsilama: str,
    icerik: str,
    kod: str | None,
    gorsel_bytes: bytes,
    gorsel_uzanti: str,
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

    # Katalog önbelleğini anında tazele (sunucu yeniden başlatmaya gerek kalmaz)
    import katalog
    katalog.yeniden_yukle()

    return {"kod": dosya_kodu, "kategori": kategori, "ad": ad, "durum": "eklendi"}


# --- Rota Planlayıcı: yeni gezilecek yer ekleme ---

def rota_yeri_ekle(
    ad: str,
    enlem: float,
    boylam: float,
    sure_dk: int,
    aciklama: str,
) -> int:
    ad = (ad or "").strip()
    aciklama = (aciklama or "").strip()
    if not ad or not aciklama:
        raise AdminHatasi("'ad' ve 'aciklama' alanları boş olamaz.")
    if sure_dk is None or sure_dk <= 0:
        raise AdminHatasi("'sure_dk' sıfırdan büyük bir sayı olmalı.")

    from rota_motoru import DB_YOLU  # tek gerçek kaynak: aynı .db dosyası

    con = sqlite3.connect(DB_YOLU)
    try:
        imlec = con.execute(
            "INSERT INTO mekanlar (ad, enlem, boylam, sure_dk, aciklama) "
            "VALUES (?, ?, ?, ?, ?)",
            (ad, enlem, boylam, sure_dk, aciklama),
        )
        con.commit()
        return imlec.lastrowid
    finally:
        con.close()