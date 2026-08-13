from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from core.models import CandidatePreference, CandidateProfile, ProfileDocument, ProfileFact


def candidate_profile(owner) -> CandidateProfile:
    profile, _ = CandidateProfile.objects.get_or_create(owner=owner)
    return profile


def compute_profile_completeness(owner) -> int:
    profile = candidate_profile(owner)
    checks = [
        bool(profile.headline),
        bool(profile.professional_summary),
        bool(profile.target_roles),
        bool(profile.location or profile.work_modes),
        bool(profile.authorized_countries),
        ProfileFact.objects.filter(owner=owner, lifecycle='verified').exists()
        or ProfileFact.objects.filter(owner=owner, verified_by_user=True).exists(),
        ProfileFact.objects.filter(owner=owner, fact_type='skill').exists(),
        ProfileFact.objects.filter(owner=owner, fact_type='achievement').exists(),
        CandidatePreference.objects.filter(owner=owner).exists(),
        ProfileDocument.objects.filter(owner=owner, status='ready').exists(),
    ]
    completeness = round(sum(checks) / len(checks) * 100)
    if profile.completeness != completeness:
        profile.completeness = completeness
        profile.save(update_fields=['completeness', 'updated_at'])
    return completeness


def profile_context(owner, *, verified_only: bool = False) -> dict[str, Any]:
    profile = candidate_profile(owner)
    facts = ProfileFact.objects.filter(owner=owner)
    if verified_only:
        facts = facts.filter(lifecycle='verified') | facts.filter(verified_by_user=True)
    facts = facts.order_by('-verified_by_user', 'fact_type', 'title')[:250]
    preferences = CandidatePreference.objects.filter(owner=owner).order_by('category', '-verified_by_user')
    return {
        'profile': {
            'headline': profile.headline,
            'professional_summary': profile.professional_summary,
            'target_roles': profile.target_roles,
            'target_industries': profile.target_industries,
            'location': profile.location,
            'authorized_countries': profile.authorized_countries,
            'work_modes': profile.work_modes,
            'employment_types': profile.employment_types,
            'minimum_compensation': profile.minimum_compensation,
            'compensation_currency': profile.compensation_currency,
            'excluded_companies': profile.excluded_companies,
            'completeness': compute_profile_completeness(owner),
        },
        'facts': [
            {
                'id': fact.id,
                'type': fact.fact_type,
                'title': fact.title,
                'statement': fact.statement,
                'confidence': fact.confidence,
                'lifecycle': fact.lifecycle,
                'verified': fact.verified_by_user or fact.lifecycle == 'verified',
                'evidence_quote': fact.evidence_quote,
            }
            for fact in facts
        ],
        'preferences': [
            {
                'id': preference.id,
                'category': preference.category,
                'label': preference.label,
                'value': preference.value,
                'importance': preference.importance,
                'verified': preference.verified_by_user,
            }
            for preference in preferences
        ],
    }


def profile_health(owner) -> dict[str, Any]:
    counts = dict(
        ProfileFact.objects.filter(owner=owner)
        .values('fact_type')
        .annotate(count=Count('id'))
        .values_list('fact_type', 'count')
    )
    unverified = ProfileFact.objects.filter(owner=owner, verified_by_user=False).exclude(lifecycle='verified').count()
    questions = []
    profile = candidate_profile(owner)
    if not profile.target_roles:
        questions.append('Which two or three role titles should the search prioritize?')
    if not profile.work_modes:
        questions.append('Do you prefer remote, hybrid, or on-site work?')
    if not profile.authorized_countries:
        questions.append('Where are you currently authorized to work?')
    if not counts.get('achievement'):
        questions.append('What accomplishment best demonstrates your impact?')
    return {
        'completeness': compute_profile_completeness(owner),
        'fact_counts': counts,
        'unverified_count': unverified,
        'questions': questions[:3],
    }


ONBOARDING_STEPS = {
    'welcome': ('Meet your Profile Steward', 'I’ll build the evidence and search brief every Forth specialist will use.'),
    'source': ('Start with what already exists', 'A resume gives me chronology, roles, education, skills, and useful language without making you repeat yourself.'),
    'source_processing': ('I’m reading your source', 'I’m extracting reusable facts now. This usually takes less than a minute.'),
    'direction': ('What should your next move look like?', 'Your target tells sourcing what to find and gives matching the right definition of fit.'),
    'logistics': ('Where can the right role be?', 'These answers become eligibility checks, not vague scoring signals.'),
    'strengths': ('What do people rely on you for?', 'I found the career shape. Now I need the capabilities you want Forth to prioritize.'),
    'impact': ('Give me one proof point', 'A specific accomplishment is more useful than a long list of responsibilities.'),
    'preferences': ('What makes work worth doing?', 'I’ll use these as boundaries when two roles look similar on paper.'),
    'summary': ('Let’s define your professional through-line', 'This becomes the shared context behind sourcing, scoring, and resume generation.'),
    'review': ('Your candidate profile is ready', 'Review the signal below. You can refine every fact later without restarting.'),
}


def _onboarding_readiness(owner) -> dict[str, Any]:
    profile = candidate_profile(owner)
    checks = {
        'career direction': bool(profile.target_roles and profile.headline),
        'location and authorization': bool(profile.authorized_countries and (profile.location or profile.work_modes)),
        'core capabilities': ProfileFact.objects.filter(owner=owner, fact_type='skill').exists(),
        'proof of impact': ProfileFact.objects.filter(owner=owner, fact_type='achievement').exists(),
        'work preferences': CandidatePreference.objects.filter(owner=owner).exists(),
        'professional summary': bool(profile.professional_summary),
    }
    complete = sum(checks.values())
    return {
        'score': round(complete / len(checks) * 100),
        'ready': all(checks.values()),
        'checks': checks,
        'missing': [label for label, passed in checks.items() if not passed],
    }


def _suggested_summary(owner) -> str:
    profile = candidate_profile(owner)
    skills = list(ProfileFact.objects.filter(owner=owner, fact_type='skill').values_list('title', flat=True)[:5])
    impact = ProfileFact.objects.filter(owner=owner, fact_type='achievement').order_by('-verified_by_user', '-id').first()
    target = ', '.join(profile.target_roles[:2])
    parts = []
    if profile.headline:
        parts.append(profile.headline.rstrip('.'))
    if skills:
        parts.append(f"Brings strength in {', '.join(skills)}")
    if impact:
        parts.append(f'Known for results such as: {impact.statement.rstrip(".")}')
    if target:
        parts.append(f'Seeking {target} opportunities where this experience can create meaningful impact')
    return '. '.join(parts) + ('.' if parts else '')


def onboarding_snapshot(owner) -> dict[str, Any]:
    profile = candidate_profile(owner)
    state = dict(profile.onboarding_state or {})
    documents = ProfileDocument.objects.filter(owner=owner)
    processing = documents.filter(status__in=['new', 'queued', 'processing']).exists()
    has_source = documents.filter(status='ready').exists()
    fact_counts = dict(ProfileFact.objects.filter(owner=owner).values('fact_type').annotate(count=Count('id')).values_list('fact_type', 'count'))
    preference_count = CandidatePreference.objects.filter(owner=owner).count()

    if profile.onboarding_completed_at:
        step_id = 'review'
    elif not state.get('started'):
        step_id = 'welcome'
    elif processing:
        step_id = 'source_processing'
    elif not has_source and 'source' not in state.get('skipped_steps', []):
        step_id = 'source'
    elif not profile.target_roles or not profile.headline:
        step_id = 'direction'
    elif not profile.authorized_countries or not (profile.location or profile.work_modes):
        step_id = 'logistics'
    elif not fact_counts.get('skill'):
        step_id = 'strengths'
    elif not fact_counts.get('achievement'):
        step_id = 'impact'
    elif not preference_count:
        step_id = 'preferences'
    elif not profile.professional_summary:
        step_id = 'summary'
    else:
        step_id = 'review'

    title, prompt = ONBOARDING_STEPS[step_id]
    readiness = _onboarding_readiness(owner)
    return {
        'needs_onboarding': profile.onboarding_completed_at is None,
        'step': {'id': step_id, 'title': title, 'prompt': prompt},
        'progress': max(5, min(100, readiness['score'] if step_id != 'welcome' else 5)),
        'readiness': readiness,
        'stats': {
            'documents': documents.count(),
            'facts': sum(fact_counts.values()),
            'skills': fact_counts.get('skill', 0),
            'achievements': fact_counts.get('achievement', 0),
            'preferences': preference_count,
        },
        'suggested_summary': _suggested_summary(owner),
    }


def _verified_fact(owner, *, fact_type: str, title: str, statement: str) -> None:
    from core.ai import embed_text

    title = str(title or '').strip()[:220]
    statement = str(statement or '').strip()
    if not title or not statement:
        return
    fact, _ = ProfileFact.objects.update_or_create(
        owner=owner,
        fact_type=fact_type,
        title=title,
        defaults={
            'statement': statement,
            'normalized_value': title.lower()[:220],
            'confidence': 'high',
            'verified_by_user': True,
            'lifecycle': 'verified',
            'strength': 'strong',
            'metadata': {'source': 'onboarding'},
            'embedding': embed_text(f'{title}\n{statement}'),
        },
    )


@transaction.atomic
def answer_onboarding(owner, *, step: str, answers: dict[str, Any]) -> dict[str, Any]:
    profile = candidate_profile(owner)
    state = dict(profile.onboarding_state or {})
    state['started'] = True
    state['last_step'] = step
    state['updated_at'] = timezone.now().isoformat()

    if step == 'source':
        skipped = list(state.get('skipped_steps', []))
        if answers.get('skip') and 'source' not in skipped:
            skipped.append('source')
        state['skipped_steps'] = skipped
    elif step == 'direction':
        roles = [str(value).strip() for value in answers.get('target_roles', []) if str(value).strip()]
        headline = str(answers.get('headline', '')).strip()
        if not roles or not headline:
            raise ValueError('Add a professional headline and at least one target role.')
        profile.headline = headline[:220]
        profile.target_roles = roles[:8]
        profile.target_industries = [str(value).strip() for value in answers.get('target_industries', []) if str(value).strip()][:12]
    elif step == 'logistics':
        countries = [str(value).strip() for value in answers.get('authorized_countries', []) if str(value).strip()]
        work_modes = [str(value).strip().lower() for value in answers.get('work_modes', []) if str(value).strip()]
        if not countries or not work_modes:
            raise ValueError('Choose at least one authorized country and one work mode.')
        profile.location = str(answers.get('location', '')).strip()[:220]
        profile.authorized_countries = countries[:12]
        profile.work_modes = work_modes[:4]
        profile.employment_types = [str(value).strip().lower() for value in answers.get('employment_types', []) if str(value).strip()][:8]
        compensation = answers.get('minimum_compensation')
        profile.minimum_compensation = int(compensation) if str(compensation or '').isdigit() else None
        profile.compensation_currency = str(answers.get('compensation_currency', 'CAD'))[:8]
    elif step == 'strengths':
        skills = [str(value).strip() for value in answers.get('skills', []) if str(value).strip()]
        capability = str(answers.get('capability', '')).strip()
        if not skills:
            raise ValueError('Add at least one capability or skill.')
        for skill in skills[:20]:
            statement = f'{skill} is a user-verified core capability.'
            if capability:
                statement = f'{skill}: {capability}'
            _verified_fact(owner, fact_type='skill', title=skill, statement=statement)
    elif step == 'impact':
        title = str(answers.get('title', '')).strip()
        story = str(answers.get('story', '')).strip()
        if not title or len(story) < 30:
            raise ValueError('Give this accomplishment a title and describe the result with enough detail.')
        _verified_fact(owner, fact_type='achievement', title=title, statement=story)
    elif step == 'preferences':
        ideals = [str(value).strip() for value in answers.get('ideal', []) if str(value).strip()]
        avoids = [str(value).strip() for value in answers.get('avoid', []) if str(value).strip()]
        if not ideals and not avoids:
            raise ValueError('Choose at least one preference or boundary.')
        for label in ideals[:12]:
            CandidatePreference.objects.update_or_create(owner=owner, category='culture', label=label, defaults={'importance': 'strong', 'verified_by_user': True, 'value': {}, 'rationale': 'Collected during onboarding.'})
        for label in avoids[:12]:
            CandidatePreference.objects.update_or_create(owner=owner, category='culture', label=label, defaults={'importance': 'avoid', 'verified_by_user': True, 'value': {}, 'rationale': 'Collected during onboarding.'})
    elif step == 'summary':
        summary = str(answers.get('professional_summary', '')).strip()
        if len(summary) < 40:
            raise ValueError('Add a little more detail so the agents have a useful professional through-line.')
        profile.professional_summary = summary
    elif step == 'complete':
        readiness = _onboarding_readiness(owner)
        if not readiness['ready']:
            raise ValueError(f"Complete these profile signals first: {', '.join(readiness['missing'])}.")
        profile.onboarding_completed_at = timezone.now()

    profile.onboarding_state = state
    profile.last_reviewed_at = timezone.now()
    profile.save()
    compute_profile_completeness(owner)
    return onboarding_snapshot(owner)
