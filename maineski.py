# -*- 1
# 1coding: utf-8 -*-
"""
main.py
--------
Sinop Akıllı Turizm Platformu - Terminal Prototipi (Aşama 1)

Hiyerarşi:
  Seviye 1: 4 Kategori menüsü
  Seviye 2: Kategori içindeki seçenekler (kişi/mekan/lezzet/doğa)
  Seviye 3: Seçilen karakterle sohbet (while True)

Navigasyon:
  - Seviye 3'te 'q' -> Seviye 2'ye (kategori seçenek listesine) döner
  - Seviye 2'de 'q' -> Seviye 1'e (4 kategori menüsüne) döner
  - Seviye 1'de 'q' -> Programdan çıkar

Not: Hafıza, API (FastAPI), web arama entegrasyonu vb. sonraki aşamalarda.
"""

from bot_engine import karakterle_sohbet


# ==================================================================
#  MENÜ VERİSİ
#  Her kategori için seçenek listesi:
#   (Görünen ad, persona_adi, alt_klasor, dosya_adi, karşılama)
#  Yeni bir seçenek eklemek için sadece buraya satır eklemen yeter.
# ==================================================================

TARIHI_KISILER = [
    ("Sinoplu Diyojen", "filozof_diyojen", "kisiler", "diyojen",
     "Ne istiyorsun? Ama önce, gölge etme, başka ihsan istemem."),
    ("Katip Kadir (1919)", "katip_kadir", "kisiler", "katip_kadir",
     "Hoş geldiniz efendim. 1919 Sinop'undan size naklen anlatayım."),
    ("Sabahattin Ali", "sahsiyet_rehberi", "kisiler", "sabahattin_ali",
     "Merhaba. Sinop'un o kalın duvarları ardından size sesleniyorum."),
    ("VI. Mithridates", "sahsiyet_rehberi", "kisiler", "mithridates",
     "Ben Pontus'un kralıyım, Sinop benim başkentimdi."),
    ("I. Alaaddin Keykubat", "sahsiyet_rehberi", "kisiler", "alaaddin_keykubat",
     "Selam olsun. Sinop'u Selçuklu'ya ben kazandırdım."),
    ("Kötürüm Bayezid", "sahsiyet_rehberi", "kisiler", "koturum_bayezid",
     "Ben Candaroğulları'ndan bir beyim, Sinop'ta hüküm sürdüm."),
    # ... prompts/kaynakca'da olan diğer kişiler de buraya eklenebilir
]

TARIHI_MEKANLAR = [
    ("Tarihi Sinop Cezaevi", "mekan_rehberi", "mekanlar", "sinop_cezaevi",
     "Anadolu'nun Alkatraz'ına hoş geldiniz. Neyi merak edersiniz?"),
    ("Alaaddin Camii", "mekan_rehberi", "mekanlar", "alaaddin_camii",
     "Sinop Ulu Camii'ni size anlatayım."),
    ("Sinop Kalesi", "mekan_rehberi", "mekanlar", "sinop_kalesi",
     "Şehri saran surların hikayesini dinlemek ister misiniz?"),
    ("Pervane Medresesi", "mekan_rehberi", "mekanlar", "pervane_medresesi",
     "1262'den kalma bu Selçuklu eserini tanıtayım."),
    ("Balatlar Kilisesi", "mekan_rehberi", "mekanlar", "balatlar_kilisesi",
     "Roma'dan Bizans'a uzanan katmanlı bir yapıdayız."),
    # ...
]

LEZZETLER = [
    ("Sinop Mantısı", "asci", "lezzetler", "sinop_mantisi",
     "Gel bakalım evladım, sana Sinop mantısının sırrını anlatayım."),
    ("Nokul", "asci", "lezzetler", "nokul",
     "Nokulun kokusu daha fırından yayılmadan anlatmaya başlayayım."),
    ("Sırık Kebabı", "asci", "lezzetler", "sirik_kebabi",
     "Boyabat'ın sırık kebabı başka olur evladım, dinle."),
    ("Sinop Keşkeği", "asci", "lezzetler", "sinop_keskegi",
     "Düğünlerin baş tacı keşkeği kazanda beraber dövelim."),
    ("Zılbıt Böreği", "asci", "lezzetler", "zilbit_boregi",
     "Ormanın otundan börek olur mu dersin? Otur anlatayım."),
    # ...
]

DOGA = [
    ("Hamsilos Fiyordu", "doga_rehberi", "doga", "hamsilos_fiyordu",
     "Türkiye'nin en özel koyuna hoş geldiniz. Rehberiniz olayım."),
    ("Erfelek Şelaleleri", "doga_rehberi", "doga", "erfelek_selaleleri",
     "28 şelalenin peşine düşmeye hazır mısınız?"),
    ("İnceburun Tabiat Parkı", "doga_rehberi", "doga", "inceburun_tabiat_parki",
     "Türkiye'nin en kuzey ucundayız."),
    ("Sarıkum Koruma Alanı", "doga_rehberi", "doga", "sarikum_koruma_alani",
     "Dört ekosistemin buluştuğu yere hoş geldiniz."),
    ("Boztepe Yarımadası", "doga_rehberi", "doga", "boztepe_yarimadasi",
     "İki limana birden bakan tepedeyiz."),
    # ...
]


# ==================================================================
#  YARDIMCI: seçenek listesi menüsü göster ve seçim al
# ==================================================================
def secenek_menusu_goster(baslik, secenekler):
    """
    Bir kategorinin seçeneklerini listeler, kullanıcıdan seçim alır.
    Dönüş:
      - seçilen öğe tuple'ı (sohbete gidilecek), veya
      - None ('q' -> üst menüye dön)
    """
    while True:
        print("\n" + "-" * 60)
        print(f"  {baslik}")
        print("-" * 60)
        for i, sec in enumerate(secenekler, start=1):
            print(f"  {i}) {sec[0]}")
        print("  q) Üst menüye dön")
        print("-" * 60)

        secim = input("Seçiminiz: ").strip().lower()

        if secim == "q":
            return None
        if not secim.isdigit():
            print(">> Lütfen bir numara girin veya 'q' yazın.")
            continue

        no = int(secim)
        if 1 <= no <= len(secenekler):
            return secenekler[no - 1]
        print(">> Geçersiz numara.")


# ==================================================================
#  4 KATEGORİ FONKSİYONU
#  Her biri: seçenekleri göster -> seçilenle sohbet et -> 'q' ile geri
# ==================================================================

def kategori_tarihi_kisiler():
    kategori = "kisiler"
    while True:
        secim = secenek_menusu_goster("TARİHİ KİŞİLER", TARIHI_KISILER)
        if secim is None:
            return  # ana menüye dön
        ad, persona, klasor, dosya, karsilama = secim
        karakterle_sohbet(ad, kategori, persona, klasor, dosya, karsilama)
        # sohbette 'q' -> buraya döner, tekrar kişi listesi gösterilir


def kategori_tarihi_mekanlar():
    kategori = "mekanlar"
    while True:
        secim = secenek_menusu_goster("TARİHİ MEKANLAR", TARIHI_MEKANLAR)
        if secim is None:
            return
        ad, persona, klasor, dosya, karsilama = secim
        karakterle_sohbet(ad, kategori, persona, klasor, dosya, karsilama)


def kategori_lezzetler():
    kategori = "lezzetler"
    while True:
        secim = secenek_menusu_goster("YÖRESEL LEZZETLER", LEZZETLER)
        if secim is None:
            return
        ad, persona, klasor, dosya, karsilama = secim
        karakterle_sohbet(ad, kategori, persona, klasor, dosya, karsilama)


def kategori_doga():
    kategori = "doga"
    while True:
        secim = secenek_menusu_goster("DOĞAL GÜZELLİKLER", DOGA)
        if secim is None:
            return
        ad, persona, klasor, dosya, karsilama = secim
        karakterle_sohbet(ad, kategori, persona, klasor, dosya, karsilama)


# ==================================================================
#  ANA MENÜ (Seviye 1)
# ==================================================================
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
            _, fonksiyon = KATEGORILER[no - 1]
            fonksiyon()  # kategori fonksiyonuna gir; 'q' ile buraya döner
        else:
            print(">> Geçersiz numara.")


if __name__ == "__main__":
    ana_menu()
