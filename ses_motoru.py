# -*- coding: utf-8 -*-
"""
ses_motoru.py
-------------
Bas-Konuş (Push-to-Talk) sesli sohbet için ses -> metin (STT) dönüşümü.

ÖNEMLİ MİMARİ NOT: Bu modül, sohbet cevabını üreten LLM sağlayıcısından
(bot_engine.py'deki SAGLAYICI — şu an Gemini) TAMAMEN BAĞIMSIZDIR. STT
işlemi HER ZAMAN Groq'un Whisper uç noktası üzerinden yapılır (hız ve
ücretsiz katman avantajı için); sohbet cevabının hangi sağlayıcıdan
üretildiğiyle hiçbir ilgisi yoktur. Yani "sohbet Gemini kullanıyor" ile
"STT Groq kullanıyor" aynı anda, çelişkisiz bir arada durur.

Bu modül SADECE ses -> metin çevirir; hafıza/oturum/prompt mantığına
DOKUNMAZ. Çevrilen metin, api.py tarafından mevcut bot_engine.cevap_uret()
fonksiyonuna aynen /sohbet'teki gibi iletilir — bu sayede sesli ve yazılı
mesajlar aynı oturumda karışmadan, aynı hafızada birikir.
"""

import os
from groq import Groq

# whisper-large-v3-turbo: hızlı + çok dilli + ucuz (varsayılan).
# Daha yüksek doğruluk gerekirse "whisper-large-v3" ile değiştirilebilir.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo")

_groq_client = None


def _client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY tanımlı değil. Sesli sohbet (STT) için Groq "
                "anahtarı gereklidir; .env dosyanıza ekleyin."
            )
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def ses_metne_cevir(ses_bytes: bytes, dosya_adi: str = "ses.webm") -> str:
    """
    Ses baytlarını Groq Whisper ile Türkçe metne çevirir.
    Boş/sessiz kayıtlarda boş string döner (çağıran taraf bunu
    "sizi anlayamadım" gibi bir kullanıcı mesajına çevirmelidir).
    """
    if not ses_bytes:
        return ""

    try:
        yanit = _client().audio.transcriptions.create(
            file=(dosya_adi or "ses.webm", ses_bytes),
            model=WHISPER_MODEL,
            language="tr",
            response_format="json",
            temperature=0.0,
        )
        return (yanit.text or "").strip()
    except Exception as e:
        raise RuntimeError(f"Ses metne çevrilemedi: {e}")
