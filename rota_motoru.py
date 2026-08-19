# -*- coding: utf-8 -*-
"""
rota_motoru.py
--------------
"Akıllı Zaman ve Rota Düzenleyici" (Kart 3) için motor.

Akış:
  1) SQLite'taki (kuzeykapisi.db / mekanlar tablosu) tüm mekanlar okunur.
  2) Kullanıcının SERBEST METİN mesajı TEK bir LLM çağrısıyla dörde ayrıştırılır:
       - kaç saat vakti olduğu (belirtilmemişse varsayılan kullanılır)
       - genel TEMA tercihi (ör. "doğa", "müze") -> aday mekan id'leri
       - kullanıcı açıkça "X ile başlamak istiyorum" dediyse: zorunlu başlangıç
       - kullanıcı açıkça "X ile bitirmek istiyorum" dediyse: zorunlu bitiş
     ÖNEMLİ: Tek bir mekanı başlangıç/bitiş olarak ADLANDIRMAK, tema filtresi
     SAYILMAZ — bu durumda diğer tüm mekanlar yine aday kalır, aradaki süre
     onlarla doldurulur (eskiden buradaki ayrım yoktu, tek mekana daralıyordu).
  3) Zorunlu başlangıç varsa ilk durak o olur. Ardından kalan süre bütçesi
     içinde açgözlü (nearest-neighbor) ara duraklar eklenir — ama zorunlu bir
     bitiş varsa, her adımda "bu adaydan sonra bitiş noktasına gidip onu
     ziyaret etmeye hâlâ yetecek kadar süre kalıyor mu" kontrol edilir, yetmezse
     o aday atlanır. En sonda zorunlu bitiş, gerçek son konumdan hesaplanan
     yol süresiyle rotaya eklenir (kullanıcı açıkça istediği için, bütçeyi çok
     az aşsa bile eklenir; aşarsa özet metninde belirtilir).
  4) Her durağa bir Google Maps yol tarifi linki eklenir.

ÖNEMLİ VARSAYIMLAR (gerekirse değiştirin):
  - Rota TEK YÖNLÜDÜR; başlangıç noktasına dönüş süresi hesaba KATILMAZ.
  - `sure_dk` sütunu, o mekanda geçirilecek GEZİ süresidir.
  - Yol süreleri kuş uçuşu mesafe + ORTALAMA_HIZ_KMH varsayımından hesaplanır.
  - Mesajda süre belirtilmezse DEFAULT_SURE_SAAT kullanılır.
"""

import os
import json
import sqlite3
import math
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# --- Ayarlar (gerekirse değiştir) ---
KOK_DIZIN = Path(__file__).parent
DB_YOLU = KOK_DIZIN / "kuzey_kapisi.db"   # <-- gerçek dosya adın farklıysa burayı değiştir
ORTALAMA_HIZ_KMH = 32                     # kalibre edilebilir varsayım
SABIT_VARIS_EKI_DK = 5                    # park etme / yürüme payı
DEFAULT_SURE_SAAT = 4.0                   # mesajda süre yoksa kullanılır
SURE_MIN_SAAT = 0.5
SURE_MAX_SAAT = 14.0

LLM_MODEL = "openai/gpt-oss-120b"

_llm = None


def _llm_al():
    global _llm
    if _llm is None:
        from langchain_groq import ChatGroq
        _llm = ChatGroq(
            model=LLM_MODEL,
            api_key=os.environ.get("GROQ_API_KEY"),
            temperature=0.1,
        )
    return _llm


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


def _mesaji_coz(mekanlar, mesaj):
    """Kullanıcının serbest metnini TEK bir LLM çağrısıyla ayrıştırır:
    (süre, tema-filtrelenmiş adaylar, zorunlu başlangıç mekanı, zorunlu bitiş
    mekanı). Herhangi bir alan çıkarılamazsa güvenli varsayımlara düşer."""
    id_harita = {m["id"]: m for m in mekanlar}
    aday_liste = [
        {"id": m["id"], "ad": m["ad"], "tur": m["tur"], "aciklama": m["aciklama"][:200]}
        for m in mekanlar
    ]
    sistem = (
        "Sen bir gezi rota asistanısın. Kullanıcının serbest Türkçe mesajından "
        "DÖRT şeyi çıkaracaksın:\n"
        "1) sure_saat: kaç saat vakti olduğu (sayısal, ondalıklı olabilir). "
        "Mesajda YOKSA null.\n"
        "2) sabit_baslangic_id: kullanıcı açıkça 'X ile başlamak istiyorum', "
        "'önce X'e gitmek istiyorum' gibi BELİRLİ bir mekanı rotanın İLK "
        "durağı yapmak istediğini söylüyorsa o mekanın id'si, yoksa null.\n"
        "3) sabit_bitis_id: kullanıcı açıkça 'X ile bitirmek istiyorum', "
        "'son olarak X'e gitmek istiyorum' gibi BELİRLİ bir mekanı rotanın "
        "SON durağı yapmak istediğini söylüyorsa o mekanın id'si, yoksa null.\n"
        "4) secilen_idler: kullanıcının GENEL TERCİHİNE (tema/kategori, ör. "
        "'doğa', 'müze', 'tarihi yerler') uyan mekanların id'leri. ÇOK ÖNEMLİ: "
        "Kullanıcı sadece belirli bir mekanı başlangıç/bitiş olarak ADLANDIRDIYSA "
        "(madde 2 veya 3), bu TEK BAŞINA bir tema tercihi SAYILMAZ — bu durumda "
        "secilen_idler'e TÜM id'leri döndür (rotanın geri kalanını doldurmak "
        "için çeşitli mekanlar gerekir). SADECE kullanıcı gerçekten bir TEMA/ "
        "KATEGORİ belirtmişse (ör. 'doğa gezmek istiyorum') secilen_idler'i o "
        "temaya göre filtrele. Belirsizse yine TÜM id'leri döndür.\n"
        "SADECE şu formatta geçerli JSON döndür, başka hiçbir açıklama/metin "
        'yazma: {"sure_saat": 6, "sabit_baslangic_id": null, '
        '"sabit_bitis_id": 12, "secilen_idler": [1,2,3]}'
    )
    kullanici = (
        f'Kullanıcının mesajı: "{mesaj.strip()}"\n\n'
        f"Mekan listesi (JSON):\n{json.dumps(aday_liste, ensure_ascii=False)}"
    )

    sure_saat = None
    sure_belirtilmedi = True
    adaylar = mekanlar
    kategoriler = []
    baslangic_id = None
    bitis_id = None

    try:
        yanit = _llm_al().invoke([("system", sistem), ("human", kullanici)])
        metin = yanit.content.strip().replace("```json", "").replace("```", "").strip()
        veri = json.loads(metin)

        ham_sure = veri.get("sure_saat")
        if isinstance(ham_sure, (int, float)) and ham_sure > 0:
            sure_saat = max(SURE_MIN_SAAT, min(SURE_MAX_SAAT, float(ham_sure)))
            sure_belirtilmedi = False

        ham_baslangic = veri.get("sabit_baslangic_id")
        if isinstance(ham_baslangic, (int, float)) and int(ham_baslangic) in id_harita:
            baslangic_id = int(ham_baslangic)

        ham_bitis = veri.get("sabit_bitis_id")
        if isinstance(ham_bitis, (int, float)) and int(ham_bitis) in id_harita:
            bitis_id = int(ham_bitis)

        if baslangic_id is not None and baslangic_id == bitis_id:
            bitis_id = None  # çelişki: aynı mekan hem başlangıç hem bitiş olamaz

        secilen_idler = set(veri.get("secilen_idler") or [])
        if secilen_idler:
            filtrelenmis = [m for m in mekanlar if m["id"] in secilen_idler]
            if filtrelenmis:
                adaylar = filtrelenmis
                kategoriler = sorted({m["tur"] for m in filtrelenmis})
    except Exception:
        pass  # LLM/parse hatasında güvenli varsayımlarla devam ederiz

    if sure_saat is None:
        sure_saat = DEFAULT_SURE_SAAT

    return sure_saat, sure_belirtilmedi, adaylar, kategoriler, baslangic_id, bitis_id


def rota_olustur(enlem, boylam, mesaj):
    tum_mekanlar = _mekanlari_getir()

    if not tum_mekanlar:
        return {
            "toplam_sure_dk": 0,
            "kullanilan_sure_dk": 0,
            "tercih_kategorisi": [],
            "rota": [],
            "ozet": "Veritabanında henüz mekan bulunamadı.",
        }

    id_harita = {m["id"]: m for m in tum_mekanlar}
    sure_saat, sure_belirtilmedi, adaylar, kategoriler, baslangic_id, bitis_id = (
        _mesaji_coz(tum_mekanlar, mesaj)
    )
    adaylar = list(adaylar)

    baslangic_mekan = id_harita.get(baslangic_id) if baslangic_id is not None else None
    bitis_mekan = id_harita.get(bitis_id) if bitis_id is not None else None

    # Zorunlu mekanlar, açgözlü seçim havuzunda ikinci kez seçilmesin
    if baslangic_mekan:
        adaylar = [m for m in adaylar if m["id"] != baslangic_mekan["id"]]
    if bitis_mekan:
        adaylar = [m for m in adaylar if m["id"] != bitis_mekan["id"]]

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
            "tur": mekan["tur"],
            "aciklama": mekan["aciklama"],
            "enlem": mekan["enlem"],
            "boylam": mekan["boylam"],
            "onceki_noktadan_yol_dk": yol_dk,
            "ziyaret_suresi_dk": mekan["sure_dk"],
            "varis_toplam_dk": kullanilan_dk,
            "google_maps_url": _google_maps_url(mekan["enlem"], mekan["boylam"]),
        })
        sira += 1
        su_anki_lat, su_anki_lon = mekan["enlem"], mekan["boylam"]
        return gerekli

    # 1) Zorunlu başlangıç — kullanıcı açıkça istedi, koşulsuz eklenir
    if baslangic_mekan:
        yol = _yol_dk(su_anki_lat, su_anki_lon, baslangic_mekan["enlem"], baslangic_mekan["boylam"])
        gerekli = durak_ekle(baslangic_mekan, yol)
        kalan_dk -= gerekli

    # 2) Ara duraklar — açgözlü en-yakın, ama zorunlu bitiş için hep yer ayır
    while adaylar and kalan_dk > 0:
        en_yakin = min(
            adaylar,
            key=lambda m: _yol_dk(su_anki_lat, su_anki_lon, m["enlem"], m["boylam"]),
        )
        yol = _yol_dk(su_anki_lat, su_anki_lon, en_yakin["enlem"], en_yakin["boylam"])
        gerekli = yol + en_yakin["sure_dk"]

        if bitis_mekan:
            bitise_yol = _yol_dk(
                en_yakin["enlem"], en_yakin["boylam"],
                bitis_mekan["enlem"], bitis_mekan["boylam"],
            )
            bitis_gerekli = bitise_yol + bitis_mekan["sure_dk"]
        else:
            bitis_gerekli = 0

        if gerekli + bitis_gerekli <= kalan_dk:
            kalan_dk -= durak_ekle(en_yakin, yol)
            adaylar.remove(en_yakin)
        else:
            adaylar.remove(en_yakin)  # sığmıyor; bir sonraki en yakına bak

    # 3) Zorunlu bitiş — kullanıcı açıkça istedi, bütçeyi az aşsa bile eklenir
    asildi_mi = False
    if bitis_mekan:
        yol = _yol_dk(su_anki_lat, su_anki_lon, bitis_mekan["enlem"], bitis_mekan["boylam"])
        gerekli = yol + bitis_mekan["sure_dk"]
        if gerekli > kalan_dk:
            asildi_mi = True
        kalan_dk -= durak_ekle(bitis_mekan, yol)

    sure_notu = (
        f" (süre belirtmediğiniz için varsayılan {DEFAULT_SURE_SAAT:g} saat kullanıldı)"
        if sure_belirtilmedi else ""
    )
    asim_notu = " Belirttiğiniz bitiş durağını dahil edebilmek için süre biraz aşıldı." if asildi_mi else ""

    if rota:
        saat = kullanilan_dk // 60
        dk = kullanilan_dk % 60
        ozet = (
            f"Elinizdeki {sure_saat:g} saatlik vakit{sure_notu} için {len(rota)} "
            f"duraklı bir rota hazırladık; tahmini toplam süre {saat} saat {dk} "
            f"dakika (yol + ziyaret dahil).{asim_notu}"
        )
    else:
        ozet = (
            f"Verilen süre{sure_notu} içine (yol süresi dahil) sığan bir durak "
            "bulunamadı. Süreyi artırmayı deneyin."
        )

    return {
        "toplam_sure_dk": round(sure_saat * 60),
        "kullanilan_sure_dk": kullanilan_dk,
        "tercih_kategorisi": kategoriler,
        "rota": rota,
        "ozet": ozet,
    }