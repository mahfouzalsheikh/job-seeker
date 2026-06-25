from __future__ import annotations

from celery import shared_task

from .models import JobPosting, ProfileDocument
from .realtime_events import publish_user_event
from .services import ingest_profile_document, recompute_match


@shared_task
def ingest_profile_document_task(document_id: int) -> dict:
    document = ProfileDocument.objects.select_related('owner').get(pk=document_id)
    publish_user_event(document.owner_id, 'profile_ingestion_started', {'document_id': document.id})
    result = ingest_profile_document(document)
    publish_user_event(document.owner_id, 'profile_ingestion_finished', {'document_id': document.id, **result})
    return result


@shared_task
def recompute_job_match_task(job_id: int) -> dict:
    job = JobPosting.objects.select_related('owner').get(pk=job_id)
    publish_user_event(job.owner_id, 'match_recompute_started', {'job_id': job.id})
    match = recompute_match(job)
    payload = {'job_id': job.id, 'match_id': match.id, 'score': match.score, 'confidence': match.confidence}
    publish_user_event(job.owner_id, 'match_recomputed', payload)
    return payload


@shared_task
def recompute_all_matches_task(owner_id: int) -> dict:
    jobs = JobPosting.objects.filter(owner_id=owner_id)
    count = 0
    for job in jobs.iterator():
        recompute_match(job)
        count += 1
    publish_user_event(owner_id, 'matches_recomputed', {'count': count})
    return {'count': count}

