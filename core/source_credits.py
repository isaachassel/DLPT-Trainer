"""Source credits for completed assessments, rendered from server-side snapshots."""
from html import escape

from .reading_import import public_url


def source_snapshot(passage):
    if passage.source_type == "synthetic":
        return {}
    return {**passage.provenance, "license": passage.license,
            "source_type": passage.source_type, "passage_id": passage.id, "skill": passage.skill}


def _link(label, url):
    if not url or not public_url(url):
        return escape(label)
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>'


def credits_html(credits):
    if not credits:
        return ""
    skills = {c.get('skill', 'reading') for c in credits.values()}
    label = next(iter(skills)) if len(skills) == 1 else 'assessment'
    rows = [f'<section class="source-credits"><h3>Sources for your {escape(label)}</h3>',
            '<p>These excerpts come from published sources. Questions and explanations '
            'were written for this practice activity. The speakers, publishers, archive, NFLC and DLI do not endorse it.</p>']
    for number, credit in enumerate(credits.values(), 1):
        title = credit.get("source_title", "Source passage")
        url = credit.get("source_original_url", credit.get("source_locator", ""))
        skill = credit.get('skill', 'reading').title()
        rows += [f'<article><h4>{escape(skill)} passage {number}</h4>',
                 f'<p>{_link(title, url)}<br>{escape(credit.get("source_publisher", credit.get("source_creator", "")))} '
                 f'· {escape(credit.get("publication_date", credit.get("source_date", "")))}</p>']
        if credit.get("source_author"):
            rows.append(f'<p>Author: {escape(credit["source_author"])}</p>')
        if credit.get("source_archive_revision_url"):
            rows.append('<p>Archived by ' + _link(credit.get("source_archive_publisher", "Source archive"),
                                               credit["source_archive_revision_url"]) + '.</p>')
        if credit.get('audio_license'):
            rows.append('<p>Audio license: ' + _link(credit['audio_license'], credit.get('audio_license_url', '')) + '</p>')
            rows.append('<p>Published captions: ' + escape(credit.get('caption_author', '')) + ' · ' +
                        _link('Fixed caption revision', credit.get('caption_source_url', '')) + ' · ' +
                        _link(credit.get('caption_license', 'See source'), credit.get('caption_license_url', '')) +
                        '. The joined caption transcript remains under this license.</p>')
        else:
            rows.append('<p>License: ' + _link(credit.get("license", "See source"), credit.get("source_license_url", "")) + '</p>')
        for key in ("selection", "modifications", "source_modifications", "authenticity_notes", "source_archive_notice"):
            if credit.get(key):
                rows.append(f'<p>{escape(credit[key])}</p>')
        if credit.get("source_license_basis"):
            rows.append('<p>' + escape(credit["source_license_basis"]) + ' ' +
                        _link("License evidence", credit.get("source_license_evidence_url", "")) + '</p>')
        rows.append('</article>')
    rows.append('</section>')
    return ''.join(rows)


def assessment_credits(state, bank=None):
    if state.status == "active":
        return ""
    credits = dict(state.source_credits)
    # Backward compatibility for checkpoints saved before attribution snapshots.
    if bank is not None:
        for pid in dict.fromkeys(r.passage_id for r in state.responses):
            if pid not in credits and pid in bank.passages:
                snapshot = source_snapshot(bank.passages[pid])
                if snapshot:
                    credits[pid] = snapshot
    return credits_html(credits)
