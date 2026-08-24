# -*- coding: utf-8 -*-
"""
rota_motoru.py
--------------
"Akıllı Zaman ve Rota Düzenleyici" (Kart 3) için motor.

TASARIM:
  - mekanlar tablosunda artık bir 'tur' sütunu YOK. Kategori, her mekan için
    BİR KEZ, yalnızca 'ad' + 'aciklama' okunarak yapay zeka ile belirlenir ve
    BELLEKTE ÖNBELLEKLENİR (_KATEGORI_ONBELLEK). Aynı mekan için tekrar tekrar
    LLM çağrısı YAPILMAZ — yalnızca daha önce hiç sınıflandırılmamış (ör. yeni
    eklenmiş) mekanlar için, TEK bir toplu çağrıyla sınıflandırma yapılır.
  - Kullanıcı süreyi bir sayı (3-15 saat) olarak, ilgi alanlarını sabit bir
    kategori listesinden (0 ya da daha fazla seçim) verir.
  - `/rota/varsayilanlar`: 6/7/8/9 saatlik, kategori filtresiz 4 hazır rota.
  - `/rota/olustur`: seçilen süre + kategori(ler)e göre TEK bir özel rota.

Rota kurulumu (ikisinde de aynı): kullanıcının konumundan başlayarak açgözlü
(nearest-neighbor) mantıkla, süre bütçesi bitene ya da aday kalmayana kadar
en yakın uygun mekan eklenir.

ÖNEMLİ VARSAYIMLAR (gerekirse değiştirin):
  - Rota TEK YÖNLÜDÜR; başlangıç noktasına dönüş süresi hesaba KATILMAZ.
  - `sure_dk` sütunu, o mekanda geçirilecek GEZİ süresidir.
  - Yol süreleri kuş uçuşu mesafe + ORTALAMA_HIZ_KMH varsayımından hesaplanır.
  - Beklenen tablo şeması artık:
      CREATE TABLE mekanlar (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ad TEXT NOT NULL,
          enlem REAL NOT NULL,
          boylam REAL NOT NULL,
          sure_dk INTEGER NOT NULL,
          aciklama TEXT NOT NULL
      )
  - Kategori önbelleği yalnızca BELLEKTEDİR; sunucu yeniden başlarsa (sohbet
    session'larıyla aynı desen) tüm mekanlar ilk istekte bir kez daha
    sınıflandırılır — küçük, kabul edilebilir bir ek maliyet.
"""

import os
import json
import sqlite3
import math
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

KOK_DIZIN = Path(__file__).parent
DB_YOLU = KOK_DIZIN / "kuzey_kapisi.db"   # <-- gerçek dosya adın farklıysa burayı değiştir
ROTA_ANLATIM_DIZIN = KOK_DIZIN / "rota_anlatim"  # {mekan_id}.md dosyaları burada
ORTALAMA_HIZ_KMH = 45                      # kalibre edilebilir varsayım
SABIT_VARIS_EKI_DK = 15                    # park etme / yürüme payı

SURE_MIN_SAAT = 3
SURE_MAX_SAAT = 15
VARSAYILAN_TUR_SAATLERI = [6, 7, 8, 9]

# --- Sabit kategori kodları (tek gerçek kaynak — KMP tarafı /rota/kategoriler
#     endpoint'inden çeker, elle kopyalamaz) ---
GECERLI_TURLER = {
    "muze": "Müze",
    "cami_medrese_turbe": "Cami / Medrese / Türbe",
    "kulturel_mekan": "Kültürel Mekanlar",
    "doga_manzara": "Doğal Güzellikler / Manzara",
    "aktivite": "Aktivite Yerleri (Yeme-İçme, Çay Bahçesi vb.)",
    "sahil": "Sahiller",
}
_VARSAYILAN_KATEGORI = "kulturel_mekan"  # LLM sınıflandıramazsa güvenli düşüş
MAKS_TUR_SECIMI = 4  # kullanıcı en fazla bu kadar kategori seçebilir

# Her kategorinin kısa açıklaması — KMP tarafında chip'in altında/tooltip'inde
# gösterilir ki kullanıcı seçmeden önce ne olduğunu anlasın.
TUR_ACIKLAMALARI = {
    "muze": "Arkeoloji, etnografya ve tarih müzeleri.",
    "cami_medrese_turbe": "Tarihi camiler, medreseler ve türbeler.",
    "kulturel_mekan": "Kaleler, konaklar, kiliseler gibi diğer tarihi/kültürel yapılar.",
    "doga_manzara": "Şelaleler, ormanlar, tepe ve manzara noktaları.",
    "aktivite": "Kafe, çay bahçesi, yeme-içme ve dinlenme mekanları.",
    "sahil": "Plajlar ve sahil şeritleri.",
}


def kategori_bilgileri():
    """/rota/kategoriler endpoint'i için: kod -> {ad, aciklama}. KMP tarafı
    checkbox listesini ve açıklama metnini buradan çeker, elle kopyalamaz."""
    return {
        kod: {"ad": ad, "aciklama": TUR_ACIKLAMALARI.get(kod, "")}
        for kod, ad in GECERLI_TURLER.items()
    }

# Özet metninde doğal bir cümle kurmak için
_KATEGORI_GEZI_IFADESI = {
    "muze": "müzeleri",
    "cami_medrese_turbe": "cami, medrese ve türbeleri",
    "kulturel_mekan": "kültürel mekanları",
    "doga_manzara": "doğal güzellikleri ve manzara noktalarını",
    "aktivite": "yeme-içme ve dinlenme noktalarını",
    "sahil": "sahilleri",
}

# --- LLM sağlayıcı (bot_engine.py'deki llm_getir() ile AYNI mantık) ---
SAGLAYICI = os.getenv("SAGLAYICI", "groq")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
SICAKLIK = 0.1   # sınıflandırma JSON döndürdüğü için düşük tutulur

_llm = None


def _llm_al():
    """SAGLAYICI ayarına göre uygun LLM örneğini döndürür (bot_engine.py'deki
    llm_getir() ile birebir aynı mantık); tembel ve tek seferlik oluşturulur."""
    global _llm
    if _llm is not None:
        return _llm

    if SAGLAYICI == "groq":
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError(
                "GROQ_API_KEY tanımlı değil. .env dosyanıza ekleyin veya "
                "terminalde tanımlayın."
            )
        from langchain_groq import ChatGroq
        _llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.environ.get("GROQ_API_KEY"),
            temperature=SICAKLIK,
        )

    elif SAGLAYICI == "gemini":
        if not os.environ.get("GOOGLE_API_KEY"):
            raise RuntimeError(
                "GOOGLE_API_KEY tanımlı değil. .env dosyanıza ekleyin veya "
                "terminalde tanımlayın."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI
        _llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            temperature=SICAKLIK,
        )

    else:
        raise ValueError(
            f"Bilinmeyen SAGLAYICI: {SAGLAYICI!r} "
            "(yalnızca 'groq' veya 'gemini' olabilir)."
        )

    return _llm


def _icerik_metni(icerik):
    """LLM yanıtının .content alanı sağlayıcıya göre değişir: Groq'ta düz
    string, Gemini'de bazen parça listesi olabilir. İkisini de düz metne çevirir."""
    if isinstance(icerik, str):
        return icerik
    if isinstance(icerik, list):
        parcalar = []
        for p in icerik:
            if isinstance(p, str):
                parcalar.append(p)
            elif isinstance(p, dict) and "text" in p:
                parcalar.append(p["text"])
        return "".join(parcalar)
    return str(icerik)


def _dogal_liste(ogeler):
    """['a', 'b', 'c'] -> 'a, b ve c' (Türkçe doğal sıralama)."""
    ogeler = list(ogeler)
    if not ogeler:
        return ""
    if len(ogeler) == 1:
        return ogeler[0]
    return ", ".join(ogeler[:-1]) + " ve " + ogeler[-1]


def _mekanlari_getir():
    con = sqlite3.connect(DB_YOLU)
    con.row_factory = sqlite3.Row
    try:
        satirlar = con.execute("SELECT * FROM mekanlar").fetchall()
        return [dict(s) for s in satirlar]
    finally:
        con.close()


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _yol_dk(lat1, lon1, lat2, lon2):
    km = _haversine_km(lat1, lon1, lat2, lon2)
    return round((km / ORTALAMA_HIZ_KMH) * 60) + SABIT_VARIS_EKI_DK


def _google_maps_url(enlem, boylam):
    return f"https://www.google.com/maps/dir/?api=1&destination={enlem},{boylam}"


# --- Kategori sınıflandırma (LLM, önbellekli) ---

_KATEGORI_ONBELLEK: dict[int, str] = {}


def _eksik_kategorileri_tamamla(mekanlar):
    """_KATEGORI_ONBELLEK'te olmayan mekanların kategorisini TEK bir LLM
    çağrısıyla toplu belirler. Zaten sınıflandırılmış mekanlar için hiçbir
    şey yapmaz (tekrar LLM çağrısı yok)."""
    eksikler = [m for m in mekanlar if m["id"] not in _KATEGORI_ONBELLEK]
    if not eksikler:
        return

    aday_liste = [
        {"id": m["id"], "ad": m["ad"], "aciklama": m["aciklama"][:300]}
        for m in eksikler
    ]
    kategori_aciklamasi = "\n".join(f"- {kod}: {ad}" for kod, ad in GECERLI_TURLER.items())
    sistem = (
        "Sen bir gezi rehberisin. Verilen her mekanı, 'ad' ve 'aciklama' "
        "alanlarına bakarak AŞAĞIDAKİ 6 kategoriden TAM OLARAK BİRİNE ata:\n"
        f"{kategori_aciklamasi}\n"
        "Her mekan için en uygun TEK kategoriyi seç. "
        "SADECE şu formatta geçerli JSON döndür, başka hiçbir açıklama/metin "
        'yazma: {"atamalar": [{"id": 1, "tur": "muze"}, {"id": 2, "tur": "sahil"}]}'
    )
    kullanici = f"Mekanlar (JSON):\n{json.dumps(aday_liste, ensure_ascii=False)}"

    try:
        yanit = _llm_al().invoke([("system", sistem), ("human", kullanici)])
        metin = _icerik_metni(yanit.content).strip().replace("```json", "").replace("```", "").strip()
        veri = json.loads(metin)
        for atama in veri.get("atamalar", []):
            mid = atama.get("id")
            tur = atama.get("tur")
            if isinstance(mid, (int, float)) and tur in GECERLI_TURLER:
                _KATEGORI_ONBELLEK[int(mid)] = tur
    except Exception as e:
        print(f"[rota_motoru] Kategori sınıflandırma başarısız, varsayılana düşülüyor: {e!r}")

    # LLM bir mekanı atlamışsa/başarısız olduysa güvenli varsayımla doldur
    for m in eksikler:
        if m["id"] not in _KATEGORI_ONBELLEK:
            _KATEGORI_ONBELLEK[m["id"]] = _VARSAYILAN_KATEGORI


def _kategorisi(mekan):
    return _KATEGORI_ONBELLEK.get(mekan["id"], _VARSAYILAN_KATEGORI)


def rota_olustur(enlem, boylam, sure_saat, turler=None):
    """
    sure_saat: 3-15 arası bir sayı (saat).
    turler: GECERLI_TURLER kodlarından bir liste; boş/None ise TÜM kategoriler
            aday olur.
    """
    turler = list(turler or [])
    gecersiz = [t for t in turler if t not in GECERLI_TURLER]
    if gecersiz:
        raise ValueError(
            f"Geçersiz tür(ler): {gecersiz}. Geçerli değerler: {list(GECERLI_TURLER)}"
        )
    if len(turler) > MAKS_TUR_SECIMI:
        raise ValueError(f"En fazla {MAKS_TUR_SECIMI} kategori seçebilirsiniz.")
    if not (SURE_MIN_SAAT <= sure_saat <= SURE_MAX_SAAT):
        raise ValueError(f"sure_saat {SURE_MIN_SAAT}-{SURE_MAX_SAAT} arasında olmalı.")

    tum_mekanlar = _mekanlari_getir()
    if not tum_mekanlar:
        return {
            "sure_saat": sure_saat,
            "toplam_sure_dk": round(sure_saat * 60),
            "kullanilan_sure_dk": 0,
            "tercih_kategorisi": [],
            "rota": [],
            "ozet": "Veritabanında henüz mekan bulunamadı.",
        }

    _eksik_kategorileri_tamamla(tum_mekanlar)

    adaylar = (
        [m for m in tum_mekanlar if _kategorisi(m) in turler]
        if turler else list(tum_mekanlar)
    )

    kalan_dk = round(sure_saat * 60)
    su_anki_lat, su_anki_lon = enlem, boylam
    rota = []
    kullanilan_dk = 0
    sira = 1

    def durak_ekle(mekan, yol_dk):
        nonlocal kullanilan_dk, sira, su_anki_lat, su_anki_lon
        gerekli = yol_dk + mekan["sure_dk"]
        kullanilan_dk += gerekli
        rota.append({
            "sira": sira,
            "id": mekan["id"],
            "ad": mekan["ad"],
            "tur": _kategorisi(mekan),
            "aciklama": mekan["aciklama"],
            "enlem": mekan["enlem"],
            "boylam": mekan["boylam"],
            "onceki_noktadan_yol_dk": yol_dk,
            "ziyaret_suresi_dk": mekan["sure_dk"],
            "varis_toplam_dk": kullanilan_dk,
            "google_maps_url": _google_maps_url(mekan["enlem"], mekan["boylam"]),
            "anlatim_var": (ROTA_ANLATIM_DIZIN / f"{mekan['id']}.md").is_file(),
        })
        sira += 1
        su_anki_lat, su_anki_lon = mekan["enlem"], mekan["boylam"]
        return gerekli

    while adaylar and kalan_dk > 0:
        en_yakin = min(
            adaylar,
            key=lambda m: _yol_dk(su_anki_lat, su_anki_lon, m["enlem"], m["boylam"]),
        )
        yol = _yol_dk(su_anki_lat, su_anki_lon, en_yakin["enlem"], en_yakin["boylam"])
        gerekli = yol + en_yakin["sure_dk"]
        if gerekli <= kalan_dk:
            kalan_dk -= durak_ekle(en_yakin, yol)
        adaylar.remove(en_yakin)

    gercek_turler = sorted({d["tur"] for d in rota})

    if rota:
        saat = kullanilan_dk // 60
        dk = kullanilan_dk % 60
        ifadeler = [_KATEGORI_GEZI_IFADESI.get(t, t) for t in gercek_turler]
        if ifadeler:
            konu = _dogal_liste(ifadeler)
            ozet = (
                f"Bu {sure_saat:g} saatlik rotada {konu} gezeceksiniz; toplam "
                f"süre (yol + ziyaret dahil) yaklaşık {saat} saat {dk} dakika sürecek."
            )
        else:
            ozet = (
                f"Bu {sure_saat:g} saatlik rotada karma bir gezi programı "
                f"hazırladık; toplam süre (yol + ziyaret dahil) yaklaşık "
                f"{saat} saat {dk} dakika sürecek."
            )
    else:
        if turler:
            secililer = _dogal_liste([GECERLI_TURLER[t] for t in turler])
            ozet = (
                f"Seçtiğiniz kategoride ({secililer}) bu süreye sığan bir yer "
                "bulunamadı. Süreyi artırmayı ya da farklı bir kategori "
                "seçmeyi deneyin."
            )
        else:
            ozet = "Bu süreye sığan bir durak bulunamadı. Süreyi artırmayı deneyin."

    return {
        "sure_saat": sure_saat,
        "toplam_sure_dk": round(sure_saat * 60),
        "kullanilan_sure_dk": kullanilan_dk,
        "tercih_kategorisi": gercek_turler,
        "rota": rota,
        "ozet": ozet,
    }


def varsayilan_rotalar_olustur(enlem, boylam):
    """6/7/8/9 saatlik, kategori filtresiz 4 hazır rota döner (uygulama
    açılışında kart olarak gösterilecek "öneri" listesi)."""
    return [rota_olustur(enlem, boylam, saat, turler=[]) for saat in VARSAYILAN_TUR_SAATLERI]