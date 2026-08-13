from __future__ import annotations

from typing import Any

from django.db.models import Count

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

