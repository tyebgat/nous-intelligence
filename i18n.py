"""Server-side translations for log messages, driven by the app_language setting."""

_LANG = "english"

_STRINGS = {
    "english": {
        "ws_connected": "[WS] Client connected.",
        "ws_disconnected": "[WS] Client disconnected.",
        "crash": "Something really bad happened and the program crashed, check the server terminal for a more detailed error.",
        "chat_received": "[CHAT RECEIVED]: {text}",
        "bot_response": "[BOT RESPONSE]: {text}",
        "chatbot_error": "[CHATBOT ERROR]: {e}",
        "emotion": "[EMOTION]: {emotion}",
        "vts_emotion_error": "[VTS EMOTION ERROR]: {e}",
        "tts_error": "[TTS ERROR]: {e}",
        "vts_neutral_error": "[VTS NEUTRAL ERROR]: {e}",
        "voice_blocked": "[VOICE] Input blocked - AI is still responding.",
        "voice_text": "[VOICE TEXT]: {text}",
        "voice_no_speech": "[VOICE] No speech detected.",
        "voice_input_error": "[VOICE INPUT ERROR]: {e}",
        "voice_stats": "[VOICE] Received {chunks} chunks, {bytes} bytes (~{seconds}s) | Peak {peak}, RMS {rms}",
        "voice_saved": "[VOICE] Saved audio to {path}",
        "voice_no_chunks": "[VOICE] Stop received, but NO audio chunks arrived.",
        "vad_retry": "[VOICE] VAD filtered everything; retrying without VAD...",
        "wake_utterance": "[WAKE] Utterance: {chunks} chunks, {bytes} bytes (~{seconds}s) | Peak {peak}, RMS {rms}",
        "wake_ignored": "[WAKE WORD] Ignored - AI is still responding.",
        "wake_detected": "[WAKE WORD] Detected. Listening...",
        "start_services": "[SERVER] Starting AI Services...",
        "init_chatbot": "[SERVER] Initializing ChatBot ({service})...",
        "chatbot_ok": "[SERVER] ChatBot initialized successfully.",
        "chatbot_fail": "[SERVER ERROR] ChatBot initialization failed: {e}",
        "start_llm": "[SERVER] Starting local LLM server...",
        "llm_ok": "[SERVER] Local LLM server running successfully.",
        "llm_fail": "[SERVER ERROR] Could not start local LLM: {e}",
        "init_tts": "[SERVER] Initializing TTS ({service})...",
        "tts_ok": "[SERVER] TTS Engine ready successfully.",
        "tts_fail": "[SERVER ERROR] TTS initialization failed: {e}",
        "connecting_vts": "[SERVER] Connecting to VTube Studio...",
        "vts_ok": "[SERVER] VTube Studio connected successfully.",
        "vts_fail": "[SERVER ERROR] VTube Studio failed to connect: {e}",
        "init_voice": "[SERVER] Initializing voice input ({service})...",
        "voice_ok": "[SERVER] Voice input ready.",
        "voice_fail": "[SERVER ERROR] Voice input initialization failed: {e}",
        "all_online": "[SERVER] All requested AI services are online.",
        "stopping": "[SERVER] Stopping AI services...",
        "vts_disconnected": "[SERVER] VTube Studio disconnected.",
        "vts_skip_close": "[SERVER] VTS has no close() method, skipping.",
        "vts_error": "[VTS ERROR]: {e}",
        "llm_stopped": "[SERVER] Local LLM server stopped.",
        "local_server_error": "[LOCAL SERVER ERROR]: {e}",
        "voice_stopped": "[SERVER] Voice input stopped.",
        "user_input_error": "[USER INPUT ERROR]: {e}",
        "shut_down": "[SERVER] AI services shut down completely.",
    },
    "spanish": {
        "ws_connected": "[WS] Cliente conectado.",
        "ws_disconnected": "[WS] Cliente desconectado.",
        "crash": "Algo muy malo pasó y el programa falló; revisa la terminal del servidor para ver el error detallado.",
        "chat_received": "[CHAT RECIBIDO]: {text}",
        "bot_response": "[RESPUESTA DEL BOT]: {text}",
        "chatbot_error": "[ERROR CHATBOT]: {e}",
        "emotion": "[EMOCIÓN]: {emotion}",
        "vts_emotion_error": "[ERROR EMOCIÓN VTS]: {e}",
        "tts_error": "[ERROR TTS]: {e}",
        "vts_neutral_error": "[ERROR NEUTRAL VTS]: {e}",
        "voice_blocked": "[VOZ] Entrada bloqueada: la IA sigue respondiendo.",
        "voice_text": "[TEXTO DE VOZ]: {text}",
        "voice_no_speech": "[VOZ] No se detectó voz.",
        "voice_input_error": "[ERROR DE ENTRADA DE VOZ]: {e}",
        "voice_stats": "[VOZ] Recibidos {chunks} fragmentos, {bytes} bytes (~{seconds}s) | Pico {peak}, RMS {rms}",
        "voice_saved": "[VOZ] Audio guardado en {path}",
        "voice_no_chunks": "[VOZ] Stop recibido, pero NO llegó ningún fragmento de audio.",
        "vad_retry": "[VOZ] El VAD filtró todo; reintentando sin VAD...",
        "wake_utterance": "[DESPERTAR] Locución: {chunks} fragmentos, {bytes} bytes (~{seconds}s) | Pico {peak}, RMS {rms}",
        "wake_ignored": "[PALABRA CLAVE] Ignorada: la IA sigue respondiendo.",
        "wake_detected": "[PALABRA CLAVE] Detectada. Escuchando...",
        "start_services": "[SERVIDOR] Iniciando servicios de IA...",
        "init_chatbot": "[SERVIDOR] Inicializando ChatBot ({service})...",
        "chatbot_ok": "[SERVIDOR] ChatBot inicializado correctamente.",
        "chatbot_fail": "[ERROR DEL SERVIDOR] Fallo al inicializar el ChatBot: {e}",
        "start_llm": "[SERVIDOR] Iniciando servidor LLM local...",
        "llm_ok": "[SERVIDOR] Servidor LLM local en ejecución.",
        "llm_fail": "[ERROR DEL SERVIDOR] No se pudo iniciar el LLM local: {e}",
        "init_tts": "[SERVIDOR] Inicializando TTS ({service})...",
        "tts_ok": "[SERVIDOR] Motor de TTS listo correctamente.",
        "tts_fail": "[ERROR DEL SERVIDOR] Fallo al inicializar el TTS: {e}",
        "connecting_vts": "[SERVIDOR] Conectando a VTube Studio...",
        "vts_ok": "[SERVIDOR] VTube Studio conectado correctamente.",
        "vts_fail": "[ERROR DEL SERVIDOR] Fallo al conectar con VTube Studio: {e}",
        "init_voice": "[SERVIDOR] Inicializando entrada de voz ({service})...",
        "voice_ok": "[SERVIDOR] Entrada de voz lista.",
        "voice_fail": "[ERROR DEL SERVIDOR] Fallo al inicializar la entrada de voz: {e}",
        "all_online": "[SERVIDOR] Todos los servicios de IA solicitados están en línea.",
        "stopping": "[SERVIDOR] Deteniendo servicios de IA...",
        "vts_disconnected": "[SERVIDOR] VTube Studio desconectado.",
        "vts_skip_close": "[SERVIDOR] VTS no tiene método close(), omitiendo.",
        "vts_error": "[ERROR VTS]: {e}",
        "llm_stopped": "[SERVIDOR] Servidor LLM local detenido.",
        "local_server_error": "[ERROR SERVIDOR LOCAL]: {e}",
        "voice_stopped": "[SERVIDOR] Entrada de voz detenida.",
        "user_input_error": "[ERROR DE ENTRADA DE USUARIO]: {e}",
        "shut_down": "[SERVIDOR] Servicios de IA apagados por completo.",
    },
}


def set_lang(lang: str) -> None:
    global _LANG
    _LANG = lang if lang in _STRINGS else "english"


def get_lang() -> str:
    return _LANG


def t(key: str, **kwargs) -> str:
    template = _STRINGS.get(_LANG, {}).get(key)
    if template is None:
        template = _STRINGS["english"].get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template
