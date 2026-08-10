# Sinop Akıllı Turizm Platformu — Veri ve Prompt Katmanı

**KUZKA Sinop YDO Projesi** · Hazırlayan: Kadir Deliceli

Bu klasör, projenin yapay zeka botlarının **karakterini** (prompts.yaml) ve
**bilgi kaynağını** (kaynakca/ altındaki .md dosyaları) içerir. "Separation of
Concerns" (Sorumlulukların Ayrılması) prensibine göre karakter ile bilgi
tamamen ayrılmıştır.

## Klasör Yapısı

```
kuzey_kapisi_projesi/
├── prompts.yaml              # Tüm botların karakteri (persona) + kırmızı çizgiler
├── README.md                 # Bu dosya
└── kaynakca/                 # Botların okuduğu resmi bilgi (RAG kaynağı)
    ├── kisiler/    (18 dosya) # Diyojen, Katip Kadir, Mithridates, Sabahattin Ali...
    ├── mekanlar/   (17 dosya) # Sinop Cezaevi, Alaaddin Camii, Sinop Kalesi...
    ├── lezzetler/  (21 dosya) # Sinop Mantısı, Nokul, Zılbıt Böreği, Keşkek...
    └── doga/       (21 dosya) # Hamsilos, Erfelek Şelaleleri, İnceburun...
```

## Nasıl Çalışır? (Veri Enjeksiyon Akışı)

1. Kullanıcı arayüzde bir seçeneğe tıklar (örn: "Sinop Mantısı").
2. FastAPI, ilgili `.md` dosyasını okur (`kaynakca/lezzetler/sinop_mantisi.md`).
3. `prompts.yaml` dosyasından ilgili persona çekilir (örn: `lezzetler.asci`).
4. Markdown'dan okunan bilgi, persona'nın `{context}` değişkenine enjekte edilir.
5. Birleşen metin modele gider; bot bu sınırlar içinde yanıt üretir.

Her `.md` dosyasının başında hangi personayı kullanacağını gösteren bir HTML
yorumu (`<!-- persona: ... -->`) vardır; kod tarafında eşleştirmeyi kolaylaştırır.

## Persona (Karakter) Mantığı

Her figür için ayrı prompt YAZILMAZ. **Kategori bazlı persona** kullanılır:

| Persona | Kapsam | Web Araması |
|---|---|---|
| `kisiler.filozof_diyojen` | Diyojen (özel karakter) | KAPALI |
| `kisiler.katip_kadir` | Katip Kadir (kısmen kurgusal anlatıcı) | KAPALI |
| `kisiler.sahsiyet_rehberi` | Diğer tüm tarihi/kültürel şahsiyetler | AÇIK (yalnızca resmi/güvenilir kaynak) |
| `mekanlar.mekan_rehberi` | Tüm tarihi mekanlar | AÇIK (tamamlayıcı) |
| `lezzetler.asci` | Tüm yöresel yemekler (tek "usta aşçı") | AÇIK (tamamlayıcı) |
| `doga.doga_rehberi` | Tüm doğal güzellikler ve gezi noktaları | AÇIK (tamamlayıcı) |

Yani 77 farklı bilgi dosyası, yalnızca 6 persona ile yönetilir.

## Web Araması Politikası

- **Diyojen ve Katip Kadir web'e KAPALIDIR.** Diyojen'de felsefi abartı
  serbest, Katip Kadir ise kısmen kurgusal bir anlatıcı; ikisi de web'e
  açılırsa karakteri bozulur veya uydurma riski artar. Yalnızca `.md` ile
  konuşurlar.
- **Şahsiyet rehberi (diğer tüm tarihi kişiler) kontrollü web'e AÇIKTIR.**
  Az bilinen bir şahsiyette `.md` yetmezse (örn. "nerede doğdun?"), bot
  bilgiyi YALNIZCA resmi/güvenilir kaynaklardan (Kültür ve Turizm Bakanlığı,
  MEB, TSK resmi sayfaları, Atatürk Kütüphanesi, üniversite/akademik yayınlar,
  TDV İslam Ansiklopedisi, resmi belediye/valilik siteleri) doğrulayarak
  tamamlar. Rastgele blog, forum, sözlük ve reklam sayfalarını kaynak almaz.
- **Mekan, lezzet ve doğa botları da web'e AÇIKTIR ama TAMAMLAYICI olarak**
  ve yine güvenilir/resmi kaynak önceliğiyle. Ana kaynak her zaman `.md`'dir.
- Hiçbir bot web'den geleni **aynen aktarmaz**; `.md` ile çelişen veya abartılı
  turizm iddialarına temkinli yaklaşır ve çelişki halinde `.md`'yi esas alır.
  Yani sistem **%100 web'e teslim olmaz.**

## Sohbetin Çabuk Bitmemesi

Az bilinen şahsiyetlerde bot künyeyi sayıp sohbeti kapatmasın diye iki önlem
alınmıştır:
- Şahsiyet `.md` dosyalarına **"Sohbeti Sürdürmek İçin Bağlantılar"** bölümü
  eklenmiştir. Bu bölüm, kişiyi kendi çağının Sinop'una ve bugün görülebilecek
  gerçek mekânlara bağlar (ör. Kötürüm Bayezid → Alaaddin Camii avlusundaki
  İsfendiyaroğulları Türbesi). Uydurma değildir; verideki gerçek bağların açık
  edilmesidir.
- Persona'ya, "kendini tanıtman sohbetin sonu değil başıdır; dönemini,
  eserlerini ve bunların Sinop'ta nerede görülebileceğini anlat, ziyaretçiye
  yeni kapılar aç" talimatı verilmiştir.

## Kırmızı Çizgiler (Değiştirilemez Kurallar)

`prompts.yaml` içindeki her persona, tek yerden yönetilen ortak bir kırmızı
çizgi bloğunu (`&kirmizi_cizgiler`) taşır:

- **Siyaset yasağı:** Güncel siyaset, partiler, seçimler, siyasetçiler hakkında
  yorum yok, taraf yok.
- **Din yasağı:** Dini inanç, itikat, fıkıh, mezhep, ibadet detayına girilmez.
- Dini kimliği olan şahsiyetler (Çeçe Sultan, Seyyid İbrahim Bilal, Marcion,
  Akila vb.) yalnızca **kendini tanıtır** — kim olduğu, dönemi, Sinop'la bağı —
  ama dini öğreti tartışmasına girmez.
- Bu konularda soru gelirse bot kibarca reddeder:
  *"Bu konuda konuşamam, ama size Sinop hakkında memnuniyetle yardımcı olabilirim."*
- Bot bilmediğini uydurmaz; emin olmadığında bilmediğini söyler.

## İçerik Notları

- `.md` dosyaları damıtılmış ama **çok bölümlü ve doludur** (tanım, tarihçe,
  özellikler, ziyaret/anlatım notları). Böylece botların soru-cevap için yeterli
  malzemesi olur.
- En ikonik başlıklar (Sinop Cezaevi, Sinop Mantısı, Hamsilos, Sinop Kalesi,
  Alaaddin Camii) güvenilir kaynaklardan **teyit edilerek** zenginleştirilmiştir.
  Örneğin Hamsilos için, halk arasında "fiyort" dense de bilimsel olarak
  "ria tipi kıyı" olduğu notu eklenmiştir.
- **Rota/koordinat verisi bu pakete dahil değildir** (Kart 3 — Akıllı Zaman ve
  Rota Düzenleyici için ayrıca hazırlanacaktır).
- Yayına almadan önce tarih ve "en büyük/en eski" gibi kesin iddiaların resmi
  (KUZKA onaylı) kaynakla son teyidi önerilir.
