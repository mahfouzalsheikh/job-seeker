from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path
from typing import Any

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from core.ai import clean_text, generate_json, keywords
from core.models import Application, Artifact, CoverLetter, JobPosting, ProfileFact, Resume, ResumeClaim
from core.services import create_tailored_resume


def _markdown_to_html(markdown: str) -> str:
    lines = []
    in_list = False
    for raw in (markdown or '').splitlines():
        line = raw.strip()
        if line.startswith(('- ', '* ')):
            if not in_list:
                lines.append('<ul>')
                in_list = True
            lines.append(f'<li>{html.escape(line[2:])}</li>')
            continue
        if in_list:
            lines.append('</ul>')
            in_list = False
        if not line:
            continue
        if line.startswith('### '):
            lines.append(f'<h3>{html.escape(line[4:])}</h3>')
        elif line.startswith('## '):
            lines.append(f'<h2>{html.escape(line[3:])}</h2>')
        elif line.startswith('# '):
            lines.append(f'<h1>{html.escape(line[2:])}</h1>')
        else:
            lines.append(f'<p>{html.escape(line)}</p>')
    if in_list:
        lines.append('</ul>')
    return '\n'.join(lines)


def document_html(title: str, markdown: str, *, kind: str) -> str:
    accent = '#177d69' if kind == 'resume' else '#7558d8'
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>
@page {{ size: Letter; margin: 0.55in 0.62in; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; color: #17231f; font: 10.4pt/1.38 Arial, sans-serif; }}
h1 {{ margin: 0 0 8px; font-size: 25pt; letter-spacing: -.7px; }}
h2 {{ margin: 16px 0 7px; padding-bottom: 4px; color: {accent}; border-bottom: 1px solid #cbd7d2; font-size: 12pt; text-transform: uppercase; letter-spacing: .7px; }}
h3 {{ margin: 11px 0 4px; font-size: 10.8pt; }}
p {{ margin: 0 0 7px; }}
ul {{ margin: 4px 0 10px; padding-left: 18px; }}
li {{ margin-bottom: 4px; }}
a {{ color: {accent}; }}
</style></head><body>{_markdown_to_html(markdown)}</body></html>'''


def _cover_letter_result(job: JobPosting, facts: list[ProfileFact]) -> dict[str, Any]:
    evidence = '\n'.join(f'- {fact.title}: {fact.statement}' for fact in facts[:60])
    schema = {
        'name': 'cover_letter_draft',
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'content_markdown': {'type': 'string'},
                'evidence_fact_ids': {'type': 'array', 'items': {'type': 'integer'}},
                'unsupported_claims': {'type': 'array', 'items': {'type': 'string'}},
                'risk_notes': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['content_markdown', 'evidence_fact_ids', 'unsupported_claims', 'risk_notes'],
        },
    }
    generated = generate_json(
        'Write a concise, specific cover letter using only supplied evidence. Never invent facts. Return 250-350 words without addresses or generic filler.',
        f'Job: {job.title} at {job.company}\n\nPosting:\n{job.description_text[:10000]}\n\nCandidate evidence:\n{evidence[:10000]}',
        schema,
    )
    if generated:
        return generated.data
    strongest = facts[:4]
    proof = ' '.join(fact.statement for fact in strongest[:2])
    content = (
        f'# {job.title} — Cover Letter\n\n'
        f'Dear {job.company or "Hiring"} team,\n\n'
        f'I am interested in the {job.title} opportunity because it closely matches the work I want to continue doing. {proof}\n\n'
        f'The role’s emphasis on {", ".join(detect_job_themes(job)[:4]) or "thoughtful execution and collaboration"} is especially relevant to my background. '
        'I would welcome the chance to discuss how that experience can support your team’s priorities.\n\n'
        'Thank you for your consideration.\n'
    )
    return {
        'content_markdown': content,
        'evidence_fact_ids': [fact.id for fact in strongest],
        'unsupported_claims': [],
        'risk_notes': ['Deterministic fallback draft: review tone and specificity before approval.'],
    }


def detect_job_themes(job: JobPosting) -> list[str]:
    extracted = job.extracted_json or {}
    themes = list(extracted.get('required_skills', [])) + keywords(job.description_text, limit=12)
    return list(dict.fromkeys(clean_text(value) for value in themes if clean_text(value)))[:8]


def validate_resume_claims(resume: Resume, facts: list[ProfileFact]) -> dict[str, Any]:
    ResumeClaim.objects.filter(resume=resume).delete()
    fact_terms = [(fact, set(keywords(f'{fact.title} {fact.statement}', limit=80))) for fact in facts]
    unsupported = []
    for raw in resume.content_markdown.splitlines():
        line = clean_text(raw.lstrip('-* '))
        if len(line) < 24 or raw.lstrip().startswith('#'):
            continue
        claim_terms = set(keywords(line, limit=60))
        best_fact = None
        best_overlap = 0
        for fact, terms in fact_terms:
            overlap = len(claim_terms & terms)
            if overlap > best_overlap:
                best_fact, best_overlap = fact, overlap
        supported = bool(best_fact and best_overlap >= 2)
        ResumeClaim.objects.create(
            owner=resume.owner,
            resume=resume,
            text=line,
            profile_fact=best_fact if supported else None,
            support_status='supported' if supported else 'unsupported',
        )
        if not supported:
            unsupported.append(line)
    validation = dict(resume.validation or {})
    validation['unsupported_claims'] = list(dict.fromkeys(validation.get('unsupported_claims', []) + unsupported))
    validation['claim_count'] = resume.claims.count()
    validation['supported_claim_count'] = resume.claims.exclude(support_status='unsupported').count()
    resume.validation = validation
    resume.save(update_fields=['validation', 'updated_at'])
    return validation


@transaction.atomic
def prepare_application_materials(owner, job: JobPosting, *, application: Application | None = None) -> dict[str, Any]:
    facts = list(ProfileFact.objects.filter(owner=owner).order_by('-verified_by_user', 'fact_type', 'title')[:160])
    resume = create_tailored_resume(owner, job=job)
    validate_resume_claims(resume, facts)
    result = _cover_letter_result(job, facts)
    version = (CoverLetter.objects.filter(owner=owner, target_job=job).order_by('-version').values_list('version', flat=True).first() or 0) + 1
    cover_letter = CoverLetter.objects.create(
        owner=owner,
        target_job=job,
        title=f'{job.title} at {job.company or "Company"} — Cover Letter',
        content_markdown=result['content_markdown'],
        content_json={'evidence_fact_ids': result.get('evidence_fact_ids', [])},
        validation={
            'unsupported_claims': result.get('unsupported_claims', []),
            'risk_notes': result.get('risk_notes', []),
        },
        version=version,
    )
    if application:
        application.resume = resume
        application.status = 'materials_ready'
        application.save(update_fields=['resume', 'status', 'updated_at'])
    return {'resume': resume, 'cover_letter': cover_letter}


def _store_artifact(*, owner, title: str, kind: str, content: bytes, filename: str, mime_type: str, application=None, resume=None, cover_letter=None, metadata=None) -> Artifact:
    digest = hashlib.sha256(content).hexdigest()
    artifact = Artifact.objects.create(
        owner=owner,
        application=application,
        resume=resume,
        cover_letter=cover_letter,
        kind=kind,
        title=title,
        content_hash=digest,
        mime_type=mime_type,
        metadata=metadata or {},
    )
    artifact.file.save(filename, ContentFile(content), save=True)
    return artifact


def render_pdf(*, owner, title: str, markdown: str, kind: str, application=None, resume=None, cover_letter=None) -> Artifact:
    rendered_html = document_html(title, markdown, kind=kind)
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80] or kind
    gotenberg_url = getattr(settings, 'GOTENBERG_URL', '').rstrip('/')
    if gotenberg_url:
        try:
            response = requests.post(
                f'{gotenberg_url}/forms/chromium/convert/html',
                files={'files': ('index.html', rendered_html.encode('utf-8'), 'text/html')},
                data={'printBackground': 'true', 'preferCssPageSize': 'true'},
                timeout=int(getattr(settings, 'GOTENBERG_TIMEOUT_SECONDS', 45)),
            )
            response.raise_for_status()
            return _store_artifact(
                owner=owner, title=title, kind=f'{kind}_pdf', content=response.content,
                filename=f'{slug}.pdf', mime_type='application/pdf', application=application,
                resume=resume, cover_letter=cover_letter, metadata={'renderer': 'gotenberg'},
            )
        except requests.RequestException as exc:
            render_error = str(exc)[:500]
    else:
        render_error = 'Gotenberg is not configured.'
    return _store_artifact(
        owner=owner, title=f'{title} (HTML preview)', kind=f'{kind}_html',
        content=rendered_html.encode('utf-8'), filename=f'{slug}.html', mime_type='text/html',
        application=application, resume=resume, cover_letter=cover_letter,
        metadata={'renderer': 'html-fallback', 'render_error': render_error},
    )


def render_application_bundle(owner, *, application: Application) -> list[Artifact]:
    if not application.resume:
        raise ValueError('Prepare application materials before rendering.')
    cover_letter = CoverLetter.objects.filter(owner=owner, target_job=application.job).order_by('-version').first()
    artifacts = [render_pdf(
        owner=owner,
        title=application.resume.title,
        markdown=application.resume.content_markdown,
        kind='resume',
        application=application,
        resume=application.resume,
    )]
    if cover_letter:
        artifacts.append(render_pdf(
            owner=owner,
            title=cover_letter.title,
            markdown=cover_letter.content_markdown,
            kind='cover_letter',
            application=application,
            cover_letter=cover_letter,
        ))
    return artifacts

