# -*- coding: utf-8 -*-
"""
api.py
------
Sinop Akıllı Turizm Platformu - FastAPI Sohbet Servisi (Aşama 2)

Session tabanlı çalışır: her konuşma kendi session_id'sine sahiptir,
geçmişi bot_engine'deki merkezi depoda ayrı tutulur. Böylece aynı anda
birden fazla kişi (ör. 3 kişi Diyojen ile) konuşsa bile sohbetler karışmaz.

Çalıştırma:
    export GROQ_API_KEY="..."
    uvicorn api:app --reload

Endpoint'ler:
    GET  /                 -> basit test arayüzü (tarayıcıdan test)
    GET  /katalog          -> kategoriler ve öğeler
    POST /oturum/baslat    -> yeni session açar, session_id döner
    POST /sohbet           -> session_id + mesaj -> cevap
    POST /oturum/kapat     -> session'ı kapatır
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware  # <-- BUNU EKLEDİK

import bot_engine
import katalog
from fastapi.responses import FileResponse
from pathlib import Path


app = FastAPI(title="Sinop Akıllı Turizm API")


# --- CORS AYARLARI BURAYA EKLENİR ---
# React/Next.js uygulamanın bu API'ye erişebilmesi için gereklidir.
'''
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js'in çalıştığı adres (Geliştirme için "*" da yapabilirsin)
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, OPTIONS vb. tüm metodlara izin ver
    allow_headers=["*"],  # Tüm header'lara izin ver
)
'''

app.add_middleware(
    CORSMiddleware,
    # Geliştirme sırasında Compose Web dev server portu (8080/8081/8082...) ve
    # erişim adresi (localhost / 127.0.0.1 / PC'nin LAN IP'si) sık değişiyor.
    # Regex ile localhost, 127.0.0.1 ve 192.168.x.x'ten HERHANGİ bir porta izin ver.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}):\d+",
    allow_origins=[
        "http://localhost:3000",   # Next.js (varsa)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# İstek/yanıt modelleri
class OturumBaslatIstek(BaseModel):
    kategori: str          # ör. "lezzetler"
    oge: str               # ör. "sinop_mantisi"


class OturumBaslatYanit(BaseModel):
    session_id: str
    baslik: str
    karsilama: str


class SohbetIstek(BaseModel):
    session_id: str
    mesaj: str


class SohbetYanit(BaseModel):
    session_id: str
    cevap: str


class OturumKapatIstek(BaseModel):
    session_id: str


# Katalog (kategoriler + öğeler) — frontend menüyü buradan çizer
@app.get("/katalog")
def katalog_listele():
    sonuc = {}
    for kat_kodu, kat in katalog.KATALOG.items():
        sonuc[kat_kodu] = {
            "ad": kat["ad"],
            "ogeler": [
                {"kod": oge_kodu, "ad": oge["ad"]}
                for oge_kodu, oge in kat["ogeler"].items()
            ],
        }
    return sonuc


# Oturum başlat: persona + .md yükle, session aç, karşılama döndür
@app.post("/oturum/baslat", response_model=OturumBaslatYanit)
def oturum_baslat(istek: OturumBaslatIstek):
    oge = katalog.oge_getir(istek.kategori, istek.oge)
    if oge is None:
        raise HTTPException(status_code=404, detail="Kategori veya öğe bulunamadı.")

    # bot_engine, personayı ve .md'yi yükleyip session açar, session_id döner
    session_id = bot_engine.oturum_baslat(
        kategori=istek.kategori,
        persona_adi=oge["persona"],
        alt_klasor=oge["klasor"],
        dosya_adi=oge["dosya"],
        baslik=oge["ad"],
    )
    return OturumBaslatYanit(
        session_id=session_id,
        baslik=oge["ad"],
        karsilama=oge.get("karsilama", ""),
    )


# Sohbet: session_id + mesaj -> o session'ın geçmişiyle cevap
@app.post("/sohbet", response_model=SohbetYanit)
def sohbet(istek: SohbetIstek):
    if not istek.mesaj.strip():
        raise HTTPException(status_code=400, detail="Boş mesaj gönderilemez.")
    try:
        cevap = bot_engine.cevap_uret(istek.session_id, istek.mesaj)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Geçersiz veya süresi dolmuş session_id. Önce /oturum/baslat çağırın.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Yanıt üretilemedi: {e}")
    # Eğer cevap Gemini'den geliyorsa (liste formundaysa) içindeki metni al:
    if isinstance(cevap, list) and len(cevap) > 0 and 'text' in cevap[0]:
        cevap_metni = cevap[0]['text']
    else:
        # Groq'tan geliyorsa (zaten metinse) doğrudan kullan:
        cevap_metni = str(cevap)

    return SohbetYanit(session_id=istek.session_id, cevap=cevap_metni)


# Oturum kapat
@app.post("/oturum/kapat")
def oturum_kapat(istek: OturumKapatIstek):
    bot_engine.oturum_kapat(istek.session_id)
    return {"durum": "kapatildi", "session_id": istek.session_id}

# --- GÖRSEL SUNUCUSU ---
# Kural: görsel adı .md dosya adıyla birebir aynı, uzantı serbest (.jpg/.png/.webp denenir).
# İstek: GET /gorseller/{kategori}/{kod}  (uzantı YAZMA — sunucu kendi bulur)
GORSELLER_DIZINI = Path(__file__).parent / "gorseller"
GECERLI_GORSEL_KATEGORILERI = {"kisiler", "mekanlar", "lezzetler", "doga", "kart"}
GECERLI_UZANTILAR = (".jpg", ".jpeg", ".png", ".webp")

@app.get("/gorseller/{kategori}/{kod}")
def gorsel_getir(kategori: str, kod: str):
    if kategori not in GECERLI_GORSEL_KATEGORILERI:
        raise HTTPException(status_code=404, detail="Geçersiz görsel kategorisi.")
    if "/" in kod or "\\" in kod or ".." in kod:
        raise HTTPException(status_code=404, detail="Geçersiz dosya adı.")
    for uzanti in GECERLI_UZANTILAR:
        yol = GORSELLER_DIZINI / kategori / f"{kod}{uzanti}"
        if yol.is_file():
            return FileResponse(yol)
    raise HTTPException(status_code=404, detail="Görsel bulunamadı.")


# Basit test arayüzü (tarayıcıdan iki sekme açıp karışma testi için)
@app.get("/")
def succes():
    return {
        "durum" : "çalışıyor"
    }