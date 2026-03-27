"""
Transcription pipeline: Whisper (speech-to-text) + pyannote.audio (speaker diarization).

Run in a background thread via campaign.py:session_process.
Requires:
  - ffmpeg installed on PATH
  - openai-whisper, pyannote.audio, pydub, torch (pip install)
  - HF_AUTH_TOKEN env var set (HuggingFace token with access to pyannote/speaker-diarization-3.1)
"""

import os
import traceback

# Lazy-loaded models — loaded once on first use and reused
_whisper_model = None
_diarization_pipeline = None


def _get_whisper_model(model_size):
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model(model_size)
    return _whisper_model


def _get_diarization_pipeline(hf_token):
    global _diarization_pipeline
    if _diarization_pipeline is None:
        from pyannote.audio import Pipeline
        _diarization_pipeline = Pipeline.from_pretrained(
            'pyannote/speaker-diarization-3.1',
            use_auth_token=hf_token
        )
    return _diarization_pipeline


def _convert_to_wav(input_path, output_path):
    """Convert audio file to 16kHz mono WAV using pydub."""
    from pydub import AudioSegment
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(output_path, format='wav')


def _align_segments(diarization_segments, whisper_result):
    """
    Align diarization speaker segments with Whisper word-level timestamps.

    diarization_segments: list of (start, end, speaker_label) from pyannote
    whisper_result: dict from whisper.transcribe(..., word_timestamps=True)

    Returns list of dicts: {speaker_label, start_time, end_time, text}
    """
    # Collect all word-level timestamps from Whisper
    all_words = []
    for seg in whisper_result.get('segments', []):
        for word in seg.get('words', []):
            all_words.append({
                'word': word.get('word', ''),
                'start': word.get('start', 0.0),
                'end': word.get('end', 0.0),
            })

    aligned = []
    for (start, end, label) in diarization_segments:
        words_in_range = [
            w['word'] for w in all_words
            if (w['start'] + w['end']) / 2 >= start
            and (w['start'] + w['end']) / 2 < end
        ]
        text = ' '.join(words_in_range).strip()
        if text:
            aligned.append({
                'speaker_label': label,
                'start_time': start,
                'end_time': end,
                'text': text,
            })

    return aligned


def process_session(app, session_id):
    """
    Main pipeline entry point. Called in a background thread.
    Creates an app context, runs transcription + diarization,
    persists TranscriptSegment rows, and updates Session.status.
    """
    with app.app_context():
        from models import db, Session, TranscriptSegment

        sess = db.session.get(Session, session_id)
        if not sess:
            return

        wav_path = None
        try:
            from flask import current_app

            hf_token     = current_app.config.get('HF_AUTH_TOKEN', '')
            model_size   = current_app.config.get('WHISPER_MODEL_SIZE', 'base')
            session_root = current_app.config.get('SESSION_UPLOAD_ROOT')

            audio_path = os.path.join(session_root, str(sess.campaign_id), sess.audio_filename)
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f'Audio file not found: {audio_path}')

            # Step 1: Convert to WAV
            wav_path = audio_path.rsplit('.', 1)[0] + '_processed.wav'
            _convert_to_wav(audio_path, wav_path)

            # Step 2: Speaker diarization
            pipeline = _get_diarization_pipeline(hf_token)
            diarization = pipeline(wav_path)

            diarization_segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                diarization_segments.append((turn.start, turn.end, speaker))

            # Step 3: Whisper transcription with word timestamps
            model = _get_whisper_model(model_size)
            result = model.transcribe(wav_path, word_timestamps=True)

            # Step 4: Align
            aligned = _align_segments(diarization_segments, result)

            # Step 5: Persist
            # Remove any existing segments (re-processing case)
            TranscriptSegment.query.filter_by(session_id=session_id).delete()

            for item in aligned:
                seg = TranscriptSegment(
                    session_id=session_id,
                    speaker_label=item['speaker_label'],
                    start_time=item['start_time'],
                    end_time=item['end_time'],
                    text=item['text'],
                )
                db.session.add(seg)

            sess.status = 'completed'
            sess.error_message = None
            db.session.commit()

        except Exception:
            db.session.rollback()
            sess = db.session.get(Session, session_id)
            if sess:
                sess.status = 'failed'
                sess.error_message = traceback.format_exc()
                db.session.commit()

        finally:
            # Clean up intermediate WAV file
            if wav_path and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
