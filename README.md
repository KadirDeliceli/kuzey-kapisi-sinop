# Kuzey Kapısı — Sinop Akıllı Turizm Platformu (Backend / API)

**KUZKA Sinop Yatırım Destek Ofisi** için geliştirilen, Sinop'u yapay zeka
rehberleriyle tanıtan bölgesel turizm platformunun **FastAPI backend'i**.

Bu API; tarihi kişiler, tarihi mekanlar, yöresel lezzetler, doğal güzellikler
ve tescilli (coğrafi işaretli) ürünler için ayrı ayrı **AI sohbet karakterleri**
sunar ve kullanıcının konumu + vaktine göre **akıllı gezi rotası** oluşturur.
Bu API'yi hem bir **Next.js web arayüzü** hem de bir **Kotlin Multiplatform
(Android / iOS / Web) uygulaması** tüketir — backend ikisinden de bağımsızdır.

---

## İçindekiler

1. [Özellikler](#özellikler)
2. [Mimari / Teknoloji Yığını](#mimari--teknoloji-yığını)
3. [Klasör Yapısı](#klasör-yapısı)
4. [Kurulum](#kurulum)
5. [API Referansı](#api-referansı)
6. [Yeni İçerik Ekleme](#yeni-i̇çerik-ekleme)
7. [Persona / Prompt Mimarisi](#persona--prompt-mimarisi)
8. [Akıllı Rota Planlayıcı](#akıllı-rota-planlayıcı)
9. [Yerel Ağda Çalıştırma (Mobil/Web İstemciler İçin)](#yerel-ağda-çalıştırma-mobilweb-i̇stemciler-i̇çin)
10. [Bu API'yi Kullanan İstemciler](#bu-apiyi-kullanan-i̇stemciler)
11. [Sorun Giderme](#sorun-giderme)

---

## Özellikler

- **Kategori bazlı AI sohbet botları**: her tarihi kişi, mekan, yemek, doğal
  alan ve tescilli ürün için ayrı bir `.md` bilgi dosyası + ortak bir persona
  (karakter) ile canlandırılan sohbet deneyimi.
- **Otomatik katalog keşfi**: yeni içerik eklemek için kod değiştirmeye gerek
  yok — ilgili klasöre bir `.md` dosyası koymak yeterli.
- **Session tabanlı sohbet hafızası**: her konuşma kendi `session_id`'sine
  sahiptir, aynı anda birden fazla kullanıcı farklı botlarla (hatta aynı
  botla) karışmadan konuşabilir.
- **Görsel servisi**: kart/kişi/mekan görselleri tek bir endpoint'ten,
  dosya adına göre otomatik bulunarak sunulur.
- **Akıllı Rota Planlayıcı**: kullanıcının konumu + "6 saatim var, doğa
  gezmek istiyorum" gibi serbest bir mesajından, süre bütçesine uyan,
  tercihe göre filtrelenmiş, sıralı bir gezi rotası üretir.

## Mimari / Teknoloji Yığını

| Katman | Teknoloji |
|---|---|
| Web çatısı | FastAPI + Pydantic |
| Sunucu | Uvicorn |
| LLM sağlayıcı | Groq (LangChain üzerinden) |
| Persona tanımları | YAML (`prompts.yaml`) |
| İçerik | Markdown dosyaları (`kaynakca/`) |
| Rota verisi | SQLite (`kuzey_kapisi.db`) |
| Ortam değişkenleri | `python-dotenv` (`.env`) |

## Klasör Yapısı

```
KuzeyKapisi/
├── .env                    # GROQ_API_KEY vb. gizli anahtarlar (Git'e girmez)
├── .env.example             # .env için şablon (Git'e girer, gerçek anahtar içermez)
├── .gitignore
├── api.py                  # FastAPI uygulaması, tüm endpoint'ler burada tanımlı
├── bot_engine.py           # LLM çağrısı, session/hafıza yönetimi
├── katalog.py              # kaynakca/ klasörünü otomatik tarayıp katalog üretir
├── rota_motoru.py          # Akıllı Rota Planlayıcı motoru
├── create_db.py            # kuzey_kapisi.db'yi (mekanlar tablosu) oluşturan betik
├── kuzey_kapisi.db          # SQLite veritabanı (mekanlar tablosu)
├── prompts.yaml            # Tüm AI karakterlerinin (persona) tanımları
├── requirements.txt         # Python bağımlılıkları
├── default.png             # (opsiyonel) genel fallback görsel
├── kaynakca/                # İçerik: her .md dosyası bir bot/karakter
│   ├── kisiler/
│   ├── mekanlar/
│   ├── lezzetler/
│   ├── doga/
│   └── tescil/
└── gorseller/                # Görseller: kaynakca ile birebir aynı isimlendirme
    ├── kisiler/
    ├── mekanlar/
    ├── lezzetler/
    ├── doga/
    ├── tescil/
    └── kart/                 # Ana/alt menü kart kapakları
```

## Kurulum

### Gereksinimler

- Python 3.10+
- Bir Groq API anahtarı ([console.groq.com](https://console.groq.com))

### Adımlar

**1. Sanal ortam oluştur ve etkinleştir**

```powershell
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux
```

**2. Bağımlılıkları kur**

```powershell
pip install -r requirements.txt
```

**3. `.env` dosyasını oluştur**

`.env.example` dosyasını kopyalayıp kendi anahtarlarını gir:
```powershell
copy .env.example .env
```
En azından `GROQ_API_KEY` doldurulmalı. `LANGCHAIN_TRACING_V2=true` bırakılırsa
LangSmith izleme aktif olur ve ayrı bir LangSmith anahtarı ister; kullanmıyorsan
`false` yap.

**4. Veritabanını hazırla**

`kuzey_kapisi.db` yoksa ya da `mekanlar` tablosunu sıfırdan kurman gerekiyorsa
`create_db.py`'yi çalıştır:
```powershell
python create_db.py
```

**5. Sunucuyu başlat**

```powershell
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```
`--host 0.0.0.0` sadece kendi bilgisayarından test edeceksen şart değil
(`127.0.0.1` de olur), ama telefon/başka bir cihazdan erişeceksen **zorunlu**
(bkz. [Yerel Ağda Çalıştırma](#yerel-ağda-çalıştırma-mobilweb-i̇stemciler-i̇çin)).

**6. Doğrula**

Tarayıcıda `http://127.0.0.1:8000/docs` — interaktif Swagger arayüzü açılır,
tüm endpoint'leri buradan deneyebilirsin. `http://127.0.0.1:8000/` `{"durum":
"çalışıyor"}` dönmeli.

---

## API Referansı

### `GET /`
Basit sağlık kontrolü. → `{"durum": "çalışıyor"}`

### `GET /katalog`
Tüm kategorileri ve içindeki öğeleri döner. Frontend menüleri buradan çizer.

```json
{
  "kisiler": {
    "ad": "Tarihi Kişiler",
    "ogeler": [{"kod": "alaaddin_keykubat", "ad": "I. Alaaddin Keykubat"}, ...]
  },
  "mekanlar": { ... },
  "lezzetler": { ... },
  "doga": { ... },
  "tescil": { ... }
}
```

### `POST /oturum/baslat`
Yeni bir sohbet oturumu açar; persona + ilgili `.md` içeriği yüklenir.

**İstek:**
```json
{"kategori": "kisiler", "oge": "alaaddin_keykubat"}
```
**Yanıt:**
```json
{"session_id": "…", "baslik": "I. Alaaddin Keykubat", "karsilama": "…"}
```
`kategori` veya `oge` bulunamazsa `404`.

### `POST /sohbet`
Var olan bir oturuma mesaj gönderir.

**İstek:**
```json
{"session_id": "…", "mesaj": "Sinop'a nasıl geldin?"}
```
**Yanıt:**
```json
{"session_id": "…", "cevap": "…"}
```
- Boş mesaj → `400`.
- `session_id` bilinmiyorsa (ör. sunucu yeniden başladıysa; hafıza RAM'de
  tutulur, kalıcı değildir) → `404`. İstemciler bu durumda sessizce
  `/oturum/baslat`'ı tekrar çağırıp mesajı yeniden denemelidir.

### `POST /oturum/kapat`
```json
{"session_id": "…"}
```
→ `{"durum": "kapatildi", "session_id": "…"}`

### `GET /gorseller/{kategori}/{kod}`
Bir görseli döner. **Uzantı yazılmaz** — sunucu `gorseller/{kategori}/`
altında `{kod}.jpg`, `.jpeg`, `.png`, `.webp` sırasıyla arar, ilk bulduğunu
döner. Hiçbiri yoksa `404` (istemci bunu kendi varsayılan görseline düşürür).

`kategori` ∈ `kisiler | mekanlar | lezzetler | doga | tescil | kart`

Örnek: `GET /gorseller/kisiler/alaaddin_keykubat`

### `POST /rota/olustur`
Bkz. [Akıllı Rota Planlayıcı](#akıllı-rota-planlayıcı) — ayrı bölümde detaylı
anlatılmıştır.

---

## Yeni İçerik Ekleme

Yeni bir kişi/mekan/lezzet/doğa/tescil eklemek için **kod değiştirmeye gerek
yoktur** — `katalog.py`, `kaynakca/` klasörünü her açılışta otomatik tarar.

**1. `.md` dosyası oluştur**, ilgili klasöre koy (`kaynakca/kisiler/`,
`kaynakca/mekanlar/`, `kaynakca/lezzetler/`, `kaynakca/doga/`,
`kaynakca/tescil/`). Dosyanın üst kısmında şu meta yorumlar bulunmalı:

```markdown
# Görünen Uzun Başlık
<!-- persona: kategori.persona_adi | kart: Tarih ve Kültür -->
<!-- ad: Menüde Görünecek Kısa Ad -->
<!-- karsilama: Sohbet açılışında botun ilk sözü -->

(Buradan sonrası botun bilgi kaynağı — {context} olarak LLM'e enjekte edilir)
```

- `persona` **zorunludur** (`kategori.persona_adi` formatında, `prompts.yaml`
  içindeki bir tanıma karşılık gelmeli) — yoksa dosya sessizce atlanır.
- `ad` ve `karsilama` verilmezse başlıktan otomatik türetilir.

**2. Görseli ekle**: `gorseller/{kategori}/{dosya_adı}.jpg` — **`.md` dosya
adıyla birebir aynı isim** (uzantısız kısım). Örn. `kaynakca/kisiler/
yeni_kisi.md` → `gorseller/kisiler/yeni_kisi.jpg`.

**3. Sunucuyu yeniden başlat** (`--reload` ile çalışıyorsa dosya
kaydedildiğinde zaten kendini tazeler) ve `/katalog`'da yeni öğenin
göründüğünü doğrula.

**Yeni bir kategori/klasör** eklemek istersen (`kaynakca/`'nın altına yepyeni
bir alt klasör), `katalog.py`'deki `KATEGORI_ADLARI` sözlüğüne bir satır
eklemen yeterlidir (kategori adı ve menü sırası için) — eklemesen de klasör
otomatik taranır, sadece menü adı klasör adının capitalize edilmiş hali olur.

---

## Persona / Prompt Mimarisi

Tüm AI karakterlerinin **kişiliği** `prompts.yaml`'da tanımlıdır; **bilgi**
asla bu dosyaya yazılmaz, `kaynakca/` içindeki `.md` dosyalarından gelir ve
`{context}` değişkenine enjekte edilir.

- **Kategori bazlı personalar**: çoğu içerik (21 yemek, 17 mekan vb.) için
  TEK bir ortak persona kullanılır (ör. `lezzetler.asci` — "40 yıllık usta
  Sinop aşçısı"); hangi yemeğin anlatılacağı `.md` dosyasından gelir.
- **Özel/benzersiz personalar**: Sinoplu Diyojen, Katip Kadir gibi tekil
  karakterlerin kendine özel `system_message`'ı vardır.
- **Ortak kırmızı çizgiler**: `kirmizi_cizgiler` adlı bir YAML anchor
  (`&kirmizi_cizgiler`) tüm personalara `*kirmizi_cizgiler` referansıyla
  dahil edilir — dil (sadece Türkçe), siyaset/din yasağı, konu kilidi (bot
  yalnızca kendi konusunu anlatır), uydurma yasağı, cevap uzunluğu gibi
  değişmez kurallar tek bir yerden yönetilir.
- **Konu kilidi**: her bot yalnızca kendisine atanan TEK öğeyi anlatır;
  başka bir şey sorulursa kullanıcıyı ana menüye yönlendirip kendi konusuna
  döner.
- **Web ile bilgi tamamlama**: bazı personalar (`sahsiyet_rehberi`,
  `mekan_rehberi`, `asci`, `doga_rehberi`, `tescil`), `.md`'deki bilgi
  yetmezse yalnızca **resmi/güvenilir kaynaklardan** (bakanlık, üniversite,
  TDV İslam Ansiklopedisi vb.) tamamlama yapabilir; çelişki durumunda
  `.md` içeriği esas alınır.

> YAML'da `<<:` (merge key) yalnızca **mapping'i mapping'e** birleştirebilir.
> `kirmizi_cizgiler` bir metin bloğu olduğu için her persona onu
> `kirmizi_cizgiler: *kirmizi_cizgiler` şeklinde **düz referansla** kullanır
> (`<<: *kirmizi_cizgiler` DEĞİL) — yeni bir persona eklerken bu deseni
> koru, aksi halde YAML parse hatası alırsın.

---

## Akıllı Rota Planlayıcı

`rota_motoru.py`, kullanıcının konumu ve **serbest metin** bir mesajından
("6 saatim var, doğa gezmek istiyorum") otomatik bir gezi rotası üretir.

### Veritabanı şeması

```sql
CREATE TABLE mekanlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    enlem REAL NOT NULL,
    boylam REAL NOT NULL,
    sure_dk INTEGER NOT NULL,   -- o mekanda geçirilecek GEZİ süresi
    tur TEXT NOT NULL,          -- ör. "kültür", "doğa"
    aciklama TEXT NOT NULL
)
```

### `POST /rota/olustur`

**İstek:**
```json
{"enlem": 42.0263, "boylam": 35.1451, "mesaj": "6 saatim var, müze gezmek istiyorum"}
```

**Yanıt:**
```json
{
  "toplam_sure_dk": 360,
  "kullanilan_sure_dk": 317,
  "tercih_kategorisi": ["kültür"],
  "rota": [
    {
      "sira": 1, "id": 15, "ad": "Sinop Cezaevi", "tur": "kültür",
      "aciklama": "…", "enlem": 42.025, "boylam": 35.142,
      "onceki_noktadan_yol_dk": 5, "ziyaret_suresi_dk": 150,
      "varis_toplam_dk": 155,
      "google_maps_url": "https://www.google.com/maps/dir/?api=1&destination=42.025,35.142"
    }
  ],
  "ozet": "Elinizdeki 6 saatlik vakit için 3 duraklı bir rota hazırladık; …"
}
```

### Nasıl çalışır — iki aşamalı hibrit yaklaşım

Rota hesabı **tamamen LLM'e bırakılmaz** (mesafe/süre aritmetiğinde ve
sıralamada LLM'ler güvenilmez); bunun yerine:

1. **LLM (tek çağrı) mesajı 6 parçaya ayrıştırır:**
   - `sure_saat` — kaç saat vakit var (belirtilmemişse `DEFAULT_SURE_SAAT`)
   - `sabit_baslangic_id` — kullanıcı "X ile başlamak istiyorum" dediyse
   - `sabit_bitis_id` — kullanıcı "X ile bitirmek istiyorum" dediyse
   - `istenilen_idler` — kullanıcının isim vererek istediği yer(ler)
     (sırası önemli değil, sadece dahil edilmesi istenir)
   - `haric_idler` — kullanıcının olumsuz belirttiği ("… istemiyorum",
     "… hariç") yer(ler)/tür(ler); **her koşulda** rotadan çıkarılır
   - `secilen_idler` — genel pozitif tema/kategori tercihi (ör. "doğa
     gezmek istiyorum"); yalnızca gerçek bir TEMA belirtildiğinde daralır,
     aksi halde tüm mekanlar aday kalır
2. **Rota kurulumu tamamen deterministik Python kodudur:**
   - Zorunlu başlangıç varsa ilk durak o olur.
   - İstenilen mekanlar, genel havuzdan **önce**, en-yakın (nearest-neighbor)
     mantığıyla öncelikli yerleştirilir.
   - Kalan süre, genel tema havuzuyla doldurulur.
   - Zorunlu bitiş varsa, gerçek son konumdan hesaplanan yol süresiyle en
     sona eklenir (kullanıcı açıkça istediği için bütçeyi az aşsa bile).
   - Her adımda, zorunlu bir bitiş varsa ona yetecek süre kalıp kalmadığı
     kontrol edilir.

### Önemli varsayımlar (gerekirse `rota_motoru.py`'de değiştirin)

- **Rota tek yönlüdür** — başlangıç noktasına dönüş süresi hesaba katılmaz.
- **Yol süresi** gerçek bir rota servisinden değil, kuş uçuşu mesafe (haversine)
  + `ORTALAMA_HIZ_KMH` (varsayılan 32 km/sa) sabitinden hesaplanır. Kendi
  bölgenizin gerçek mesafelerine göre bu sabiti kalibre edin.
- `DB_YOLU` sabiti gerçek `.db` dosya adınızla **birebir** eşleşmeli.

---

## Yerel Ağda Çalıştırma (Mobil/Web İstemciler İçin)

Telefon ya da başka bir bilgisayardan (aynı Wi-Fi/hotspot) bu API'ye
bağlanmak için:

1. **Sunucuyu tüm arayüzlerde dinlet:**
   ```powershell
   uvicorn api:app --reload --host 0.0.0.0 --port 8000
   ```
   `--host 0.0.0.0` **olmadan** sadece kendi bilgisayarından erişilebilir.

2. **PC'nin LAN IP'sini bul:** `ipconfig` (Windows) → bağlı olduğun ağın
   (Wi-Fi/hotspot) **IPv4 Address**'i. İstemci tarafında (`Config.BASE_URL`
   vb.) bu adresi kullan; `127.0.0.1`/`localhost` **telefonda telefonun
   kendisi** demektir, PC değil.

3. **Windows Güvenlik Duvarı'nda 8000 portuna gelen bağlantıya izin ver**
   (en sık karşılaşılan tıkanma noktası budur): `wf.msc` → Gelen Kurallar →
   Yeni Kural → Port → TCP → `8000` → Bağlantıya izin ver → Etki Alanı/Özel/
   Genel üçünü de işaretle.

4. **Ağ profilinin "Özel (Private)" olduğundan emin ol** (özellikle hotspot
   bağlantıları Windows'ta "Genel (Public)" profiline düşer ve bu profilde
   gelen bağlantılar daha sıkı engellenir): Ayarlar → Ağ ve İnternet → Wi-Fi
   → bağlı ağ → Ağ profili türü → **Özel**.

5. **Doğrula:** telefonun **tarayıcısında** `http://<PC_IP>:8000` aç,
   `{"durum": "çalışıyor"}` görmelisin. Bu adımı geçemiyorsan istemci
   uygulaması da bağlanamaz — önce burada çöz.

6. **CORS** (yalnızca web/tarayıcı tabanlı istemciler için, native
   Android/iOS'u etkilemez): `api.py`'deki `CORSMiddleware(allow_origins=[...])`
   listesine geliştirme ortamlarınızın adreslerini ekleyin (Next.js: `http://
   localhost:3000`, Compose Multiplatform Web dev server: genellikle
   `http://localhost:8080`, gerçek port ilk çalıştırmada konsoldan
   doğrulanmalı). Birden fazla istemci varsa geliştirme sürecinde
   `allow_origins=["*"]` kullanmak pratik bir kısayoldur.

---

## Bu API'yi Kullanan İstemciler

| İstemci | Teknoloji | Not |
|---|---|---|
| Web arayüzü | Next.js 14 (App Router) + TypeScript + Tailwind | Ayrı proje: `kuzey-kapisi-frontend/` |
| Android / iOS / Web | Kotlin Multiplatform + Compose Multiplatform | Ayrı proje; MVVM, Ktor ile bu API'ye bağlanır |

Her iki istemci de aynı `/katalog`, `/oturum/baslat`, `/sohbet`,
`/oturum/kapat`, `/gorseller`, `/rota/olustur` sözleşmesini kullanır —
backend'de bir değişiklik ikisini de etkiler.

---

## Sorun Giderme

| Belirti | Olası Sebep |
|---|---|
| `uvicorn` açılışta YAML hatasıyla çöküyor | `prompts.yaml` bozuk — genelde `<<: *kirmizi_cizgiler` gibi geçersiz bir merge kullanımı. Düz referansa (`kirmizi_cizgiler: *kirmizi_cizgiler`) çevirin. |
| `/sohbet` sürekli `404` dönüyor | Sunucu yeniden başladı, hafıza (RAM) sıfırlandı; istemci `/oturum/baslat`'ı tekrar çağırmalı. |
| `/rota/olustur` hata veriyor | `rota_motoru.py`'deki `DB_YOLU`, gerçek `.db` dosya adınızla eşleşmiyor olabilir. |
| Yeni eklediğim `.md` katalogda görünmüyor | Meta yorumlarını (`persona:` zorunlu) kontrol edin; `persona` eksikse dosya sessizce atlanır. |
| Görsel her zaman `404` | Görsel adı `.md` dosya adıyla **birebir** (büyük/küçük harf dahil) eşleşmiyor olabilir; uzantı `.jpg/.jpeg/.png/.webp` dışında bir şeyse de bulunamaz. |
| Telefon/başka cihaz API'ye bağlanamıyor | Bkz. [Yerel Ağda Çalıştırma](#yerel-ağda-çalıştırma-mobilweb-i̇stemciler-i̇çin) — sırasıyla `--host 0.0.0.0`, doğru LAN IP, Windows Firewall kuralı, ağ profili "Özel" mi kontrol edin. |