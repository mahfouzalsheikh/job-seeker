from __future__ import annotations

import json
from typing import Any, Callable

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from core.ai import clean_text, generate_json
from core.domain.briefing import today_briefing
from core.domain.documents import prepare_application_materials, render_application_bundle
from core.domain.profiles import profile_health
from core.domain.sourcing import execute_source_run
from core.models import (
    AgentRun,
    AgentStep,
    Application,
    ApplicationEvent,
    ApprovalRequest,
    ConversationMessage,
    ConversationThread,
    JobPosting,
    JobSource,
    ProfileFact,
    SourceRun,
)
from core.realtime_events import publish_user_event


def default_thread(owner) -> ConversationThread:
    thread = ConversationThread.objects.filter(owner=owner, status='active').first()
    if thread:
        return thread
    return ConversationThread.objects.create(owner=owner, title='Job search concierge')


def _classify(message: str) -> dict[str, str]:
    schema = {
        'name': 'concierge_route',
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'agent': {'type': 'string', 'enum': ['profile', 'sourcing', 'matching', 'application', 'documents', 'concierge']},
                'intent': {'type': 'string'},
            },
            'required': ['agent', 'intent'],
        },
    }
    generated = generate_json(
        'Route this job-search request to one specialist. Do not answer the request.',
        message[:4000],
        schema,
    )
    if generated:
        return generated.data
    lowered = message.lower()
    if any(term in lowered for term in ['resume', 'cover letter', 'materials', 'pdf', 'tailor', 'prepare']):
        return {'agent': 'documents', 'intent': 'prepare_materials'}
    if any(term in lowered for term in ['find jobs', 'source', 'discover', 'new roles', 'refresh jobs']):
        return {'agent': 'sourcing', 'intent': 'run_sources'}
    if any(term in lowered for term in ['profile', 'skill', 'experience', 'fact', 'know about me']):
        return {'agent': 'profile', 'intent': 'profile_review'}
    if any(term in lowered for term in ['score', 'match', 'fit', 'why this job']):
        return {'agent': 'matching', 'intent': 'explain_matches'}
    if any(term in lowered for term in ['apply', 'follow up', 'pipeline', 'interview']):
        return {'agent': 'application', 'intent': 'application_next_action'}
    return {'agent': 'concierge', 'intent': 'daily_briefing'}


def create_concierge_run(owner, *, message: str, thread: ConversationThread | None = None) -> AgentRun:
    thread = thread or default_thread(owner)
    ConversationMessage.objects.create(owner=owner, thread=thread, role='user', content=message)
    route = _classify(message)
    return AgentRun.objects.create(
        owner=owner,
        thread=thread,
        agent=route['agent'],
        objective=message,
        input={'message': message, 'intent': route['intent']},
        model=getattr(settings, 'OPENAI_TEXT_MODEL', ''),
    )


def _record_step(run: AgentRun, name: str, handler: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    sequence = run.steps.count() + 1
    step = AgentStep.objects.create(
        owner=run.owner, run=run, sequence=sequence, name=name, status='running', started_at=timezone.now(),
    )
    try:
        output = json.loads(json.dumps(handler(), cls=DjangoJSONEncoder))
        step.status = 'succeeded'
        step.output = output
        return output
    except Exception as exc:
        step.status = 'failed'
        step.error = str(exc)[:2000]
        raise
    finally:
        step.completed_at = timezone.now()
        step.save(update_fields=['status', 'output', 'error', 'completed_at', 'updated_at'])


def _job_from_run(run: AgentRun) -> JobPosting | None:
    job_id = run.input.get('job_id')
    if job_id:
        return JobPosting.objects.filter(owner=run.owner, pk=job_id).first()
    return JobPosting.objects.filter(owner=run.owner).select_related('match').order_by('-match__score').first()


def _approval(run: AgentRun, *, kind: str, title: str, prompt: str, payload: dict[str, Any]) -> ApprovalRequest:
    approval = ApprovalRequest.objects.create(
        owner=run.owner, run=run, kind=kind, title=title, prompt=prompt, payload=payload,
    )
    run.status = 'waiting_approval'
    run.save(update_fields=['status', 'updated_at'])
    publish_user_event(run.owner_id, 'approval_requested', {'approval_id': approval.id, 'run_id': run.id, 'kind': kind})
    return approval


def _handle_profile(run: AgentRun) -> dict[str, Any]:
    health = profile_health(run.owner)
    if health['questions']:
        reply = f"Your profile is {health['completeness']}% complete. The highest-value question is: {health['questions'][0]}"
    else:
        reply = f"Your profile is {health['completeness']}% complete with {health['unverified_count']} facts still awaiting review."
    return {'reply': reply, 'profile_health': health}


def _handle_sourcing(run: AgentRun) -> dict[str, Any]:
    sources = list(JobSource.objects.filter(owner=run.owner, enabled=True))
    summaries = []
    for source in sources:
        source_run = SourceRun.objects.create(owner=run.owner, source=source)
        execute_source_run(source_run)
        summaries.append({
            'source': source.name,
            'status': source_run.status,
            'imported': source_run.imported_count,
            'updated': source_run.updated_count,
            'errors': source_run.error_count,
        })
    imported = sum(item['imported'] for item in summaries)
    return {'reply': f'I refreshed {len(sources)} sources and found {imported} new roles.', 'source_runs': summaries}


def _handle_matching(run: AgentRun) -> dict[str, Any]:
    briefing = today_briefing(run.owner)
    queue = briefing['review_queue']
    if not queue:
        reply = 'There are no fresh scored opportunities yet. Add or run a source to build the review queue.'
    else:
        best = queue[0]
        reply = f"{best['title']} at {best['company'] or 'the company'} leads the queue at {best['score']} fit. {best['summary']}"
    return {'reply': reply, 'review_queue': queue[:5]}


def _handle_documents(run: AgentRun) -> dict[str, Any]:
    job = _job_from_run(run)
    if not job:
        return {'reply': 'Choose or import a job before preparing application materials.'}
    approval = _approval(
        run,
        kind='prepare_application',
        title=f'Prepare application for {job.title}',
        prompt=f'Create an evidence-backed resume and cover letter for {job.title} at {job.company or "this company"}?',
        payload={'job_id': job.id},
    )
    return {'reply': 'I have the role and evidence ready. Your approval is required before I draft the application materials.', 'approval_id': approval.id}


def _handle_application(run: AgentRun) -> dict[str, Any]:
    due = today_briefing(run.owner)['due_actions']
    if due:
        return {'reply': f"You have {len(due)} follow-up action{'s' if len(due) != 1 else ''} due. Start with {due[0]['title']}.", 'due_actions': due}
    job = _job_from_run(run)
    if job:
        approval = _approval(
            run,
            kind='prepare_application',
            title=f'Move {job.title} forward',
            prompt='Approve this opportunity and prepare its application materials?',
            payload={'job_id': job.id},
        )
        return {'reply': 'There are no overdue follow-ups. I can move your strongest opportunity forward.', 'approval_id': approval.id}
    return {'reply': 'Your pipeline is clear. Import or discover jobs to create the next action.'}


def _handle_concierge(run: AgentRun) -> dict[str, Any]:
    briefing = today_briefing(run.owner)
    reply = f"You have {briefing['review_count']} roles to review, {briefing['pending_approvals']} approvals waiting, and {briefing['followups_due']} follow-ups due."
    return {'reply': reply, 'briefing': briefing}


HANDLERS = {
    'profile': _handle_profile,
    'sourcing': _handle_sourcing,
    'matching': _handle_matching,
    'application': _handle_application,
    'documents': _handle_documents,
    'concierge': _handle_concierge,
}


def execute_agent_run(run: AgentRun) -> AgentRun:
    if run.status in {'succeeded', 'cancelled'}:
        return run
    run.status = 'running'
    run.started_at = run.started_at or timezone.now()
    run.save(update_fields=['status', 'started_at', 'updated_at'])
    publish_user_event(run.owner_id, 'agent_run_started', {'run_id': run.id, 'agent': run.agent})
    try:
        output = _record_step(run, f'{run.agent}.execute', lambda: HANDLERS[run.agent](run))
        run.output = output
        if run.status != 'waiting_approval':
            run.status = 'succeeded'
            run.completed_at = timezone.now()
        if run.thread and output.get('reply'):
            ConversationMessage.objects.create(
                owner=run.owner, thread=run.thread, role='assistant', content=output['reply'], metadata={'run_id': run.id, 'agent': run.agent},
            )
    except Exception as exc:
        run.status = 'failed'
        run.error = str(exc)[:4000]
        run.completed_at = timezone.now()
        if run.thread:
            ConversationMessage.objects.create(
                owner=run.owner, thread=run.thread, role='assistant',
                content='I could not complete that workflow. The failure was recorded so it can be retried safely.',
                metadata={'run_id': run.id, 'error': run.error},
            )
    run.save()
    publish_user_event(run.owner_id, 'agent_run_updated', {'run_id': run.id, 'agent': run.agent, 'status': run.status})
    return run


@transaction.atomic
def decide_approval(approval: ApprovalRequest, *, approved: bool, response: dict[str, Any] | None = None) -> ApprovalRequest:
    if approval.status != 'pending':
        return approval
    approval.status = 'approved' if approved else 'rejected'
    approval.response = response or {}
    approval.decided_at = timezone.now()
    approval.save(update_fields=['status', 'response', 'decided_at', 'updated_at'])
    run = approval.run
    if not approved:
        if run:
            run.status = 'cancelled'
            run.completed_at = timezone.now()
            run.save(update_fields=['status', 'completed_at', 'updated_at'])
        return approval

    if approval.kind == 'prepare_application':
        job = JobPosting.objects.get(owner=approval.owner, pk=approval.payload['job_id'])
        application, _ = Application.objects.get_or_create(
            owner=approval.owner, job=job, defaults={'status': 'preparing'},
        )
        application.status = 'preparing'
        application.save(update_fields=['status', 'updated_at'])
        materials = prepare_application_materials(approval.owner, job, application=application)
        ApplicationEvent.objects.create(
            owner=approval.owner, application=application, event_type='materials_prepared',
            happened_at=timezone.now(), notes='Resume and cover letter drafts prepared after user approval.',
            metadata={'resume_id': materials['resume'].id, 'cover_letter_id': materials['cover_letter'].id},
        )
        if run:
            run.output = {**(run.output or {}), 'application_id': application.id, 'resume_id': materials['resume'].id, 'cover_letter_id': materials['cover_letter'].id}
    elif approval.kind == 'verify_fact':
        fact = ProfileFact.objects.get(owner=approval.owner, pk=approval.payload['fact_id'])
        fact.verified_by_user = True
        fact.lifecycle = 'verified'
        fact.save(update_fields=['verified_by_user', 'lifecycle', 'updated_at'])
    elif approval.kind == 'render_bundle':
        application = Application.objects.get(owner=approval.owner, pk=approval.payload['application_id'])
        artifacts = render_application_bundle(approval.owner, application=application)
        if run:
            run.output = {**(run.output or {}), 'artifact_ids': [artifact.id for artifact in artifacts]}

    if run:
        run.status = 'succeeded'
        run.completed_at = timezone.now()
        run.save(update_fields=['status', 'output', 'completed_at', 'updated_at'])
    publish_user_event(approval.owner_id, 'approval_decided', {'approval_id': approval.id, 'status': approval.status})
    return approval
