# -*- coding: utf-8 -*-
"""
bot_engine.py
--------------
Sinop Akıllı Turizm Platformu - Bot Çekirdeği

Bu dosya, sohbet mantığının ortak (tekrar etmeyen) kısmını barındırır:
  - prompts.yaml'dan persona (system_message + kırmızı çizgiler) okuma
  - kaynakca/*.md dosyasından bilgi (context) okuma
  - LangChain + Groq/Gemini ile sohbet zinciri kurma
  - basit oturum içi hafıza (sadece o karakterle konuşulurken)


main.py bu fonksiyonları çağırır. Böylece 4 kategori fonksiyonu sade kalır.
"""

import os
import yaml

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv()
# ------------------------------------------------------------------
# Ayarlar
# ------------------------------------------------------------------
KOK_DIZIN = os.path.dirname(os.path.abspath(__file__))
PROMPTS_YOLU = os.path.join(KOK_DIZIN, "prompts.yaml")
KAYNAKCA_DIZIN = os.path.join(KOK_DIZIN, "kaynakca")

# ------------------------------------------------------------------
# MODEL SAĞLAYICI SEÇİMİ (TEK YERDEN)
# ------------------------------------------------------------------
# Buradaki tek değişkeni değiştirerek tüm yapıyı Groq veya Gemini'ye
# geçirebilirsin. Geri kalan hiçbir fonksiyona dokunmana gerek yok;
# hepsi _llm() üzerinden bu ayarı kullanır.
#
#   SAGLAYICI = "groq"    -> Groq (GROQ_API_KEY gerekir)
#   SAGLAYICI = "gemini"  -> Gemini (GOOGLE_API_KEY gerekir)
SAGLAYICI = "groq"

# Gemini model tercihi
GEMINI_MODEL = "gemini-flash-latest"

# Groq model tercihi:
#   - "llama-3.3-70b-versatile" : daha güçlü/tutarlı (persona için önerilir)
#   - "llama-3.1-8b-instant"    : daha hızlı ve ucuz
#   - "openai/gpt-oss-120b"     : mevcut tercih
GROQ_MODEL = "openai/gpt-oss-120b"

SICAKLIK = 0.5  # persona canlılığı ile tutarlılık dengesi (dil sapmasını azaltır)


# ------------------------------------------------------------------
# prompts.yaml yükleme (bir kez okunur, tekrar tekrar açılmaz)
# ------------------------------------------------------------------
def prompts_yukle():
    with open(PROMPTS_YOLU, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


PROMPTS = prompts_yukle()


def persona_getir(kategori, persona_adi):
    """prompts.yaml içinden bir personanın system_message + kırmızı çizgilerini alır."""
    p = PROMPTS[kategori][persona_adi]
    system_message = p["system_message"]
    kirmizi = p.get("kirmizi_cizgiler", "")
    return system_message, kirmizi


# ------------------------------------------------------------------
# .md kaynak yükleme (context)
# ------------------------------------------------------------------
def kaynak_oku(alt_klasor, dosya_adi):
    """kaynakca/<alt_klasor>/<dosya_adi>.md içeriğini döndürür."""
    yol = os.path.join(KAYNAKCA_DIZIN, alt_klasor, dosya_adi + ".md")
    if not os.path.exists(yol):
        return "(Bu konu için ayrıntılı bilgi dosyası bulunamadı.)"
    with open(yol, "r", encoding="utf-8") as f:
        return f.read().strip()


# ------------------------------------------------------------------
# LLM (tek örnek yeterli)
# ------------------------------------------------------------------
def llm_getir():
    """
    SAGLAYICI ayarına göre uygun LLM örneğini döndürür.
    İlgili API anahtarı tanımlı değilse anlaşılır bir hata verir.
    """
    if SAGLAYICI == "groq":
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError(
                "GROQ_API_KEY tanımlı değil. Terminalde şu şekilde ayarlayın:\n"
                "  export GROQ_API_KEY='...'   (Linux/Mac)\n"
                "  set GROQ_API_KEY=...        (Windows)"
            )
        return ChatGroq(model=GROQ_MODEL, temperature=SICAKLIK)

    elif SAGLAYICI == "gemini":
        if not os.environ.get("GOOGLE_API_KEY"):
            raise RuntimeError(
                "GOOGLE_API_KEY tanımlı değil. Terminalde şu şekilde ayarlayın:\n"
                "  export GOOGLE_API_KEY='...'   (Linux/Mac)\n"
                "  set GOOGLE_API_KEY=...        (Windows)"
            )
        return ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=SICAKLIK)

    else:
        raise ValueError(
            f"Bilinmeyen SAGLAYICI: {SAGLAYICI!r} "
            "(yalnızca 'groq' veya 'gemini' olabilir)."
        )


LLM = None  # ilk sohbette kurulur (lazy)


def _llm():
    global LLM
    if LLM is None:
        LLM = llm_getir()
    return LLM


# ------------------------------------------------------------------
# İÇERİK NORMALİZASYONU (Gemini/LangChain format filtresi)
# ------------------------------------------------------------------
def _icerik_metne(icerik):
    """
    LLM cevabının .content alanını HER ZAMAN düz metne (string) çevirir.

    Neden gerekli?
      Gemini/LangChain cevabı bazen düz metin yerine bir liste
      (content block'ları: [{'type': 'text', 'text': '...'}]) döndürür.
      Bu liste doğrudan AIMessage olarak geçmişe eklenirse, sonraki
      turlarda model kendi geçmişini okuyamaz ve yanıt boş/hatalı gelir
      (API tarafında da Pydantic doğrulama hatasına yol açar).

    Bu fonksiyon:
      - string ise aynen döndürür,
      - liste ise TÜM metin bloklarını sırayla birleştirir (yalnızca ilkini değil),
      - beklenmedik bir tip gelirse güvenli biçimde str()'e çevirir.
    """
    if isinstance(icerik, str):
        return icerik

    if isinstance(icerik, list):
        parcalar = []
        for blok in icerik:
            if isinstance(blok, dict):
                parcalar.append(blok.get("text", ""))
            else:
                parcalar.append(str(blok))
        return "".join(parcalar).strip()

    return str(icerik)


# ------------------------------------------------------------------
# System prompt'u derleme: persona + kırmızı çizgiler + context
# ------------------------------------------------------------------
def system_prompt_derle(system_message, kirmizi, context):
    """
    persona'nın system_message'ındaki {context} yerine .md bilgisini koyar,
    kırmızı çizgileri de ekler.
    """
    govde = system_message.replace("{context}", context)
    return govde.strip() + "\n\n" + kirmizi.strip()


# ------------------------------------------------------------------
# SESSION (OTURUM) TABANLI HAFIZA DEPOSU
# ------------------------------------------------------------------
# Konuşma geçmişi artık tek bir yerel değişkende değil, session_id'ye
# göre AYRI kutularda tutulur. Böylece aynı anda birden fazla kişi
# (ör. 3 kişi Diyojen ile) konuşsa bile geçmişleri karışmaz.
#
# Yapı:
#   _OTURUMLAR = {
#       "abc123": {"baslik": "...", "mesajlar": [SystemMessage, ...]},
#       "def456": {...},
#   }
#
# Not: Bu depo şu an RAM'dedir (uçucu). Program kapanınca silinir.
# Kalıcılık (SQLite vb.) sonraki aşamaya aittir.

import uuid

_OTURUMLAR = {}


def oturum_ac(baslik, system_prompt, session_id=None):
    """
    Yeni bir sohbet oturumu açar ve session_id döndürür.
    - session_id verilmezse otomatik üretilir (rastgele, benzersiz).
    - Aynı anda açılan her oturum ayrı bir kutuya sahip olur.
    """
    if session_id is None:
        session_id = str(uuid.uuid4())
    _OTURUMLAR[session_id] = {
        "baslik": baslik,
        "mesajlar": [SystemMessage(content=system_prompt)],
    }
    return session_id


def oturum_kapat(session_id):
    """Bir oturumu ve geçmişini bellekten siler ('q' ile çıkışta)."""
    _OTURUMLAR.pop(session_id, None)


def cevap_uret(session_id, kullanici_mesaji):
    """
    ÇEKİRDEK FONKSİYON.
    Verilen session_id'nin geçmişine mesajı ekler, LLM'den yanıt alır,
    yanıtı da geçmişe ekleyip döndürür.

    Bu fonksiyon hem konsol döngüsü hem de (ileride) API tarafından
    çağrılabilir. session_id sayesinde her konuşma kendi geçmişini
    kullanır; başka session'ların geçmişine ASLA dokunmaz.
    """
    if session_id not in _OTURUMLAR:
        raise KeyError(f"Bilinmeyen session_id: {session_id}")

    mesajlar = _OTURUMLAR[session_id]["mesajlar"]
    mesajlar.append(HumanMessage(content=kullanici_mesaji))

    try:
        cevap = _llm().invoke(mesajlar)
        # Model cevabı liste (content block) dönse bile temiz metne çevir.
        # Böylece geçmişe her zaman düz string kaydedilir ve sonraki
        # turlarda model kendi geçmişini sorunsuz okur.
        metin = _icerik_metne(cevap.content)
    except Exception as e:
        mesajlar.pop()  # başarısız mesajı geçmişten çıkar
        raise e

    # Geçmişe bozuk listeyi değil, temizlenmiş düz metni ekliyoruz.
    mesajlar.append(AIMessage(content=metin))
    return metin


# ------------------------------------------------------------------
# Tek bir karakterle sohbet döngüsü (while True) — KONSOL için
# ------------------------------------------------------------------
def sohbet_dongusu(baslik, system_prompt, karsilama=None):
    """
    Seçilen karakterle terminalde sohbet eder.
    - Kendi session_id'sini açar; hafızayı merkezi depoda tutar.
    - Kullanıcı 'q' yazarsa döngüden çıkar ve oturumu kapatır.
    """
    print("\n" + "=" * 60)
    print(f"  {baslik}")
    print("  (Üst menüye dönmek için 'q' yazın)")
    print("=" * 60)

    # Bu konuşmaya özel bir oturum aç
    session_id = oturum_ac(baslik, system_prompt)

    if karsilama:
        print(f"\n{baslik}: {karsilama}\n")

    while True:
        try:
            kullanici = input("Siz: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if kullanici.lower() == "q":
            break
        if not kullanici:
            continue

        try:
            metin = cevap_uret(session_id, kullanici)
        except Exception as e:
            print(f"\n[Hata] Yanıt alınamadı: {e}\n")
            continue

        print(f"\n{baslik}: {metin}\n")

    # Konuşma bitti: oturumu bellekten temizle
    oturum_kapat(session_id)


# ------------------------------------------------------------------
# Kolaylaştırıcı: kaynak + persona verince doğrudan sohbete sokar
# ------------------------------------------------------------------
def karakterle_sohbet(baslik, kategori, persona_adi, alt_klasor, dosya_adi,
                      karsilama=None):
    """
    Tek satırda: personayı ve .md kaynağı yükle, system prompt'u derle,
    sohbet döngüsünü başlat.
    """
    system_message, kirmizi = persona_getir(kategori, persona_adi)
    context = kaynak_oku(alt_klasor, dosya_adi)
    system_prompt = system_prompt_derle(system_message, kirmizi, context)
    sohbet_dongusu(baslik, system_prompt, karsilama)


# ------------------------------------------------------------------
# API/DIŞ KULLANIM İÇİN KOLAYLAŞTIRICI (ileride FastAPI çağıracak)
# ------------------------------------------------------------------
def oturum_baslat(kategori, persona_adi, alt_klasor, dosya_adi, baslik=None):
    """
    Konsol döngüsü OLMADAN bir oturum açar ve session_id döndürür.
    İleride API şunu yapacak:
        sid = oturum_baslat("kisiler","filozof_diyojen","kisiler","diyojen")
        cevap = cevap_uret(sid, "merhaba")
        cevap = cevap_uret(sid, "adım Kadir")   # aynı sid -> aynı geçmiş
    """
    system_message, kirmizi = persona_getir(kategori, persona_adi)
    context = kaynak_oku(alt_klasor, dosya_adi)
    system_prompt = system_prompt_derle(system_message, kirmizi, context)
    return oturum_ac(baslik or persona_adi, system_prompt)