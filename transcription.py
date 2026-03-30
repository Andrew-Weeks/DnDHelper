"""
Transcription pipeline: Whisper (speech-to-text) + pyannote.audio (speaker diarization).

Run in a background thread via campaign.py:session_process.
Requires:
  - ffmpeg installed on PATH
  - openai-whisper, pyannote.audio, pydub, torch (pip install)
  - HF_AUTH_TOKEN env var set (HuggingFace token with access to pyannote/speaker-diarization-3.1)
"""

import os
import shutil
import subprocess
import traceback

# Lazy-loaded models — loaded once on first use and reused
_whisper_model = None
_diarization_pipeline = None


def _find_first_file(root_dir, filename):
    """Return first matching filename under root_dir, or None."""
    if not root_dir or not os.path.isdir(root_dir):
        return None

    for current_root, _, files in os.walk(root_dir):
        if filename in files:
            return os.path.join(current_root, filename)
    return None


def _resolve_ffmpeg_tools():
    """Resolve ffmpeg/ffprobe executable paths from PATH or common Windows locations."""
    ffmpeg_path = shutil.which('ffmpeg')
    ffprobe_path = shutil.which('ffprobe')

    if ffmpeg_path and ffprobe_path:
        return ffmpeg_path, ffprobe_path

    # Windows fallback for winget installs when PATH hasn't refreshed in this process.
    if os.name == 'nt':
        local_app_data = os.environ.get('LOCALAPPDATA', '')
        winget_links = os.path.join(local_app_data, 'Microsoft', 'WinGet', 'Links')
        winget_packages = os.path.join(local_app_data, 'Microsoft', 'WinGet', 'Packages')

        if not ffmpeg_path:
            ffmpeg_path = os.path.join(winget_links, 'ffmpeg.exe')
            if not os.path.isfile(ffmpeg_path):
                ffmpeg_path = _find_first_file(winget_packages, 'ffmpeg.exe')

        if not ffprobe_path:
            ffprobe_path = os.path.join(winget_links, 'ffprobe.exe')
            if not os.path.isfile(ffprobe_path):
                ffprobe_path = _find_first_file(winget_packages, 'ffprobe.exe')

    if ffmpeg_path and ffprobe_path and os.path.isfile(ffmpeg_path) and os.path.isfile(ffprobe_path):
        return ffmpeg_path, ffprobe_path

    return None, None


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
            token=hf_token
        )
    return _diarization_pipeline


def _convert_to_wav(input_path, output_path):
    """Convert audio file to 16kHz mono WAV using ffmpeg."""
    ffmpeg_path, _ffprobe_path = _resolve_ffmpeg_tools()
    if not ffmpeg_path:
        raise RuntimeError(
            'Missing ffmpeg on PATH. Install ffmpeg '
            'and restart the app. On Windows: "winget install Gyan.FFmpeg".'
        )

    command = [
        ffmpeg_path,
        '-y',
        '-i', input_path,
        '-ac', '1',
        '-ar', '16000',
        output_path,
    ]

    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise RuntimeError(
            'Audio conversion failed because ffmpeg was not found. '
            'Install ffmpeg and restart the app.'
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b'').decode('utf-8', errors='replace').strip()
        short_err = stderr[-1200:] if stderr else 'Unknown ffmpeg error.'
        raise RuntimeError(f'Audio conversion failed: {short_err}') from exc


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


def _normalize_speaker_labels(diarization_segments):
    """
    Renumber speaker labels by first appearance time for stable UI labeling.

    Example: arbitrary model labels like SPEAKER_03/SPEAKER_00 become
    SPEAKER_00/SPEAKER_01 in timeline order.
    """
    # Ensure deterministic order even if upstream iterator order changes.
    ordered = sorted(diarization_segments, key=lambda item: (item[0], item[1], item[2]))
    label_map = {}
    next_index = 0

    normalized = []
    for start, end, label in ordered:
        if label not in label_map:
            label_map[label] = f'SPEAKER_{next_index:02d}'
            next_index += 1
        normalized.append((start, end, label_map[label]))

    return normalized


def process_session(app, session_id):
    """
    Main pipeline entry point. Called in a background thread.
    Creates an app context, runs transcription + diarization,
    persists TranscriptSegment rows, and updates Session.status.
    """
    with app.app_context():
        from models import db, Session, TranscriptSegment, CampaignMember

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
            # Pre-load the WAV with scipy to bypass torchaudio/torchcodec backend
            # failures on Windows (torchcodec DLL load error).
            import numpy as _np
            import scipy.io.wavfile as _scipy_wav
            import torch as _torch

            _sr, _wav_data = _scipy_wav.read(wav_path)
            if _wav_data.dtype == _np.int16:
                _wf_np = _wav_data.astype(_np.float32) / 32768.0
            elif _wav_data.dtype == _np.int32:
                _wf_np = _wav_data.astype(_np.float32) / 2147483648.0
            elif _wav_data.dtype == _np.uint8:
                _wf_np = (_wav_data.astype(_np.float32) - 128.0) / 128.0
            else:
                _wf_np = _wav_data.astype(_np.float32)
            # pyannote expects shape [channels, samples]
            _waveform = _torch.from_numpy(_wf_np).unsqueeze(0)
            audio_input = {'waveform': _waveform, 'sample_rate': _sr}

            pipeline = _get_diarization_pipeline(hf_token)

            # Hint diarization with expected campaign speaker count to reduce
            # under-clustering (multiple people grouped into one label).
            diarization_kwargs = {}
            use_campaign_hint = bool(current_app.config.get('DIARIZATION_USE_CAMPAIGN_HINT', True))
            if use_campaign_hint:
                expected_speakers = 1 + CampaignMember.query.filter_by(campaign_id=sess.campaign_id).count()
                speaker_slack = max(0, int(current_app.config.get('DIARIZATION_SPEAKER_SLACK', 1)))
                speaker_cap = max(1, int(current_app.config.get('DIARIZATION_MAX_SPEAKERS_CAP', 10)))

                max_speakers = min(expected_speakers, speaker_cap)
                min_speakers = max(1, min(max_speakers, expected_speakers - speaker_slack))

                if min_speakers <= max_speakers and max_speakers > 1:
                    diarization_kwargs['min_speakers'] = min_speakers
                    diarization_kwargs['max_speakers'] = max_speakers

            try:
                diarization = pipeline(audio_input, **diarization_kwargs) if diarization_kwargs else pipeline(audio_input)
            except TypeError:
                # Older/newer pipeline signatures may reject kwargs; fall back.
                diarization = pipeline(audio_input)

            diarization_segments = []
            # pyannote.audio 4.x returns DiarizeOutput; the Annotation is in .speaker_diarization
            annotation = diarization.speaker_diarization if hasattr(diarization, 'speaker_diarization') else diarization
            for turn, _, speaker in annotation.itertracks(yield_label=True):
                diarization_segments.append((turn.start, turn.end, speaker))

            diarization_segments = _normalize_speaker_labels(diarization_segments)

            # Step 3: Whisper transcription with word timestamps
            # Step 3: Whisper transcription with word timestamps
            # Pass a torch.Tensor so Whisper skips its internal ffmpeg load_audio call
            # (ffmpeg may not be on PATH in the running process on Windows).
            model = _get_whisper_model(model_size)
            result = model.transcribe(_torch.from_numpy(_wf_np), word_timestamps=True)

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
