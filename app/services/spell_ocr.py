"""
Spell OCR service — extracts structured spell data from an image
using Claude's vision capability.
"""

import json
import anthropic

_DEFAULT_MODEL = 'claude-haiku-4-5-20251001'

_SYSTEM_PROMPT = """\
You are a D&D spell parser. You will receive an image of a spell (from a book, \
spell card, or similar source). Extract the spell information and return it as \
a JSON object with exactly these keys:

{
  "name": "string — spell name",
  "level": integer 0-9 (0 = cantrip),
  "school": "string — e.g. Evocation, Abjuration",
  "casting_time": "string — e.g. 1 action, 1 bonus action",
  "range": "string — e.g. 60 feet, Self, Touch",
  "components": "string — e.g. V, S, M",
  "material_description": "string or null — material component details if any",
  "duration": "string — e.g. Instantaneous, Concentration up to 1 minute",
  "description": "string — the full spell description text"
}

Rules:
- Return ONLY the JSON object, no markdown fences, no commentary.
- If a field is not visible or not applicable, use null for optional fields.
- "level" must be an integer. Cantrips are level 0.
- For "components", use the standard abbreviation format: "V, S, M" etc.
- Preserve the full description text as faithfully as possible.
"""


def extract_spell_from_image(api_key, model, image_base64, media_type):
    """
    Send an image to Claude Vision and extract structured spell data.

    Returns a dict with spell fields, or raises ValueError on parse failure.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    model = model or _DEFAULT_MODEL

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': media_type,
                            'data': image_base64,
                        },
                    },
                    {
                        'type': 'text',
                        'text': 'Extract the spell information from this image.',
                    },
                ],
            }
        ],
    )

    raw_text = message.content[0].text

    # Strip markdown fences if Claude wraps the JSON despite instructions
    text = raw_text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f'Could not parse spell data from image. Raw: {raw_text[:300]}')

    if not data.get('name'):
        raise ValueError('Could not identify a spell name in the image.')

    if 'level' in data and data['level'] is not None:
        try:
            data['level'] = int(data['level'])
        except (TypeError, ValueError):
            data['level'] = 0

    return data
