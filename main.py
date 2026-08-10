# -*- coding: utf-8 -*-
"""
main.py — Sinop Akıllı Turizm Platformu - Terminal Prototipi

Hiyerarşi: 4 Kategori -> öğe listesi -> karakterle sohbet (while True)
Navigasyon: 'q' her seviyede bir üst seviyeye çıkarır.
Menü verisi katalog.py'den okunur (API ile ortak tek kaynak).
"""

from bot_engine import karakterle_sohbet
import katalog


def secenek_menusu_goster(baslik, ogeler):
    """ogeler: [(kod, sozluk), ...] -> seçilen sözlük veya None ('q')."""
    while True:
        print("\n" + "-" * 60)
        print(f"  {baslik}")
        print("-" * 60)
        for i, (_, oge) in enumerate(ogeler, start=1):
            print(f"  {i}) {oge['ad']}")
        print("  q) Üst menüye dön")
        print("-" * 60)

        secim = input("Seçiminiz: ").strip().lower()
        if secim == "q":
            return None
        if not secim.isdigit():
            print(">> Lütfen bir numara girin veya 'q' yazın.")
            continue
        no = int(secim)
        if 1 <= no <= len(ogeler):
            return ogeler[no - 1][1]
        print(">> Geçersiz numara.")


def kategori_gez(kategori_kodu):
    kat = katalog.KATALOG[kategori_kodu]
    ogeler = list(kat["ogeler"].items())
    while True:
        oge = secenek_menusu_goster(kat["ad"].upper(), ogeler)
        if oge is None:
            return
        karakterle_sohbet(
            baslik=oge["ad"],
            kategori=kategori_kodu,
            persona_adi=oge["persona"],
            alt_klasor=oge["klasor"],
            dosya_adi=oge["dosya"],
            karsilama=oge.get("karsilama"),
        )


# Her kategori için ayrı fonksiyon (hepsi kategori_gez'e sarar)
def kategori_tarihi_kisiler():  kategori_gez("kisiler")
def kategori_tarihi_mekanlar(): kategori_gez("mekanlar")
def kategori_lezzetler():       kategori_gez("lezzetler")
def kategori_doga():            kategori_gez("doga")


KATEGORILER = [
    ("Tarihi Kişiler", kategori_tarihi_kisiler),
    ("Tarihi Mekanlar", kategori_tarihi_mekanlar),
    ("Yöresel Lezzetler", kategori_lezzetler),
    ("Doğal Güzellikler", kategori_doga),
]


def ana_menu():
    print("\n" + "#" * 60)
    print("#  SİNOP AKILLI TURİZM PLATFORMU")
    print("#  Terminal Prototipi")
    print("#" * 60)

    while True:
        print("\n" + "=" * 60)
        print("  ANA MENÜ - Bir kategori seçin")
        print("=" * 60)
        for i, (ad, _) in enumerate(KATEGORILER, start=1):
            print(f"  {i}) {ad}")
        print("  q) Çıkış")
        print("=" * 60)

        secim = input("Seçiminiz: ").strip().lower()
        if secim == "q":
            print("\nGörüşmek üzere! Sinop'a bekleriz.\n")
            break
        if not secim.isdigit():
            print(">> Lütfen bir numara girin veya 'q' yazın.")
            continue
        no = int(secim)
        if 1 <= no <= len(KATEGORILER):
            KATEGORILER[no - 1][1]()
        else:
            print(">> Geçersiz numara.")


if __name__ == "__main__":
    ana_menu()
