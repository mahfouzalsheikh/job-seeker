from __future__ import annotations

import re
from typing import Any

from django.db import transaction

from core.ai import cosine_similarity, detect_skills, embed_text, keywords
from core.domain.profiles import profile_context
from core.models import JobMatch, JobPosting, MatchSignal, ProfileFact


WEIGHTS = {
    'skills': 35,
    'evidence': 25,
    'direction': 20,
    'domain': 10,
    'logistics': 10,
}


def _contains(blob: str, value: str) -> bool:
    return bool(value and re.search(rf'(?<!\w){re.escape(value.lower())}(?!\w)', blob.lower()))


def _compensation_floor(value: str) -> int | None:
    numbers = [int(raw.replace(',', '')) for raw in re.findall(r'\b(\d{2,3}(?:,\d{3})?)\b', value or '')]
    numbers = [number * 1000 if number < 1000 else number for number in numbers]
    return min(numbers) if numbers else None


def eligibility(job: JobPosting, context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    profile = context['profile']
    failures: list[str] = []
    uncertainties: list[str] = []
    company = job.company.lower()
    if any(str(item).lower() in company for item in profile.get('excluded_companies', [])):
        failures.append('Company is on the exclusion list.')
    work_modes = [str(item).lower() for item in profile.get('work_modes', [])]
    if work_modes and job.remote_policy not in work_modes and job.remote_policy != 'unknown':
        strong_mode = any(
            pref['category'] == 'work_mode' and pref['importance'] == 'must'
            for pref in context['preferences']
        )
        (failures if strong_mode else uncertainties).append(f'{job.remote_policy.title()} work may not match the preferred work mode.')
    minimum = profile.get('minimum_compensation')
    offered = _compensation_floor(job.compensation)
    if minimum and offered and offered < minimum:
        failures.append(f'Visible compensation is below the {minimum:,} minimum.')
    elif minimum and not offered:
        uncertainties.append('Compensation is not visible.')
    if profile.get('authorized_countries') and not job.location:
        uncertainties.append('Work location or authorization requirement is unclear.')
    status = 'fail' if failures else 'uncertain' if uncertainties else 'pass'
    return status, failures, uncertainties


def _signal(kind: str, label: str, score: int, explanation: str, evidence: list[Any]) -> dict[str, Any]:
    return {
        'kind': kind,
        'label': label,
        'score': max(0, min(100, round(score))),
        'weight': WEIGHTS.get(kind, 0),
        'explanation': explanation,
        'evidence': evidence,
    }


@transaction.atomic
def recompute_match(job: JobPosting) -> JobMatch:
    context = profile_context(job.owner)
    facts = list(ProfileFact.objects.filter(owner=job.owner).order_by('-verified_by_user', 'fact_type', 'title')[:250])
    fact_text = '\n'.join(f'{fact.title}: {fact.statement}' for fact in facts)
    profile_blob = fact_text.lower()
    job_blob = job.description_text.lower()
    job_skills = list(dict.fromkeys(
        [req.normalized_value or req.text for req in job.requirements.filter(category='skill')]
        or detect_skills(job.description_text)
    ))
    covered = [skill for skill in job_skills if _contains(profile_blob, skill)]
    missing = [skill for skill in job_skills if skill not in covered]
    skill_score = round(len(covered) / max(1, len(job_skills)) * 100)

    supporting = []
    for fact in facts:
        overlap = [skill for skill in covered if _contains(f'{fact.title} {fact.statement}', skill)]
        if overlap:
            supporting.append({
                'fact_id': fact.id,
                'title': fact.title,
                'statement': fact.statement,
                'skills': overlap,
                'verified': fact.verified_by_user or fact.lifecycle == 'verified',
            })
    verified_support = [fact for fact in supporting if fact['verified']]
    evidence_score = min(100, len(supporting) * 10 + len(verified_support) * 8)

    targets = [str(value).lower() for value in context['profile'].get('target_roles', [])]
    title_tokens = set(keywords(job.title, limit=20))
    target_tokens = set(keywords(' '.join(targets), limit=60))
    direction_score = round(100 * len(title_tokens & target_tokens) / max(1, len(title_tokens))) if targets else 55

    industries = [str(value).lower() for value in context['profile'].get('target_industries', [])]
    domain_score = 80 if any(value in job_blob or value in job.company.lower() for value in industries) else 55 if industries else 60

    hard_status, failures, uncertainties = eligibility(job, context)
    logistics_score = 100 if hard_status == 'pass' else 60 if hard_status == 'uncertain' else 0

    fact_embedding = embed_text(fact_text) if fact_text else []
    job_embedding = job.embedding or embed_text(job.description_text)
    semantic = round(((cosine_similarity(fact_embedding, job_embedding) + 1) / 2) * 100) if fact_text else 0
    evidence_score = round(evidence_score * .7 + semantic * .3)

    signals = [
        _signal('skills', 'Skills and depth', skill_score, f'{len(covered)} of {len(job_skills)} visible skills are supported.', covered),
        _signal('evidence', 'Experience evidence', evidence_score, f'{len(supporting)} profile facts support this role; {len(verified_support)} are verified.', supporting[:12]),
        _signal('direction', 'Role direction', direction_score, 'Alignment with the candidate’s stated target roles.', context['profile'].get('target_roles', [])),
        _signal('domain', 'Domain relevance', domain_score, 'Alignment with target industries and prior domain evidence.', industries),
        _signal('logistics', 'Logistics', logistics_score, 'Location, work mode, compensation, and exclusions.', failures + uncertainties),
    ]
    weighted = sum(signal['score'] * signal['weight'] for signal in signals) / 100
    score = round(weighted)
    if hard_status == 'fail':
        score = min(score, 39)
    elif hard_status == 'uncertain':
        score = min(score, 84)
    confidence_points = len(verified_support) * 2 + len(facts) / 10 + (10 if job.requirements.exists() else 0)
    confidence = 'high' if confidence_points >= 24 else 'medium' if confidence_points >= 10 else 'low'
    summary = (
        f'{"Strong" if score >= 80 else "Promising" if score >= 65 else "Possible" if score >= 50 else "Low"} fit: '
        f'{len(covered)} supported skills, {len(missing)} visible gaps, eligibility {hard_status}.'
    )
    explanation = {
        'summary': summary,
        'covered_skills': covered,
        'job_skills': job_skills,
        'eligibility_failures': failures,
        'eligibility_uncertainties': uncertainties,
        'signals': signals,
        'score_version': '2026-08-v2',
    }
    match, _ = JobMatch.objects.update_or_create(
        owner=job.owner,
        job=job,
        defaults={
            'score': max(0, min(100, score)),
            'hard_filter_status': hard_status,
            'explanation_json': explanation,
            'missing_requirements': missing,
            'supporting_facts': supporting[:16],
            'confidence': confidence,
        },
    )
    MatchSignal.objects.filter(match=match).delete()
    MatchSignal.objects.bulk_create([
        MatchSignal(owner=job.owner, match=match, **signal) for signal in signals
    ])
    return match

