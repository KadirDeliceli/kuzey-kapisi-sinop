# -*- coding: utf-8 -*-
"""
rota_motoru.py
--------------
"Akıllı Zaman ve Rota Düzenleyici" (Kart 3) için motor.

Akış:
  1) SQLite'taki (kuzeykapisi.db / mekanlar tablosu) tüm mekanlar okunur.
  2) Kullanıcının SERBEST METİN mesajı TEK bir LLM çağrısıyla ayrıştırılır:
       - kaç saat vakti olduğu (belirtilmemişse varsayılan kullanılır)
       - zorunlu başlangıç mekanı (kullanıcı "X ile başlamak istiyorum" dediyse)
       - zorunlu bitiş mekanı (kullanıcı "X ile bitirmek istiyorum" dediyse)
       - İSTENİLEN mekan(lar) (kullanıcı isim vererek "X'e/Y'ye gitmek/görmek
         istiyorum" dediyse — sırası önemli değil, sadece dahil edilmesi
         istenir; tek ya da birden çok olabilir)
       - genel TEMA tercihi (ör. "doğa", "müze") -> aday mekan id'leri
     ÖNEMLİ: Belirli mekan(lar)ı İSİM VEREREK istemek, tema filtresi SAYILMAZ
     — bu durumda diğer tüm mekanlar yine aday kalır, aradaki süre onlarla
     doldurulur.
  3) Rota kurulumu:
       a) Zorunlu başlangıç varsa ilk durak o olur (koşulsuz eklenir).
       b) İSTENİLEN mekanlar, süre bütçesi içinde en-yakın mantığıyla
          ÖNCELİKLİ olarak yerleştirilir (genel havuzdan ÖNCE denenir) —
          böylece kullanıcının isim verdiği yerler, "daha yakın" genel
          adaylar yüzünden dışarıda kalmaz.
       c) Kalan süre, genel tema havuzuyla (secilen_idler) yine en-yakın
          mantığıyla doldurulur.
       d) Zorunlu bitiş varsa, gerçek son konumdan hesaplanan yol süresiyle
          en sona eklenir (kullanıcı açıkça istediği için bütçeyi az aşsa
          bile eklenir).
       Adım (b) ve (c)'de her zaman, zorunlu bitiş için yeterli süre kalıp
       kalmadığı kontrol edilir.
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

# bot_engine.py'deki llm_getir() ile AYNI SAGLAYICI mantığı
SAGLAYICI = os.getenv("SAGLAYICI", "groq")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
SICAKLIK = 0.1   # rota ayrıştırma JSON döndürdüğü için düşük tutulur

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


def _icerik_metni(icerik):
    """LLM yanıtının .content alanı sağlayıcıya göre değişir: Groq'ta düz
    string, Gemini'de bazen parça listesi ([{"type": "text", "text": "…"}]
    gibi) olabilir (api.py'deki /sohbet endpoint'inde de aynı durum ele
    alınır). İkisini de düz metne çevirir."""
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


def _mesaji_coz(mekanlar, mesaj):
    """Kullanıcının serbest metnini TEK bir LLM çağrısıyla ayrıştırır:
    (süre, zorunlu başlangıç, zorunlu bitiş, istenilen mekan(lar), tema
    filtresi). Herhangi bir alan çıkarılamazsa güvenli varsayımlara düşer."""
    id_harita = {m["id"]: m for m in mekanlar}
    aday_liste = [
        {"id": m["id"], "ad": m["ad"], "tur": m["tur"], "aciklama": m["aciklama"][:200]}
        for m in mekanlar
    ]
    sistem = (
        "Sen bir gezi rota asistanısın. Kullanıcının serbest Türkçe mesajından "
        "ALTI şeyi çıkaracaksın:\n"
        "1) sure_saat: kaç saat vakti olduğu (sayısal, ondalıklı olabilir). "
        "Mesajda YOKSA null.\n"
        "2) sabit_baslangic_id: kullanıcı açıkça 'X ile başlamak istiyorum', "
        "'önce X'e gitmek istiyorum' gibi BELİRLİ bir mekanı rotanın İLK "
        "durağı yapmak istediğini söylüyorsa o mekanın id'si, yoksa null.\n"
        "3) sabit_bitis_id: kullanıcı açıkça 'X ile bitirmek istiyorum', "
        "'son olarak X'e gitmek istiyorum' gibi BELİRLİ bir mekanı rotanın "
        "SON durağı yapmak istediğini söylüyorsa o mekanın id'si, yoksa null.\n"
        "4) istenilen_idler: kullanıcının mesajda AÇIKÇA İSİM VEREREK görmek/ "
        "gitmek istediğini belirttiği mekan(lar)ın id listesi. TEK bir yer de "
        "olabilir, BİRDEN FAZLA yer de olabilir. Bu mekanların rotadaki SIRASI "
        "önemli değildir (başlangıç/bitiş olmaları GEREKMEZ, sadece rotaya "
        "dahil edilmeleri istenir). Örnek: 'Aklıman'a gitmek istiyorum' -> "
        "Aklıman'ın id'si burada. Bir mekan zaten sabit_baslangic_id veya "
        "sabit_bitis_id olarak seçildiyse, onu TEKRAR buraya ekleme.\n"
        "5) haric_idler: kullanıcının OLUMSUZ belirttiği, GEZMEK İSTEMEDİĞİ "
        "mekan(lar)ın id listesi. 'X gezmek istemiyorum', 'X'e gitmek "
        "istemem', 'X hariç', 'X olmasın' gibi ifadeleri yakala. Bu, hem "
        "belirli bir mekan ismi (ör. 'Sinop Kalesi istemiyorum') hem de bir "
        "TÜR/TEMA (ör. 'türbe ve cami gezmek istemiyorum' -> bu türden/isimden "
        "TÜM mekanların id'leri) için geçerlidir; mekanın 'ad', 'tur' ve "
        "'aciklama' alanlarına bakarak eşleşen TÜM id'leri buraya koy. Bu "
        "mekanlar rotada KESİNLİKLE görünmemeli, başka hiçbir kural (madde 2, "
        "3, 4, 6) bunu geçersiz kılamaz.\n"
        "6) secilen_idler: kullanıcının GENEL POZİTİF TERCİHİNE (tema/kategori, "
        "ör. 'doğa', 'müze', 'tarihi yerler') uyan mekanların id'leri. ÇOK "
        "ÖNEMLİ: Kullanıcı sadece belirli mekan(lar)ı İSİM VEREREK istediyse "
        "(madde 2, 3 veya 4) ya da sadece hariç tutma belirttiyse (madde 5), "
        "bu TEK BAŞINA bir pozitif tema tercihi SAYILMAZ — bu durumda "
        "secilen_idler'e TÜM id'leri döndür (haric_idler zaten ayrıca "
        "elenecek). SADECE kullanıcı gerçekten POZİTİF bir TEMA/KATEGORİ "
        "belirtmişse (ör. 'doğa gezmek istiyorum') secilen_idler'i o temaya "
        "göre filtrele. Kullanıcı sadece süre belirtip başka hiçbir şey "
        "söylemediyse (ör. '6 saatim var') de yine TÜM id'leri döndür.\n"
        "SADECE şu formatta geçerli JSON döndür, başka hiçbir açıklama/metin "
        'yazma: {"sure_saat": 6, "sabit_baslangic_id": null, '
        '"sabit_bitis_id": null, "istenilen_idler": [7], "haric_idler": [4,9], '
        '"secilen_idler": [1,2,3]}'
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
    istenilen_idler = []
    haric_idler = set()

    try:
        yanit = _llm_al().invoke([("system", sistem), ("human", kullanici)])
        metin = _icerik_metni(yanit.content).strip().replace("```json", "").replace("```", "").strip()
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

        ham_istenilen = veri.get("istenilen_idler") or []
        for x in ham_istenilen:
            if isinstance(x, (int, float)):
                xi = int(x)
                if xi in id_harita and xi not in (baslangic_id, bitis_id):
                    istenilen_idler.append(xi)
        istenilen_idler = list(dict.fromkeys(istenilen_idler))  # sırayı koru, tekrarı at

        ham_haric = veri.get("haric_idler") or []
        haric_idler = set()
        for x in ham_haric:
            if isinstance(x, (int, float)) and int(x) in id_harita:
                haric_idler.add(int(x))

        secilen_idler = set(veri.get("secilen_idler") or [])
        if secilen_idler:
            filtrelenmis = [m for m in mekanlar if m["id"] in secilen_idler]
            if filtrelenmis:
                adaylar = filtrelenmis
                kategoriler = sorted({m["tur"] for m in filtrelenmis})
    except Exception as e:
        print(f"[rota_motoru] Mesaj çözümlenemedi, varsayılanlara düşülüyor: {e!r}")

    if sure_saat is None:
        sure_saat = DEFAULT_SURE_SAAT

    return sure_saat, sure_belirtilmedi, adaylar, kategoriler, baslangic_id, bitis_id, istenilen_idler, haric_idler


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
    (sure_saat, sure_belirtilmedi, adaylar, kategoriler,
     baslangic_id, bitis_id, istenilen_idler, haric_idler) = _mesaji_coz(tum_mekanlar, mesaj)
    adaylar = list(adaylar)

    # HARİÇ TUTULANLAR: hiçbir aşamada kullanılmasın (en güçlü kural)
    if haric_idler:
        adaylar = [m for m in adaylar if m["id"] not in haric_idler]
        istenilen_idler = [i for i in istenilen_idler if i not in haric_idler]
        if baslangic_id in haric_idler:
            baslangic_id = None
        if bitis_id in haric_idler:
            bitis_id = None

    baslangic_mekan = id_harita.get(baslangic_id) if baslangic_id is not None else None
    bitis_mekan = id_harita.get(bitis_id) if bitis_id is not None else None
    istenilen_havuz = [id_harita[i] for i in istenilen_idler if i in id_harita]

    # Zorunlu/istenilen mekanlar, genel havuzda ikinci kez seçilmesin
    disari_id_seti = {m["id"] for m in ([baslangic_mekan] if baslangic_mekan else [])}
    disari_id_seti |= {m["id"] for m in ([bitis_mekan] if bitis_mekan else [])}
    disari_id_seti |= {m["id"] for m in istenilen_havuz}
    adaylar = [m for m in adaylar if m["id"] not in disari_id_seti]

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

    def bitis_icin_yer_var_mi(aday_lat, aday_lon, ekstra_gerekli, kalan):
        """Bu adayı eklersek, zorunlu bitişe hâlâ yetecek kadar süre kalır mı?"""
        if not bitis_mekan:
            return ekstra_gerekli <= kalan
        kalan_sonra = kalan - ekstra_gerekli
        if kalan_sonra < 0:
            return False
        bitise_yol = _yol_dk(aday_lat, aday_lon, bitis_mekan["enlem"], bitis_mekan["boylam"])
        bitis_gerekli = bitise_yol + bitis_mekan["sure_dk"]
        return bitis_gerekli <= kalan_sonra

    # 1) Zorunlu başlangıç — kullanıcı açıkça istedi, koşulsuz eklenir
    if baslangic_mekan:
        yol = _yol_dk(su_anki_lat, su_anki_lon, baslangic_mekan["enlem"], baslangic_mekan["boylam"])
        kalan_dk -= durak_ekle(baslangic_mekan, yol)

    # 2) İSTENİLEN mekanlar — genel havuzdan ÖNCE, öncelikli yerleştirilir
    while istenilen_havuz and kalan_dk > 0:
        en_yakin = min(
            istenilen_havuz,
            key=lambda m: _yol_dk(su_anki_lat, su_anki_lon, m["enlem"], m["boylam"]),
        )
        yol = _yol_dk(su_anki_lat, su_anki_lon, en_yakin["enlem"], en_yakin["boylam"])
        gerekli = yol + en_yakin["sure_dk"]

        if bitis_icin_yer_var_mi(su_anki_lat, su_anki_lon, gerekli, kalan_dk):
            kalan_dk -= durak_ekle(en_yakin, yol)
        istenilen_havuz.remove(en_yakin)  # sığdı ya da sığmadı, ele alındı

    # 3) Genel tema havuzu — en-yakın mantığıyla kalan süreyi doldurur
    while adaylar and kalan_dk > 0:
        en_yakin = min(
            adaylar,
            key=lambda m: _yol_dk(su_anki_lat, su_anki_lon, m["enlem"], m["boylam"]),
        )
        yol = _yol_dk(su_anki_lat, su_anki_lon, en_yakin["enlem"], en_yakin["boylam"])
        gerekli = yol + en_yakin["sure_dk"]

        if bitis_icin_yer_var_mi(su_anki_lat, su_anki_lon, gerekli, kalan_dk):
            kalan_dk -= durak_ekle(en_yakin, yol)
        adaylar.remove(en_yakin)

    # 4) Zorunlu bitiş — kullanıcı açıkça istedi, bütçeyi az aşsa bile eklenir
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