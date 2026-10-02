#!/usr/bin/env python3
"""A local, owner-scoped MCP adapter for Forth.

This intentionally uses the standard library JSON-RPC transport instead of an
MCP framework so the career system has no additional runtime dependency.  It
implements the stdio subset required by MCP clients: initialize, tools/list,
and tools/call.

Run it with an explicitly selected owner.  Never run it with a shared or
untrusted account:

    FORTH_MCP_OWNER_EMAIL=you@example.com python backend/mcp_server.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forth.settings')

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

from core.domain.documents import prepare_application_materials  # noqa: E402
from core.domain.matching import recompute_match  # noqa: E402
from core.domain.profiles import candidate_profile  # noqa: E402
from core.models import (  # noqa: E402
    Application,
    ApplicationEvent,
    CandidatePreference,
    CoverLetter,
    JobMatch,
    JobPosting,
    ProfileFact,
    Resume,
)
from core.services import import_job_posting  # noqa: E402


class ToolError(ValueError):
    """A safe, actionable tool error shown to the MCP caller."""


def _owner():
    """Resolve one owner explicitly; fail closed if no selector is configured."""
    owner_id = os.environ.get('FORTH_MCP_OWNER_ID', '').strip()
    owner_email = os.environ.get('FORTH_MCP_OWNER_EMAIL', '').strip()
    if not owner_id and not owner_email:
        raise ToolError(
            'Set FORTH_MCP_OWNER_ID or FORTH_MCP_OWNER_EMAIL before starting Forth MCP. '
            'The server will not choose an account implicitly.'
        )
    query = get_user_model().objects
    try:
        return query.get(pk=int(owner_id)) if owner_id else query.get(email__iexact=owner_email)
    except (ValueError, get_user_model().DoesNotExist) as exc:
        raise ToolError('The configured Forth MCP owner does not exist.') from exc


def _limit(value: Any, *, default: int = 10, maximum: int = 40) -> int:
    try:
        return max(1, min(int(value or default), maximum))
    except (TypeError, ValueError):
        return default


def _job_result(job: JobPosting, match: JobMatch | None = None) -> dict[str, Any]:
    match = match or getattr(job, 'match', None)
    return {
        'job_id': job.id,
        'title': job.title,
        'company': job.company,
        'location': job.location,
        'work_mode': job.remote_policy,
        'seniority': job.seniority,
        'compensation': job.compensation,
        'source_url': job.source_url,
        'application_url': job.application_url or job.source_url,
        'freshness': job.freshness_status,
        'status': job.status,
        'match': None if not match else {
            'score': match.score,
            'confidence': match.confidence,
            'eligibility': match.hard_filter_status,
            'summary': (match.explanation_json or {}).get('summary', ''),
            'covered_skills': (match.explanation_json or {}).get('covered_skills', []),
            'missing_requirements': match.missing_requirements,
            'eligibility_notes': (
                (match.explanation_json or {}).get('eligibility_failures', [])
                + (match.explanation_json or {}).get('eligibility_uncertainties', [])
            ),
            'supporting_facts': match.supporting_facts[:8],
        },
    }


def get_candidate_context(arguments: dict[str, Any]) -> dict[str, Any]:
    owner = _owner()
    profile = candidate_profile(owner)
    facts = ProfileFact.objects.filter(owner=owner).order_by('-verified_by_user', 'fact_type', 'title')
    if arguments.get('verified_only', True):
        facts = facts.filter(verified_by_user=True)
    return {
        'profile': {
            'headline': profile.headline,
            'summary': profile.professional_summary,
            'target_roles': profile.target_roles,
            'target_industries': profile.target_industries,
            'location': profile.location,
            'authorized_countries': profile.authorized_countries,
            'work_modes': profile.work_modes,
            'employment_types': profile.employment_types,
            'minimum_compensation': profile.minimum_compensation,
            'compensation_currency': profile.compensation_currency,
            'completeness': profile.completeness,
        },
        'preferences': list(CandidatePreference.objects.filter(owner=owner).values(
            'category', 'label', 'value', 'importance', 'verified_by_user', 'rationale',
        )),
        'facts': list(facts[:_limit(arguments.get('limit'), default=30)] .values(
            'id', 'fact_type', 'title', 'statement', 'verified_by_user', 'lifecycle', 'strength',
        )),
    }


def search_jobs(arguments: dict[str, Any]) -> dict[str, Any]:
    owner = _owner()
    query = str(arguments.get('query', '')).strip()
    min_score = arguments.get('min_score')
    jobs = JobPosting.objects.filter(owner=owner).select_related('match')
    if arguments.get('work_mode'):
        jobs = jobs.filter(remote_policy=str(arguments['work_mode']).lower())
    if min_score is not None:
        try:
            jobs = jobs.filter(match__score__gte=int(min_score))
        except (TypeError, ValueError):
            raise ToolError('min_score must be an integer from 0 to 100.')
    if query:
        from core.domain.embeddings import rank_jobs_by_query
        jobs = rank_jobs_by_query(jobs, query)
    else:
        jobs = jobs.order_by('-match__score', '-posted_at', '-discovered_at')
    return {'query': query, 'jobs': [_job_result(job) for job in jobs[:_limit(arguments.get('limit'))]]}


def record_job(arguments: dict[str, Any]) -> dict[str, Any]:
    """Import a browser-found public posting and immediately score it."""
    text = str(arguments.get('description', '')).strip()
    source_url = str(arguments.get('source_url', '')).strip()
    if len(text) < 80:
        raise ToolError('description must contain the job posting text (at least 80 characters).')
    if source_url and not source_url.startswith(('https://', 'http://')):
        raise ToolError('source_url must be an http(s) URL.')
    owner = _owner()
    job = import_job_posting(owner, text=text, source_url=source_url)
    job.refresh_from_db()
    match = JobMatch.objects.filter(owner=owner, job=job).first() or recompute_match(job)
    return {'recorded': True, 'job': _job_result(job, match)}


def prepare_application(arguments: dict[str, Any]) -> dict[str, Any]:
    """Create drafts only. It never approves materials or submits a form."""
    owner = _owner()
    try:
        job = JobPosting.objects.get(owner=owner, pk=int(arguments.get('job_id')))
    except (TypeError, ValueError, JobPosting.DoesNotExist) as exc:
        raise ToolError('job_id must identify a job in the configured owner workspace.') from exc
    application, _ = Application.objects.get_or_create(
        owner=owner, job=job, defaults={'status': 'preparing'},
    )
    result = prepare_application_materials(owner, job, application=application)
    resume, letter = result['resume'], result['cover_letter']
    return {
        'application_id': application.id,
        'job_id': job.id,
        'status': 'materials_ready',
        'resume': {
            'id': resume.id, 'title': resume.title, 'content_markdown': resume.content_markdown,
            'approved': resume.approved, 'validation': resume.validation,
        },
        'cover_letter': {
            'id': letter.id, 'title': letter.title, 'content_markdown': letter.content_markdown,
            'approved': letter.approved, 'validation': letter.validation,
        },
        'next_step': 'Review and explicitly approve the drafts. Application submission remains a separate browser action requiring confirmation.',
    }


def get_application_materials(arguments: dict[str, Any]) -> dict[str, Any]:
    owner = _owner()
    try:
        job = JobPosting.objects.get(owner=owner, pk=int(arguments.get('job_id')))
    except (TypeError, ValueError, JobPosting.DoesNotExist) as exc:
        raise ToolError('job_id must identify a job in the configured owner workspace.') from exc
    application = Application.objects.filter(owner=owner, job=job).select_related('resume').first()
    resume = Resume.objects.filter(owner=owner, target_job=job).order_by('-updated_at').first()
    letter = CoverLetter.objects.filter(owner=owner, target_job=job).order_by('-version').first()
    return {
        'job': _job_result(job),
        'application': None if not application else {
            'id': application.id, 'status': application.status, 'applied_at': application.applied_at,
        },
        'resume': None if not resume else {
            'id': resume.id, 'content_markdown': resume.content_markdown,
            'approved': resume.approved, 'validation': resume.validation,
        },
        'cover_letter': None if not letter else {
            'id': letter.id, 'content_markdown': letter.content_markdown,
            'approved': letter.approved, 'validation': letter.validation,
        },
        'submission_rule': 'Do not enter candidate data or submit an external application without explicit user confirmation at the browser step.',
    }


def record_submitted_application(arguments: dict[str, Any]) -> dict[str, Any]:
    """Record an application only after the browser visibly confirms submission."""
    owner = _owner()
    try:
        application = Application.objects.get(owner=owner, pk=int(arguments.get('application_id')))
    except (TypeError, ValueError, Application.DoesNotExist) as exc:
        raise ToolError('application_id must identify an application in the configured owner workspace.') from exc
    confirmation = str(arguments.get('submission_confirmation', '')).strip()
    if len(confirmation) < 12:
        raise ToolError('Provide the visible submission confirmation before recording an application as applied.')
    application.status = 'applied'
    application.applied_at = timezone.now()
    application.save(update_fields=['status', 'applied_at', 'updated_at'])
    ApplicationEvent.objects.create(
        owner=owner, application=application, event_type='submitted', happened_at=application.applied_at,
        notes=confirmation[:1000], metadata={'recorded_by': 'forth_mcp'},
    )
    return {'application_id': application.id, 'status': application.status, 'applied_at': application.applied_at.isoformat()}


TOOLS: dict[str, tuple[str, dict[str, Any], Callable[[dict[str, Any]], dict[str, Any]]]] = {
    'get_candidate_context': (
        'Read the owner-scoped career profile, verified evidence, and job-search preferences before sourcing or matching.',
        {'type': 'object', 'properties': {'verified_only': {'type': 'boolean', 'default': True}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 40}}},
        get_candidate_context,
    ),
    'search_jobs': (
        'Search and rank jobs already recorded in Forth. Results include explainable fit scores and evidence gaps.',
        {'type': 'object', 'properties': {'query': {'type': 'string'}, 'min_score': {'type': 'integer', 'minimum': 0, 'maximum': 100}, 'work_mode': {'type': 'string', 'enum': ['remote', 'hybrid', 'onsite', 'unknown']}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 40}}},
        search_jobs,
    ),
    'record_job': (
        'Record a public job found through browser research, normalize it, deduplicate it, and compute its explainable match. Requires full posting text; it does not submit anything.',
        {'type': 'object', 'properties': {'description': {'type': 'string', 'description': 'Visible job posting text.'}, 'source_url': {'type': 'string', 'description': 'Canonical public posting URL.'}}, 'required': ['description']},
        record_job,
    ),
    'prepare_application': (
        'Create a tracked application plus unapproved, claim-validated tailored resume and cover-letter drafts. Never approves materials or submits an external application.',
        {'type': 'object', 'properties': {'job_id': {'type': 'integer'}}, 'required': ['job_id']},
        prepare_application,
    ),
    'get_application_materials': (
        'Read current tailored materials and validation state for a recorded job. Use it to prepare a browser-assisted application after the user has reviewed the drafts.',
        {'type': 'object', 'properties': {'job_id': {'type': 'integer'}}, 'required': ['job_id']},
        get_application_materials,
    ),
    'record_submitted_application': (
        'Update Forth only after a browser visibly confirms that an external application was submitted. This does not submit a form.',
        {'type': 'object', 'properties': {'application_id': {'type': 'integer'}, 'submission_confirmation': {'type': 'string', 'description': 'Visible confirmation text from the completed site.'}}, 'required': ['application_id', 'submission_confirmation']},
        record_submitted_application,
    ),
}


def _tool_definitions() -> list[dict[str, Any]]:
    return [{'name': name, 'description': spec[0], 'inputSchema': spec[1]} for name, spec in TOOLS.items()]


def _result(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {'content': [{'type': 'text', 'text': json.dumps(value, default=str, ensure_ascii=False)}], 'isError': is_error}


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get('method')
    request_id = request.get('id')
    if method == 'notifications/initialized':
        return None
    if method == 'initialize':
        payload = {
            'protocolVersion': request.get('params', {}).get('protocolVersion', '2025-03-26'),
            'capabilities': {'tools': {'listChanged': False}},
            'serverInfo': {'name': 'forth-job-seeker', 'version': '0.1.0'},
        }
    elif method == 'tools/list':
        payload = {'tools': _tool_definitions()}
    elif method == 'tools/call':
        params = request.get('params') or {}
        name = params.get('name')
        arguments = params.get('arguments') or {}
        if name not in TOOLS:
            payload = _result({'error': f'Unknown tool: {name}'}, is_error=True)
        elif not isinstance(arguments, dict):
            payload = _result({'error': 'Tool arguments must be an object.'}, is_error=True)
        else:
            try:
                payload = _result(TOOLS[name][2](arguments))
            except ToolError as exc:
                payload = _result({'error': str(exc)}, is_error=True)
            except Exception:
                payload = _result({'error': 'Forth could not complete that operation. Check the local server logs.'}, is_error=True)
    else:
        payload = {'error': {'code': -32601, 'message': f'Method not found: {method}'}}
    if request_id is None:
        return None
    return {'jsonrpc': '2.0', 'id': request_id, 'result': payload} if 'error' not in payload else {'jsonrpc': '2.0', 'id': request_id, **payload}


def main() -> None:
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError('JSON-RPC request must be an object.')
            response = handle_request(request)
        except (json.JSONDecodeError, ValueError) as exc:
            response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': str(exc)}}
        if response is not None:
            print(json.dumps(response, default=str, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
