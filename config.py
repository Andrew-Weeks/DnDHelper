import os


class Config:
    SECRET_KEY = 'change-me-to-a-random-secret-before-deploying'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dndhelper.db'

    # Optional: require this passphrase when registering as DM.
    # Set to None to allow anyone to register as DM.
    DM_SECRET = 'dungeon-master'

    # Optional: require this passphrase when registering as a Developer.
    # Set to None to allow anyone to register as Developer.
    DEV_SECRET = 'developer-mode'

    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB (session recordings can be large)

    # Transcription settings — set via environment variables before running
    WHISPER_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'base')
    HF_AUTH_TOKEN = os.environ.get('HF_AUTH_TOKEN', '')

    # Analysis settings (Claude API)
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    ANALYSIS_MODEL = os.environ.get('ANALYSIS_MODEL', 'claude-haiku-4-5-20251001')
    DIARIZATION_USE_CAMPAIGN_HINT = os.environ.get('DIARIZATION_USE_CAMPAIGN_HINT', '1').lower() in ('1', 'true', 'yes', 'on')
    DIARIZATION_SPEAKER_SLACK = int(os.environ.get('DIARIZATION_SPEAKER_SLACK', '1'))
    DIARIZATION_MAX_SPEAKERS_CAP = int(os.environ.get('DIARIZATION_MAX_SPEAKERS_CAP', '10'))
