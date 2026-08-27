import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware  # <-- BUNU EKLEDİK

import bot_engine
import katalog
from fastapi.responses import FileResponse
from pathlib import Path
import rota_motoru
from fastapi import Form, File, UploadFile, Header, Depends
import admin_motoru


app = FastAPI(title="Sinop Akıllı Turizm API")

# uygulamanın bu API'ye erişebilmesi için gereklidir.

'''app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}):\d+",
    allow_origins=[
        "http://localhost:3000",   # Next.js (varsa)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)'''

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Canlıda her yerden gelen isteklere izin ver
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# İstek/yanıt modelleri
class OturumBaslatIstek(BaseModel):
    kategori: str          # "lezzetler"
    oge: str               # "sinop_mantisi"


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

class RotaIstek(BaseModel):
    enlem: float
    boylam: float
    sure_saat: int
    turler: list[str] = []


#frontend menüyü buradan çizer
@app.get("/katalog")
def katalog_listele():
    sonuc = {}
    for kat_kodu, kat in katalog.KATALOG.items():
        sonuc[kat_kodu] = {
            "ad": kat["ad"],
            "ogeler": [
                {"kod": oge_kodu, "ad": oge["ad"], "anlatim_var": oge.get("anlatim_var", False)}
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
#görsel adı .md dosya adıyla birebir aynı olmak zorunda.
GORSELLER_DIZINI = Path(__file__).parent / "gorseller"
GECERLI_GORSEL_KATEGORILERI = {"kisiler", "mekanlar", "lezzetler", "doga", "tescil", "kart"}
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

@app.post("/rota/olustur")
def rota_olustur_endpoint(istek: RotaIstek):
    try:
        return rota_motoru.rota_olustur(istek.enlem, istek.boylam, istek.sure_saat, istek.turler)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rota oluşturulamadı: {e}")


@app.get("/rota/varsayilanlar")
def rota_varsayilanlar_endpoint(enlem: float, boylam: float):
    try:
        return {"rotalar": rota_motoru.varsayilan_rotalar_olustur(enlem, boylam)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Varsayılan rotalar oluşturulamadı: {e}")


@app.get("/rota/kategoriler")
def rota_kategoriler_endpoint():
    return rota_motoru.kategori_bilgileri()


# --- ADMIN ---

class AdminGirisIstek(BaseModel):
    kullanici_adi: str
    sifre: str


@app.post("/admin/giris")
def admin_giris(istek: AdminGirisIstek):
    try:
        token = admin_motoru.giris_yap(istek.kullanici_adi, istek.sifre)
    except admin_motoru.AdminHatasi as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"token": token}


def admin_yetki_kontrol(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    if not admin_motoru.token_gecerli_mi(x_admin_token):
        raise HTTPException(
            status_code=401,
            detail="Geçersiz ya da süresi dolmuş oturum. Lütfen tekrar giriş yapın.",
        )
    return True


@app.post("/admin/cikis")
def admin_cikis(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    admin_motoru.cikis_yap(x_admin_token)
    return {"durum": "cikis_yapildi"}


ANLATIM_DIZINI = Path(__file__).parent / "anlatim"

@app.get("/anlatim/{kategori}/{kod}")
def anlatim_getir(kategori: str, kod: str):
    if "/" in kod or "\\" in kod or ".." in kod:
        raise HTTPException(status_code=404, detail="Geçersiz dosya adı.")
    yol = ANLATIM_DIZINI / kategori / f"{kod}.md"
    if not yol.is_file():
        raise HTTPException(status_code=404, detail="Bu içerik için anlatım metni bulunamadı.")
    return {"metin": yol.read_text(encoding="utf-8").strip()}

ROTA_ANLATIM_DIZINI = Path(__file__).parent / "rota_anlatim"

@app.get("/rota-anlatim/{mekan_id}")
def rota_anlatim_getir(mekan_id: int):
    yol = ROTA_ANLATIM_DIZINI / f"{mekan_id}.md"
    if not yol.is_file():
        raise HTTPException(status_code=404, detail="Bu durak için anlatım metni bulunamadı.")
    return {"metin": yol.read_text(encoding="utf-8").strip()}

# --- PERSONA: EKLE (anlatim alanı eklendi) ---
@app.post("/admin/persona-ekle")
async def admin_persona_ekle(
    kategori: str = Form(...),
    ad: str = Form(...),
    karsilama: str = Form(...),
    icerik: str = Form(...),
    kod: str = Form(None),
    anlatim: str = Form(None),
    gorsel: UploadFile = File(...),
    _yetki: bool = Depends(admin_yetki_kontrol),
):
    gorsel_bytes = await gorsel.read()
    gorsel_uzanti = os.path.splitext(gorsel.filename or "")[1]
    try:
        return admin_motoru.persona_ekle(
            kategori, ad, karsilama, icerik, kod, gorsel_bytes, gorsel_uzanti, anlatim
        )
    except admin_motoru.AdminHatasi as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/persona/{kategori}/{kod}")
def admin_persona_getir(kategori: str, kod: str, _yetki: bool = Depends(admin_yetki_kontrol)):
    try:
        return admin_motoru.persona_getir(kategori, kod)
    except admin_motoru.AdminHatasi as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/admin/rota-yeri/{mekan_id}")
def admin_rota_yeri_getir(mekan_id: int, _yetki: bool = Depends(admin_yetki_kontrol)):
    try:
        return admin_motoru.rota_yeri_getir(mekan_id)
    except admin_motoru.AdminHatasi as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- PERSONA: GÜNCELLE ---
@app.put("/admin/persona-guncelle/{kategori}/{kod}")
async def admin_persona_guncelle(
    kategori: str,
    kod: str,
    ad: str = Form(...),
    karsilama: str = Form(...),
    icerik: str = Form(...),
    anlatim: str = Form(default=""),
    anlatim_kaldir: bool = Form(default=False),
    gorsel: UploadFile = File(None),
    _yetki: bool = Depends(admin_yetki_kontrol),
):
    gorsel_bytes = None
    gorsel_uzanti = None
    if gorsel is not None and gorsel.filename:   # boş dosya parçasını (Swagger "Send empty value") görmezden gel
        gorsel_bytes = await gorsel.read()
        gorsel_uzanti = os.path.splitext(gorsel.filename or "")[1]
    try:
        return admin_motoru.persona_guncelle(
            kategori, kod, ad, karsilama, icerik, anlatim, anlatim_kaldir, gorsel_bytes, gorsel_uzanti
        )
    except admin_motoru.AdminHatasi as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- PERSONA: SİL ---
@app.delete("/admin/persona-sil/{kategori}/{kod}")
def admin_persona_sil(
    kategori: str,
    kod: str,
    _yetki: bool = Depends(admin_yetki_kontrol),
):
    try:
        return admin_motoru.persona_sil(kategori, kod)
    except admin_motoru.AdminHatasi as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- ROTA YERİ: EKLE (anlatim alanı eklendi) ---
class RotaYerEkleIstek(BaseModel):
    ad: str
    enlem: float
    boylam: float
    sure_dk: int
    aciklama: str
    anlatim: str | None = None


@app.post("/admin/rota-yer-ekle")
def admin_rota_yer_ekle(
    istek: RotaYerEkleIstek,
    _yetki: bool = Depends(admin_yetki_kontrol),
):
    try:
        return admin_motoru.rota_yeri_ekle(
            istek.ad, istek.enlem, istek.boylam, istek.sure_dk, istek.aciklama, istek.anlatim
        )
    except admin_motoru.AdminHatasi as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- ROTA YERİ: GÜNCELLE ---
class RotaYerGuncelleIstek(BaseModel):
    ad: str
    enlem: float
    boylam: float
    sure_dk: int
    aciklama: str
    anlatim: str | None = None


@app.put("/admin/rota-yer-guncelle/{mekan_id}")
def admin_rota_yer_guncelle(
    mekan_id: int,
    istek: RotaYerGuncelleIstek,
    _yetki: bool = Depends(admin_yetki_kontrol),
):
    try:
        return admin_motoru.rota_yeri_guncelle(
            mekan_id, istek.ad, istek.enlem, istek.boylam, istek.sure_dk, istek.aciklama, istek.anlatim
        )
    except admin_motoru.AdminHatasi as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/rota-yerleri")
def admin_rota_yerleri_listele(_yetki: bool = Depends(admin_yetki_kontrol)):
    return {"mekanlar": rota_motoru.tum_mekanlari_listele()}

# --- ROTA YERİ: SİL ---
@app.delete("/admin/rota-yer-sil/{mekan_id}")
def admin_rota_yer_sil(
    mekan_id: int,
    _yetki: bool = Depends(admin_yetki_kontrol),
):
    try:
        return admin_motoru.rota_yeri_sil(mekan_id)
    except admin_motoru.AdminHatasi as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/")
def succes():
    return {
        "durum" : "çalışıyor"
    }