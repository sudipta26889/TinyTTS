import os

class Config:
    LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
    LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")
    TTS_MODEL = os.getenv("TTS_MODEL", "tts-kokoro")
    DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "af_alloy")
    DEFAULT_SPEED = float(os.getenv("DEFAULT_SPEED", "1.0"))
    MAX_STORAGE_GB = float(os.getenv("MAX_STORAGE_GB", "10"))
    INITIAL_CHUNK_SIZE = int(os.getenv("INITIAL_CHUNK_SIZE", "4000"))
    MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "500"))
    LARGE_INPUT_WARNING = int(os.getenv("LARGE_INPUT_WARNING", "100000"))
    DATA_DIR = os.getenv("DATA_DIR", "/data")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "4040"))

    # Kokoro TTS voice names (prefixed: af=American Female, am=American Male, bf=British Female, bm=British Male)
    VOICES = ["af_alloy", "af_nova", "af_bella", "af_sarah", "af_sky", "am_echo", "am_onyx", "am_adam", "bm_fable", "bm_george"]
    SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]
