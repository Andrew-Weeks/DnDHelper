"""
AI analysis pipeline for session transcripts.

Runs four analysis passes against a completed session transcript using the
Claude API (configurable model via ANALYSIS_MODEL app config key).

Analyses:
  summary       — narrative paragraph summary of session events
  ic_ooc        — per-segment in-character vs out-of-character classification
  combat_phases — list of combat encounters with timestamps
  npcs          — extracted NPC names and context

Entry point: analyze_session(app, session_id)
Called from a background thread by the campaign blueprint.
"""

import json
import traceback

import anthropic

ANALYSIS_TYPES = ('summary', 'ic_ooc', 'combat_phases', 'npcs')

_DEFAULT_MODEL = 'claude-haiku-4-5-20251001'

# Approximate token budget before we chunk the transcript.
# Haiku context window is 200k tokens; 60k words ~ 80k tokens, leaving
# room for the system prompt and output.
_CHUNK_WORD_LIMIT = 60_000


def _build_transcript_text(segments):
    """Return a plain-text representation of all transcript segments."""
    lines = []
    for seg in segments:
        speaker = seg.speaker_user.username if seg.speaker_user else seg.speaker_label
        ts = f"{int(seg.start_time) // 60}:{int(seg.start_time) % 60:02d}"
        lines.append(f"[{ts}] {speaker}: {seg.text}")
    return "\n".join(lines)


def _call_claude(client, model, system_prompt, user_content):
    """Single blocking Claude API call. Returns the text response."""
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text


def _run_summary(client, model, transcript_text):
    """
    Returns a dict: {"summary": "<narrative text>"}
    """
    system = (
        "You are a scribe for a tabletop RPG campaign. "
        "Given a session transcript, write a concise narrative summary of the key events. "
        "Write in past tense, 3-6 paragraphs. Focus on story events, decisions made, and notable moments. "
        "Ignore out-of-character chatter, rules discussions, and bathroom breaks. "
        "Respond with a JSON object containing a single key 'summary' whose value is the summary text."
    )
    words = transcript_text.split()
    if len(words) > _CHUNK_WORD_LIMIT:
        # Chunk and summarise each chunk, then reduce
        chunks = []
        chunk_size = _CHUNK_WORD_LIMIT
        for i in range(0, len(words), chunk_size):
            chunk_text = " ".join(words[i:i + chunk_size])
            partial = _call_claude(client, model, system,
                                   f"Summarise this portion of the session transcript:\n\n{chunk_text}")
            try:
                chunks.append(json.loads(partial)["summary"])
            except (json.JSONDecodeError, KeyError):
                chunks.append(partial)
        combined = "\n\n".join(chunks)
        result_text = _call_claude(
            client, model, system,
            f"Here are summaries of consecutive portions of a single session. "
            f"Combine them into one cohesive narrative summary:\n\n{combined}"
        )
    else:
        result_text = _call_claude(client, model, system,
                                   f"Session transcript:\n\n{transcript_text}")
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        return {"summary": result_text}


def _run_ic_ooc(client, model, segments):
    """
    Classifies each segment as in_character, out_of_character, or unknown.
    Returns a dict: {"classifications": {"<segment_id>": "<label>", ...}}
    """
    system = (
        "You are analysing a tabletop RPG session transcript. "
        "Classify each line as one of: 'in_character' (player speaking as their character, "
        "narrative description, in-world dialogue), 'out_of_character' (player speaking as "
        "themselves — rules questions, jokes, real-world chat, dice mechanics discussion), "
        "or 'unknown' (ambiguous). "
        "Respond ONLY with a JSON object: "
        "{\"classifications\": {\"<id>\": \"<label>\", ...}} "
        "where <id> is the segment id integer from the input."
    )
    # Send in batches of 200 segments to stay well under context limits
    batch_size = 200
    all_classifications = {}

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        lines = []
        for seg in batch:
            speaker = seg.speaker_user.username if seg.speaker_user else seg.speaker_label
            lines.append(f'{{"id": {seg.id}, "speaker": "{speaker}", "text": {json.dumps(seg.text)}}}')
        user_content = "Classify these transcript segments:\n[\n" + ",\n".join(lines) + "\n]"
        raw = _call_claude(client, model, system, user_content)
        try:
            batch_result = json.loads(raw)
            all_classifications.update(batch_result.get("classifications", {}))
        except json.JSONDecodeError:
            # Mark the whole batch unknown if parsing fails
            for seg in batch:
                all_classifications[str(seg.id)] = "unknown"

    return {"classifications": all_classifications}


def _run_combat_phases(client, model, transcript_text):
    """
    Returns a dict: {"combat_phases": [{"start": "M:SS", "end": "M:SS", "description": "..."}, ...]}
    """
    system = (
        "You are analysing a tabletop RPG session transcript. "
        "Identify each combat encounter — when it begins and ends based on cues like "
        "'roll for initiative', 'attack', 'damage', 'hit points', 'cast a spell', etc. "
        "Return a JSON object: "
        "{\"combat_phases\": [{\"start\": \"M:SS\", \"end\": \"M:SS\", \"description\": \"brief description\"}, ...]} "
        "If no combat occurs, return {\"combat_phases\": []}. "
        "Use the timestamps from the transcript (format M:SS)."
    )
    words = transcript_text.split()
    if len(words) > _CHUNK_WORD_LIMIT:
        # For very long sessions, pass the first and last portions which capture most combat transitions
        half = _CHUNK_WORD_LIMIT // 2
        truncated = " ".join(words[:half]) + "\n\n[...transcript continues...]\n\n" + " ".join(words[-half:])
        text_to_send = truncated
    else:
        text_to_send = transcript_text

    raw = _call_claude(client, model, system, f"Session transcript:\n\n{text_to_send}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"combat_phases": []}


def _run_npcs(client, model, transcript_text):
    """
    Returns a dict: {"npcs": [{"name": "...", "first_mention": "M:SS", "notes": "..."}, ...]}
    """
    system = (
        "You are analysing a tabletop RPG session transcript. "
        "Extract all Non-Player Characters (NPCs) mentioned — characters spoken to or about "
        "who are not the player characters themselves. "
        "For each NPC provide: their name, the timestamp of their first mention (M:SS format), "
        "and brief notes on what was established about them in this session. "
        "Return a JSON object: "
        "{\"npcs\": [{\"name\": \"...\", \"first_mention\": \"M:SS\", \"notes\": \"...\"}, ...]} "
        "If no NPCs are mentioned, return {\"npcs\": []}."
    )
    words = transcript_text.split()
    if len(words) > _CHUNK_WORD_LIMIT:
        chunks = []
        for i in range(0, len(words), _CHUNK_WORD_LIMIT):
            chunk_text = " ".join(words[i:i + _CHUNK_WORD_LIMIT])
            partial = _call_claude(client, model, system,
                                   f"Extract NPCs from this transcript portion:\n\n{chunk_text}")
            try:
                chunks.append(json.loads(partial).get("npcs", []))
            except json.JSONDecodeError:
                pass
        # Deduplicate by name across chunks
        seen = {}
        for chunk_npcs in chunks:
            for npc in chunk_npcs:
                name = npc.get("name", "").strip().lower()
                if name and name not in seen:
                    seen[name] = npc
        return {"npcs": list(seen.values())}

    raw = _call_claude(client, model, system, f"Session transcript:\n\n{transcript_text}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"npcs": []}


def _run_single_analysis(app, session_id, analysis_type):
    """Run one analysis pass and persist the result."""
    with app.app_context():
        from flask import current_app
        from app.models import db, Session, TranscriptSegment, SessionAnalysis

        analysis = SessionAnalysis.query.filter_by(
            session_id=session_id, analysis_type=analysis_type
        ).first()
        if not analysis:
            return

        try:
            sess = db.session.get(Session, session_id)
            if not sess or sess.status != 'completed':
                raise ValueError("Session transcript not available.")

            segments = (TranscriptSegment.query
                        .filter_by(session_id=session_id)
                        .order_by(TranscriptSegment.start_time)
                        .all())
            if not segments:
                raise ValueError("No transcript segments found.")

            model = current_app.config.get('ANALYSIS_MODEL', _DEFAULT_MODEL)
            api_key = current_app.config.get('ANTHROPIC_API_KEY') or None
            client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

            transcript_text = _build_transcript_text(segments)

            if analysis_type == 'summary':
                result = _run_summary(client, model, transcript_text)

            elif analysis_type == 'ic_ooc':
                result = _run_ic_ooc(client, model, segments)
                # Write context back to each segment
                classifications = result.get("classifications", {})
                for seg in segments:
                    label = classifications.get(str(seg.id))
                    if label in ('in_character', 'out_of_character', 'unknown'):
                        seg.context = label

            elif analysis_type == 'combat_phases':
                result = _run_combat_phases(client, model, transcript_text)

            elif analysis_type == 'npcs':
                result = _run_npcs(client, model, transcript_text)

            else:
                raise ValueError(f"Unknown analysis type: {analysis_type}")

            analysis.result_json = json.dumps(result)
            analysis.status = 'completed'
            analysis.error_message = None
            db.session.commit()

        except Exception:
            db.session.rollback()
            analysis = SessionAnalysis.query.filter_by(
                session_id=session_id, analysis_type=analysis_type
            ).first()
            if analysis:
                analysis.status = 'failed'
                analysis.error_message = traceback.format_exc()
                db.session.commit()


def analyze_session(app, session_id):
    """
    Entry point called from a background thread.
    Creates or resets SessionAnalysis rows for all four types, then
    runs them concurrently in sub-threads.
    """
    import threading

    with app.app_context():
        from app.models import db, SessionAnalysis

        for atype in ANALYSIS_TYPES:
            existing = SessionAnalysis.query.filter_by(
                session_id=session_id, analysis_type=atype
            ).first()
            if existing:
                existing.status = 'processing'
                existing.result_json = None
                existing.error_message = None
            else:
                db.session.add(SessionAnalysis(
                    session_id=session_id,
                    analysis_type=atype,
                    status='processing',
                ))
        db.session.commit()

    threads = []
    for atype in ANALYSIS_TYPES:
        t = threading.Thread(
            target=_run_single_analysis,
            args=(app, session_id, atype),
            daemon=True,
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
