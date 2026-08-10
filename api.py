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

import bot_engine
import katalog

app = FastAPI(title="Sinop Akıllı Turizm API")


# ------------------------------------------------------------------
# İstek/yanıt modelleri
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Katalog (kategoriler + öğeler) — frontend menüyü buradan çizer
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Oturum başlat: persona + .md yükle, session aç, karşılama döndür
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Sohbet: session_id + mesaj -> o session'ın geçmişiyle cevap
# ------------------------------------------------------------------
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
    return SohbetYanit(session_id=istek.session_id, cevap=cevap)


# ------------------------------------------------------------------
# Oturum kapat
# ------------------------------------------------------------------
@app.post("/oturum/kapat")
def oturum_kapat(istek: OturumKapatIstek):
    bot_engine.oturum_kapat(istek.session_id)
    return {"durum": "kapatildi", "session_id": istek.session_id}


# ------------------------------------------------------------------
# Basit test arayüzü (tarayıcıdan iki sekme açıp karışma testi için)
# ------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def test_arayuzu():
    return """
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sinop Turizm — Test Arayüzü</title>
<style>
  :root { --bg:#0f1720; --card:#16212e; --line:#26384a; --txt:#e6edf3;
          --sub:#93a4b3; --acc:#3fa7d6; --me:#1f6feb; --bot:#22303f; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--txt); }
  header { padding:14px 18px; border-bottom:1px solid var(--line);
           font-weight:600; font-size:15px; }
  header small { color:var(--sub); font-weight:400; }
  .wrap { max-width:720px; margin:0 auto; padding:16px; }
  .row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
  select, button, input {
    background:var(--card); color:var(--txt); border:1px solid var(--line);
    border-radius:8px; padding:9px 12px; font-size:14px; }
  button { cursor:pointer; }
  button.primary { background:var(--acc); color:#062230; border:none; font-weight:600; }
  #baslat { background:var(--me); color:#fff; border:none; font-weight:600; }
  .sid { font-size:12px; color:var(--sub); margin:6px 0 12px; word-break:break-all; }
  #log { border:1px solid var(--line); border-radius:12px; background:var(--card);
         min-height:320px; max-height:52vh; overflow-y:auto; padding:12px; }
  .msg { margin:8px 0; padding:9px 12px; border-radius:10px; max-width:85%;
         line-height:1.45; white-space:pre-wrap; }
  .me  { background:var(--me); color:#fff; margin-left:auto; }
  .bot { background:var(--bot); }
  .sys { color:var(--sub); font-size:12px; text-align:center; margin:8px 0; }
  .send-row { display:flex; gap:8px; margin-top:12px; }
  .send-row input { flex:1; }
  .hint { color:var(--sub); font-size:12px; margin-top:14px; line-height:1.5; }
</style>
</head>
<body>
<header>Sinop Akıllı Turizm — <small>Test Arayüzü (session karışma testi)</small></header>
<div class="wrap">
  <div class="row">
    <select id="kategori"></select>
    <select id="oge"></select>
    <button id="baslat">Oturum Başlat</button>
  </div>
  <div class="sid" id="sid">Henüz oturum yok.</div>
  <div id="log"></div>
  <div class="send-row">
    <input id="mesaj" placeholder="Mesaj yazın..." autocomplete="off" disabled>
    <button class="primary" id="gonder" disabled>Gönder</button>
  </div>
  <div class="hint">
    <b>Karışma testi:</b> Bu sayfayı <b>iki ayrı sekmede</b> açın. İkisinde de
    aynı karakteri (ör. Diyojen) başlatın — her sekme AYRI bir session_id alır.
    Bir sekmede "adım Kadir" deyip diğerinde "adım Ayşe" deyin; sonra ikisinde de
    "adımı hatırlıyor musun?" diye sorun. Cevaplar karışmamalı.
  </div>
</div>
<script>
let sid = null;
const $ = id => document.getElementById(id);

async function katalogYukle() {
  const r = await fetch('/katalog'); const k = await r.json();
  window._kat = k;
  const ks = $('kategori'); ks.innerHTML = '';
  Object.entries(k).forEach(([kod, v]) => {
    const o = document.createElement('option'); o.value = kod; o.textContent = v.ad; ks.appendChild(o);
  });
  ogeYukle();
}
function ogeYukle() {
  const kk = $('kategori').value; const os = $('oge'); os.innerHTML = '';
  window._kat[kk].ogeler.forEach(o => {
    const el = document.createElement('option'); el.value = o.kod; el.textContent = o.ad; os.appendChild(el);
  });
}
$('kategori').addEventListener('change', ogeYukle);

function ekle(sinif, metin) {
  const d = document.createElement('div'); d.className = 'msg ' + sinif; d.textContent = metin;
  $('log').appendChild(d); $('log').scrollTop = $('log').scrollHeight;
}
function sistem(metin){ const d=document.createElement('div'); d.className='sys'; d.textContent=metin; $('log').appendChild(d); }

$('baslat').addEventListener('click', async () => {
  const kategori = $('kategori').value, oge = $('oge').value;
  const r = await fetch('/oturum/baslat', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({kategori, oge})
  });
  if (!r.ok) { alert('Oturum açılamadı'); return; }
  const d = await r.json();
  sid = d.session_id;
  $('sid').textContent = 'session_id: ' + sid;
  $('log').innerHTML = '';
  sistem('— ' + d.baslik + ' ile sohbet —');
  if (d.karsilama) ekle('bot', d.karsilama);
  $('mesaj').disabled = false; $('gonder').disabled = false; $('mesaj').focus();
});

async function gonder() {
  const m = $('mesaj').value.trim();
  if (!m || !sid) return;
  ekle('me', m); $('mesaj').value = '';
  $('gonder').disabled = true;
  try {
    const r = await fetch('/sohbet', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({session_id: sid, mesaj: m})
    });
    const d = await r.json();
    if (!r.ok) { ekle('bot', '[Hata] ' + (d.detail || 'bilinmiyor')); }
    else { ekle('bot', d.cevap); }
  } catch(e) { ekle('bot', '[Bağlantı hatası]'); }
  $('gonder').disabled = false; $('mesaj').focus();
}
$('gonder').addEventListener('click', gonder);
$('mesaj').addEventListener('keydown', e => { if (e.key === 'Enter') gonder(); });

katalogYukle();
</script>
</body>
</html>
"""
