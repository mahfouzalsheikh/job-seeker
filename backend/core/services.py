from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .ai import (
    chunk_text,
    clean_text,
    cosine_similarity,
    detect_skills,
    embed_text,
    extract_job,
    extract_profile_facts,
    keywords,
    stable_hash,
    tailor_resume,
)
from .models import (
    Application,
    Artifact,
    JobMatch,
    JobPosting,
    ProfileChunk,
    ProfileDocument,
    ProfileFact,
    Resume,
)


def extract_text_from_upload(path: str) -> str:
    lowered = path.lower()
    try:
        if lowered.endswith('.pdf'):
            from pypdf import PdfReader

            reader = PdfReader(path)
            return '\n\n'.join(page.extract_text() or '' for page in reader.pages)
        if lowered.endswith('.docx'):
            from docx import Document

            doc = Document(path)
            return '\n'.join(paragraph.text for paragraph in doc.paragraphs)
        with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
            return handle.read()
    except Exception as exc:
        raise ValueError(f'Could not extract text from upload: {exc}') from exc


@transaction.atomic
def ingest_profile_document(document: ProfileDocument) -> dict[str, Any]:
    document.status = 'processing'
    document.status_message = 'Extracting profile facts'
    document.save(update_fields=['status', 'status_message', 'updated_at'])

    text = document.raw_text
    if document.upload and not text:
        text = extract_text_from_upload(document.upload.path)
        document.raw_text = text
        document.save(update_fields=['raw_text', 'updated_at'])

    cleaned = clean_text(text)
    if not cleaned:
        document.status = 'failed'
        document.status_message = 'No text was found in the document.'
        document.save(update_fields=['status', 'status_message', 'updated_at'])
        return {'created_facts': 0, 'created_chunks': 0}

    ProfileChunk.objects.filter(document=document).delete()
    chunks = []
    for index, chunk in enumerate(chunk_text(text)):
        chunks.append(ProfileChunk.objects.create(
            owner=document.owner,
            document=document,
            text=chunk,
            token_count=max(1, len(chunk.split())),
            embedding=embed_text(chunk),
            metadata={'index': index},
        ))

    extracted = extract_profile_facts(text, title=document.title)
    existing_keys = set(
        ProfileFact.objects.filter(owner=document.owner)
        .values_list('fact_type', 'title', 'statement')
    )
    created = 0
    for raw_fact in extracted.data.get('facts', []):
        statement = clean_text(raw_fact.get('statement', ''))
        title = clean_text(raw_fact.get('title', ''))[:220] or statement[:80] or 'Profile fact'
        fact_type = clean_text(raw_fact.get('fact_type', 'achievement')).lower().replace(' ', '_')
        if fact_type not in {choice[0] for choice in ProfileFact.FACT_CHOICES}:
            fact_type = 'achievement'
        key = (fact_type, title, statement)
        if not statement or key in existing_keys:
            continue
        source_chunk = chunks[0] if chunks else None
        ProfileFact.objects.create(
            owner=document.owner,
            fact_type=fact_type,
            title=title,
            statement=statement,
            confidence=clean_text(raw_fact.get('confidence', 'medium'))[:24] or 'medium',
            source_document=document,
            source_chunk=source_chunk,
            embedding=embed_text(f'{title}\n{statement}'),
            metadata={'extractor': extracted.source},
        )
        existing_keys.add(key)
        created += 1

    document.status = 'ready'
    document.status_message = f'Created {created} facts from {len(chunks)} chunks.'
    document.metadata = {**(document.metadata or {}), 'extractor': extracted.source}
    document.save(update_fields=['status', 'status_message', 'metadata', 'updated_at'])

    if document.kind == 'resume':
        ensure_canonical_resume(document)

    return {'created_facts': created, 'created_chunks': len(chunks)}


def ensure_canonical_resume(document: ProfileDocument) -> Resume:
    existing = Resume.objects.filter(owner=document.owner, kind='canonical').order_by('-updated_at').first()
    title = 'Canonical Resume'
    content = document.raw_text.strip()
    if existing:
        existing.title = title
        existing.content_markdown = content
        existing.content_json = {'source_document_id': document.id}
        existing.save(update_fields=['title', 'content_markdown', 'content_json', 'updated_at'])
        return existing
    return Resume.objects.create(
        owner=document.owner,
        kind='canonical',
        title=title,
        content_markdown=content,
        content_json={'source_document_id': document.id},
    )


@transaction.atomic
def import_job_posting(owner, *, text: str, source_url: str = '', source=None) -> JobPosting:
    extracted = extract_job(text, source_url=source_url)
    data = extracted.data
    content_hash = stable_hash(f'{owner.pk}:{source_url}:{text}')
    defaults = {
        'source': source,
        'title': clean_text(data.get('title'))[:240] or 'Imported Job',
        'company': clean_text(data.get('company'))[:220],
        'location': clean_text(data.get('location'))[:220],
        'remote_policy': normalize_remote_policy(data.get('remote_policy')),
        'seniority': clean_text(data.get('seniority'))[:120],
        'compensation': clean_text(data.get('compensation'))[:160],
        'description_text': text,
        'extracted_json': {**data, 'extractor': extracted.source},
        'source_url': source_url,
        'application_url': clean_text(data.get('application_url'))[:1000] or source_url,
        'embedding': embed_text(text),
    }
    job, _ = JobPosting.objects.update_or_create(
        owner=owner,
        content_hash=content_hash,
        defaults=defaults,
    )
    recompute_match(job)
    return job


def normalize_remote_policy(value: Any) -> str:
    lowered = clean_text(value).lower()
    if 'remote' in lowered:
        return 'remote'
    if 'hybrid' in lowered:
        return 'hybrid'
    if 'site' in lowered or 'office' in lowered:
        return 'onsite'
    return 'unknown'


def recompute_match(job: JobPosting) -> JobMatch:
    facts = list(ProfileFact.objects.filter(owner=job.owner).order_by('-verified_by_user', 'fact_type', 'title')[:200])
    fact_text = '\n'.join(f'{fact.title}: {fact.statement}' for fact in facts)
    fact_embedding = embed_text(fact_text) if fact_text else []
    job_embedding = job.embedding or embed_text(job.description_text)
    if not job.embedding:
        job.embedding = job_embedding
        job.save(update_fields=['embedding', 'updated_at'])

    semantic = (cosine_similarity(fact_embedding, job_embedding) + 1) / 2 if fact_text else 0
    job_skills = detect_skills(job.description_text)
    profile_text = fact_text.lower()
    covered = [skill for skill in job_skills if skill.lower() in profile_text]
    missing = [skill for skill in job_skills if skill not in covered]
    skill_score = len(covered) / max(1, len(job_skills))

    job_terms = set(keywords(job.description_text, limit=120))
    profile_terms = set(keywords(fact_text, limit=500))
    lexical = len(job_terms & profile_terms) / max(1, len(job_terms))

    score = round((semantic * 35) + (skill_score * 45) + (lexical * 20))
    if job.remote_policy == 'remote':
        score = min(100, score + 3)
    score = max(0, min(100, score))

    supporting = []
    for fact in facts:
        fact_blob = f'{fact.title} {fact.statement}'.lower()
        overlap = [skill for skill in covered if skill.lower() in fact_blob]
        if not overlap:
            continue
        supporting.append({
            'fact_id': fact.id,
            'title': fact.title,
            'statement': fact.statement,
            'skills': overlap,
        })
        if len(supporting) >= 8:
            break

    confidence = 'high' if score >= 80 else 'medium' if score >= 55 else 'low'
    explanation = {
        'semantic_score': round(semantic, 3),
        'skill_score': round(skill_score, 3),
        'lexical_score': round(lexical, 3),
        'covered_skills': covered,
        'job_skills': job_skills,
        'summary': build_match_summary(score, covered, missing),
    }
    match, _ = JobMatch.objects.update_or_create(
        owner=job.owner,
        job=job,
        defaults={
            'score': score,
            'hard_filter_status': 'pass',
            'explanation_json': explanation,
            'missing_requirements': missing,
            'supporting_facts': supporting,
            'confidence': confidence,
        },
    )
    return match


def build_match_summary(score: int, covered: list[str], missing: list[str]) -> str:
    if score >= 80:
        prefix = 'Strong match'
    elif score >= 55:
        prefix = 'Possible match'
    else:
        prefix = 'Weak match'
    coverage = f'{len(covered)} covered skills'
    gap = f'{len(missing)} visible gaps' if missing else 'no obvious skill gaps'
    return f'{prefix}: {coverage}, {gap}.'


def create_tailored_resume(owner, *, job: JobPosting, canonical: Resume | None = None) -> Resume:
    if canonical is None:
        canonical = Resume.objects.filter(owner=owner, kind='canonical').order_by('-updated_at').first()
    if canonical is None:
        canonical = Resume.objects.create(
            owner=owner,
            kind='canonical',
            title='Canonical Resume',
            content_markdown='',
            content_json={},
        )
    facts = list(ProfileFact.objects.filter(owner=owner).order_by('-verified_by_user', 'fact_type', 'title')[:120])
    result = tailor_resume(
        canonical_markdown=canonical.content_markdown,
        job_title=job.title,
        job_text=job.description_text,
        facts=[{
            'id': fact.id,
            'title': fact.title,
            'statement': fact.statement,
            'verified_by_user': fact.verified_by_user,
        } for fact in facts],
    )
    validation = {
        'generator': result.source,
        'summary_changes': result.data.get('summary_changes', []),
        'keyword_coverage': result.data.get('keyword_coverage', []),
        'unsupported_claims': result.data.get('unsupported_claims', []),
        'weak_claims': result.data.get('weak_claims', []),
        'evidence_links': result.data.get('evidence_links', []),
        'risk_notes': result.data.get('risk_notes', []),
    }
    return Resume.objects.create(
        owner=owner,
        kind='tailored',
        title=clean_text(result.data.get('title'))[:220] or f'{job.title} Tailored Resume',
        content_markdown=result.data.get('content_markdown', canonical.content_markdown),
        content_json={'target_job_id': job.id},
        parent_resume=canonical,
        target_job=job,
        validation=validation,
    )


def generate_strategy(owner) -> dict[str, Any]:
    apps = Application.objects.filter(owner=owner)
    total = apps.count()
    by_status = dict(apps.values_list('status').annotate(count=Count('id')).values_list('status', 'count'))
    interviews = sum(by_status.get(status, 0) for status in ['recruiter_screen', 'technical_screen', 'onsite_final', 'offer'])
    applied = by_status.get('applied', 0) + interviews + by_status.get('rejected', 0)
    response_rate = round((interviews / applied) * 100, 1) if applied else 0
    followups_due = apps.filter(
        follow_up_at__lte=timezone.now(),
    ).exclude(status__in=['rejected', 'archived', 'offer']).count()
    top_matches = JobMatch.objects.filter(owner=owner).select_related('job').order_by('-score')[:5]

    recommendations = []
    if top_matches:
        best = top_matches[0]
        recommendations.append({
            'title': f'Prioritize {best.job.title}',
            'detail': f'This is currently the highest-scoring match at {best.score}.',
        })
    if followups_due:
        recommendations.append({
            'title': f'Follow up on {followups_due} application{"s" if followups_due != 1 else ""}',
            'detail': 'These applications have follow-up dates due or overdue.',
        })
    weak_facts = ProfileFact.objects.filter(owner=owner, verified_by_user=False).count()
    if weak_facts:
        recommendations.append({
            'title': 'Verify profile facts',
            'detail': f'{weak_facts} extracted facts are unverified and may limit resume confidence.',
        })
    if not recommendations:
        recommendations.append({
            'title': 'Import more jobs',
            'detail': 'Add job descriptions to improve matching and strategy feedback.',
        })

    return {
        'totals': {
            'applications': total,
            'applied': applied,
            'interviews': interviews,
            'response_rate': response_rate,
            'followups_due': followups_due,
        },
        'by_status': by_status,
        'top_matches': [
            {'job_id': match.job_id, 'title': match.job.title, 'company': match.job.company, 'score': match.score}
            for match in top_matches
        ],
        'recommendations': recommendations,
    }


def dashboard(owner) -> dict[str, Any]:
    strategy = generate_strategy(owner)
    return {
        'profile_documents': ProfileDocument.objects.filter(owner=owner).count(),
        'profile_facts': ProfileFact.objects.filter(owner=owner).count(),
        'jobs': JobPosting.objects.filter(owner=owner).count(),
        'matches': JobMatch.objects.filter(owner=owner).count(),
        'applications': Application.objects.filter(owner=owner).count(),
        'resumes': Resume.objects.filter(owner=owner).count(),
        'strategy': strategy,
    }

