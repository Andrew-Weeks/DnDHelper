import requests

from models import Spell, db

OPEN5E_SPELLS_API = 'https://api.open5e.com/spells/'
SRD_DOCUMENT_SLUGS = ('wotc-srd', '5esrd')


def _parse_level(payload):
    value = payload.get('level_int')
    if isinstance(value, int):
        return value

    raw_level = str(payload.get('level', '')).strip().lower()
    if raw_level in {'cantrip', '0'}:
        return 0

    try:
        return int(raw_level)
    except (TypeError, ValueError):
        return 0


def _as_text(value):
    if value is None:
        return None

    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return ', '.join(cleaned) if cleaned else None

    rendered = str(value).strip()
    return rendered or None


def _map_spell_payload(payload):
    return {
        'name': (payload.get('name') or 'Unknown Spell').strip()[:120],
        'level': _parse_level(payload),
        'school': _as_text(payload.get('school')),
        'casting_time': _as_text(payload.get('casting_time')),
        'spell_range': _as_text(payload.get('range')),
        'components': _as_text(payload.get('components')),
        'material_description': _as_text(payload.get('material')),
        'duration': _as_text(payload.get('duration')),
        'description': (payload.get('desc') or '').strip() or 'No description provided.',
        'higher_level': _as_text(payload.get('higher_level')),
        'class_list': _as_text(payload.get('dnd_class')),
        'source_name': _as_text(payload.get('document__title')) or '5e SRD 2014',
        'external_id': _as_text(payload.get('slug')),
    }


def sync_open5e_srd_spells(timeout_seconds=20, max_pages=200):
    inserted = 0
    updated = 0

    seen_external_ids = set()

    for document_slug in SRD_DOCUMENT_SLUGS:
        next_url = OPEN5E_SPELLS_API
        params = {
            'document__slug': document_slug,
            'limit': 100,
            'ordering': 'name',
        }

        for _ in range(max_pages):
            response = requests.get(next_url, params=params, timeout=timeout_seconds)
            response.raise_for_status()

            payload = response.json()
            results = payload.get('results') or []
            for item in results:
                external_id = item.get('slug')
                if not external_id or external_id in seen_external_ids:
                    continue

                seen_external_ids.add(external_id)
                mapped = _map_spell_payload(item)
                spell = Spell.query.filter_by(source_type='srd', external_id=external_id).first()
                if spell:
                    for field, value in mapped.items():
                        setattr(spell, field, value)
                    updated += 1
                else:
                    db.session.add(Spell(source_type='srd', **mapped))
                    inserted += 1

            next_url = payload.get('next')
            if not next_url:
                break

            # Once we receive a fully-qualified next URL, params are embedded.
            params = None

    db.session.commit()
    return {
        'inserted': inserted,
        'updated': updated,
        'total': inserted + updated,
    }
