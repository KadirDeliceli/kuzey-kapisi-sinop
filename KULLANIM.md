# Terminal Prototipi — Çalıştırma (Aşama 1)

Bu aşamada proje, LangChain + Groq ile çalışan **terminal tabanlı** bir
sohbet prototipidir. Hafıza (kalıcı), FastAPI, arayüz ve rota sonraki
aşamalara bırakılmıştır.

## 1. Gereksinimler

```bash
pip install langchain-groq langchain-core pyyaml
```

## 2. Groq API anahtarı

https://console.groq.com adresinden ücretsiz bir API anahtarı al ve ortam
değişkeni olarak tanımla:

```bash
# Linux / Mac
export GROQ_API_KEY="buraya_anahtarin"

# Windows (cmd)
set GROQ_API_KEY=buraya_anahtarin
```

## 3. Çalıştır

```bash
python main.py
```

## 4. Kullanım (Hiyerarşi)

```
ANA MENÜ (4 kategori)
   │  1) Tarihi Kişiler   2) Tarihi Mekanlar
   │  3) Yöresel Lezzetler 4) Doğal Güzellikler
   ▼
KATEGORİ SEÇENEKLERİ (ör. Diyojen, Sabahattin Ali...)
   ▼
SOHBET (while True) — karakterle konuşursun
```

- Sohbetteyken **`q`** → kategori seçenek listesine döner.
- Seçenek listesindeyken **`q`** → ana menüye (4 kategori) döner.
- Ana menüde **`q`** → programdan çıkar.

## 5. Dosya Yapısı

- `main.py` — hiyerarşik menü + 4 kategori fonksiyonu (senin akışın).
- `bot_engine.py` — persona/kaynak yükleme + Groq sohbet çekirdeği (ortak motor).
- `prompts.yaml` — persona (karakter) tanımları + kırmızı çizgiler.
- `kaynakca/` — her öğenin bilgi (.md) dosyaları (context kaynağı).

## 6. Yeni Öğe Eklemek

`main.py` içindeki ilgili listeye (ör. `TARIHI_KISILER`) tek satır eklemen
yeterli:

```python
("Görünen Ad", "persona_adi", "alt_klasor", "dosya_adi", "karşılama cümlesi"),
```

`persona_adi` prompts.yaml'daki personadır; `dosya_adi` ise
`kaynakca/alt_klasor/dosya_adi.md` dosyasını işaret eder.

## Model Seçimi

`bot_engine.py` içinde `GROQ_MODEL`:
- `llama-3.3-70b-versatile` — daha güçlü/tutarlı (varsayılan, persona için iyi).
- `llama-3.1-8b-instant` — daha hızlı ve ucuz.

## Notlar

- Şu anki hafıza yalnızca **oturum içidir** (o karakterle konuşurken tutulur,
  `q` ile çıkınca sıfırlanır). Kalıcı hafıza sonraki aşamada.
- Web araması prompt'larda tanımlıdır; canlı web aracı entegrasyonu da
  sonraki aşamaya aittir (şu an model kendi bilgisiyle + .md ile yanıtlar).
