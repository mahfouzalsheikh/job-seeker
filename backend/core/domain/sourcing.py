from __future__ import annotations

import html
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree
from urllib.parse import urlencode, urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from core.ai import clean_text, stable_hash
from core.models import JobPosting, JobPostingVersion, JobRequirement, JobSource, SourceRun


def _plain(value: Any) -> str:
    text = html.unescape(str(value or ''))
    text = re.sub(r'<(br|/p|/li)>', '\n', text, flags=re.I)
    return clean_text(re.sub(r'<[^>]+>', ' ', text))


@dataclass
class SourceRecord:
    external_id: str
    title: str
    company: str
    location: str
    description: str
    source_url: str
    application_url: str
    posted_at: datetime | None = None
    payload: dict[str, Any] | None = None


class SourceConnector:
    def __init__(self, source: JobSource):
        self.source = source
        self.config = source.config or {}
        self.timeout = int(getattr(settings, 'SOURCE_HTTP_TIMEOUT_SECONDS', 20))

    def fetch(self) -> list[SourceRecord]:
        return []

    def get_json(self, url: str) -> Any:
        validate_public_url(url)
        response = requests.get(url, timeout=self.timeout, headers={'User-Agent': 'Forth/1.0'})
        response.raise_for_status()
        return response.json()


class GreenhouseConnector(SourceConnector):
    def fetch(self) -> list[SourceRecord]:
        board = clean_text(self.config.get('board_token') or self.config.get('board'))
        if not board:
            raise ValueError('Greenhouse sources require config.board_token.')
        validate_slug(board, 'Greenhouse board token')
        rows = self.get_json(f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true').get('jobs', [])
        company = clean_text(self.config.get('company')) or board.replace('-', ' ').title()
        return [SourceRecord(
            external_id=str(row.get('id', '')),
            title=clean_text(row.get('title')),
            company=company,
            location=clean_text((row.get('location') or {}).get('name')),
            description=_plain(row.get('content')),
            source_url=clean_text(row.get('absolute_url')),
            application_url=clean_text(row.get('absolute_url')),
            payload=row,
        ) for row in rows]


class LeverConnector(SourceConnector):
    def fetch(self) -> list[SourceRecord]:
        site = clean_text(self.config.get('site') or self.config.get('company_slug'))
        if not site:
            raise ValueError('Lever sources require config.site.')
        validate_slug(site, 'Lever site')
        rows = self.get_json(f'https://api.lever.co/v0/postings/{site}?mode=json')
        company = clean_text(self.config.get('company')) or site.replace('-', ' ').title()
        records = []
        for row in rows:
            categories = row.get('categories') or {}
            body = '\n'.join([_plain(row.get('descriptionPlain') or row.get('description'))] + [
                _plain(item.get('content')) for item in row.get('lists', [])
            ])
            records.append(SourceRecord(
                external_id=str(row.get('id', '')),
                title=clean_text(row.get('text')),
                company=company,
                location=clean_text(categories.get('location')),
                description=body,
                source_url=clean_text(row.get('hostedUrl')),
                application_url=clean_text(row.get('applyUrl') or row.get('hostedUrl')),
                payload=row,
            ))
        return records


class AshbyConnector(SourceConnector):
    def fetch(self) -> list[SourceRecord]:
        board = clean_text(self.config.get('board') or self.config.get('company_slug'))
        if not board:
            raise ValueError('Ashby sources require config.board.')
        validate_slug(board, 'Ashby board')
        rows = self.get_json(f'https://api.ashbyhq.com/posting-api/job-board/{board}').get('jobs', [])
        company = clean_text(self.config.get('company')) or board.replace('-', ' ').title()
        return [SourceRecord(
            external_id=str(row.get('id') or stable_hash(str(row.get('jobUrl', '')))[:20]),
            title=clean_text(row.get('title')),
            company=company,
            location=clean_text(row.get('location')),
            description=_plain(row.get('descriptionPlain') or row.get('descriptionHtml')),
            source_url=clean_text(row.get('jobUrl')),
            application_url=clean_text(row.get('applyUrl') or row.get('jobUrl')),
            payload=row,
        ) for row in rows]


class JobicyConnector(SourceConnector):
    """Free public remote-job feed with structured location and salary data."""

    def fetch(self) -> list[SourceRecord]:
        count = max(1, min(100, int(self.config.get('count') or 30)))
        params: dict[str, str | int] = {'count': count}
        for key in ('geo', 'industry'):
            value = clean_text(self.config.get(key)).lower()
            if value:
                validate_slug(value, f'Jobicy {key}')
                params[key] = value
        tag = clean_text(self.config.get('tag'))
        if tag:
            params['tag'] = tag[:50]
        payload = self.get_json(f'https://jobicy.com/api/v2/remote-jobs?{urlencode(params)}')
        records = []
        for row in payload.get('jobs', []):
            url = clean_text(row.get('url'))
            job_types = ', '.join(clean_text(value) for value in row.get('jobType', []) if clean_text(value))
            levels = ', '.join(clean_text(value) for value in row.get('jobLevel', []) if clean_text(value)) if isinstance(row.get('jobLevel'), list) else clean_text(row.get('jobLevel'))
            salary = ''
            if row.get('salaryMin') is not None or row.get('salaryMax') is not None:
                salary = ' '.join(str(value) for value in [row.get('salaryCurrency'), row.get('salaryMin'), '-', row.get('salaryMax'), row.get('salaryPeriod')] if value not in {None, ''})
            description = '\n'.join(value for value in [
                _plain(row.get('jobDescription') or row.get('jobExcerpt')),
                f'Employment type: {job_types}' if job_types else '',
                f'Seniority: {levels}' if levels else '',
                f'Compensation: {salary}' if salary else '',
            ] if value)
            records.append(SourceRecord(
                external_id=str(row.get('id') or row.get('jobSlug') or stable_hash(url)[:20]),
                title=clean_text(row.get('jobTitle')),
                company=clean_text(row.get('companyName')),
                location=clean_text(row.get('jobGeo')),
                description=description,
                source_url=url,
                application_url=url,
                posted_at=_source_datetime(row.get('pubDate')),
                payload={**row, '_source_attribution': 'Jobicy'},
            ))
        return records


class ArbeitnowConnector(SourceConnector):
    """Free ATS-derived Europe/UK feed with optional local relevance filtering."""

    def fetch(self) -> list[SourceRecord]:
        pages = max(1, min(5, int(self.config.get('pages') or 1)))
        max_results = max(1, min(100, int(self.config.get('max_results') or 30)))
        remote_only = bool(self.config.get('remote_only'))
        configured_keywords = self.config.get('keywords') or []
        if isinstance(configured_keywords, str):
            configured_keywords = configured_keywords.split(',')
        keywords = [clean_text(value).lower() for value in configured_keywords if clean_text(value)]
        records = []
        for page in range(1, pages + 1):
            payload = self.get_json(f'https://www.arbeitnow.com/api/job-board-api?page={page}')
            for row in payload.get('data', []):
                if remote_only and not bool(row.get('remote')):
                    continue
                haystack = ' '.join([
                    clean_text(row.get('title')),
                    clean_text(row.get('description')),
                    ' '.join(clean_text(value) for value in row.get('tags', [])),
                ]).lower()
                if keywords and not any(keyword in haystack for keyword in keywords):
                    continue
                url = clean_text(row.get('url'))
                records.append(SourceRecord(
                    external_id=clean_text(row.get('slug')) or stable_hash(url)[:20],
                    title=clean_text(row.get('title')),
                    company=clean_text(row.get('company_name')),
                    location=clean_text(row.get('location')),
                    description=_plain(row.get('description')),
                    source_url=url,
                    application_url=url,
                    posted_at=_source_datetime(row.get('created_at')),
                    payload={**row, '_source_attribution': 'Arbeitnow'},
                ))
                if len(records) >= max_results:
                    return records
        return records


class RSSConnector(SourceConnector):
    def fetch(self) -> list[SourceRecord]:
        url = clean_text(self.config.get('url'))
        if not url:
            raise ValueError('RSS sources require config.url.')
        validate_public_url(url)
        response = requests.get(url, timeout=self.timeout, headers={'User-Agent': 'Forth/1.0'})
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        records = []
        for item in root.findall('.//item'):
            field = lambda name: clean_text(item.findtext(name) or '')
            link = field('link')
            description = _plain(item.findtext('description'))
            records.append(SourceRecord(
                external_id=field('guid') or stable_hash(link)[:20],
                title=field('title'),
                company=clean_text(self.config.get('company')),
                location='',
                description=description,
                source_url=link,
                application_url=link,
                payload={'guid': field('guid')},
            ))
        return records


CONNECTORS = {
    'greenhouse': GreenhouseConnector,
    'lever': LeverConnector,
    'ashby': AshbyConnector,
    'jobicy': JobicyConnector,
    'arbeitnow': ArbeitnowConnector,
    'rss': RSSConnector,
}


def _source_datetime(value: Any) -> datetime | None:
    if value in {None, ''}:
        return None
    if isinstance(value, (int, float)) or str(value).isdigit():
        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def validate_slug(value: str, label: str) -> None:
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', value):
        raise ValueError(f'{label} contains invalid characters.')


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('Source URLs must use http or https.')
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError('The source hostname could not be resolved.') from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError('Source URLs must resolve to a public network address.')


def connector_for(source: JobSource) -> SourceConnector:
    connector_name = clean_text((source.config or {}).get('connector')).lower()
    if (source.config or {}).get('demo') and not connector_name:
        return SourceConnector(source)
    if source.kind == 'rss':
        connector_name = connector_name or 'rss'
    if source.kind == 'manual':
        return SourceConnector(source)
    connector_class = CONNECTORS.get(connector_name)
    if connector_class is None:
        raise ValueError('Choose a supported connector: greenhouse, lever, ashby, jobicy, arbeitnow, or rss.')
    return connector_class(source)


def persist_job_structure(job: JobPosting, *, source_payload: dict | None = None) -> JobPostingVersion:
    content_hash = stable_hash(job.description_text)
    current = job.versions.filter(content_hash=content_hash).first()
    if current:
        job.last_seen_at = timezone.now()
        job.freshness_status = 'fresh'
        job.save(update_fields=['last_seen_at', 'freshness_status', 'updated_at'])
        return current
    job.versions.filter(is_current=True).update(is_current=False)
    version_number = (job.versions.aggregate(value=Max('version'))['value'] or 0) + 1
    version = JobPostingVersion.objects.create(
        owner=job.owner,
        job=job,
        version=version_number,
        content_hash=content_hash,
        description_text=job.description_text,
        extracted_json=job.extracted_json,
        source_payload=source_payload or {},
        fetched_at=timezone.now(),
        is_current=True,
    )
    extracted = job.extracted_json or {}
    JobRequirement.objects.filter(job=job).delete()
    groups = [
        ('required', extracted.get('required_skills', []), 'skill', True, 90),
        ('preferred', extracted.get('preferred_skills', []), 'skill', False, 55),
        ('responsibility', extracted.get('responsibilities', []), 'responsibility', False, 45),
    ]
    for kind, values, category, is_hard, weight in groups:
        for value in values or []:
            text = clean_text(value)
            if text:
                JobRequirement.objects.create(
                    owner=job.owner, job=job, kind=kind, category=category,
                    text=text, normalized_value=text.lower()[:220], is_hard=is_hard, weight=weight,
                )
    return version


@transaction.atomic
def upsert_source_record(source: JobSource, record: SourceRecord) -> tuple[JobPosting, bool]:
    from core.services import import_job_posting

    lookup = {'owner': source.owner, 'source': source, 'source_external_id': record.external_id}
    existing = JobPosting.objects.filter(**lookup).first() if record.external_id else None
    if existing:
        from core.ai import extract_job

        extracted_result = extract_job(record.description, source_url=record.source_url)
        extracted = {**extracted_result.data, 'extractor': extracted_result.source}
        existing.title = record.title or existing.title
        existing.company = record.company or existing.company
        existing.location = record.location or existing.location
        existing.description_text = record.description or existing.description_text
        existing.source_url = record.source_url or existing.source_url
        existing.application_url = record.application_url or existing.application_url
        existing.canonical_url = record.source_url or existing.canonical_url
        existing.last_seen_at = timezone.now()
        existing.freshness_status = 'fresh'
        existing.extracted_json = extracted
        existing.save()
        persist_job_structure(existing, source_payload=record.payload)
        from core.domain.embeddings import refresh_job_embedding
        from core.domain.matching import recompute_match

        refresh_job_embedding(existing)
        recompute_match(existing)
        return existing, False

    job = import_job_posting(source.owner, text=record.description, source_url=record.source_url, source=source, score=False)
    job.title = record.title or job.title
    job.company = record.company or job.company
    job.location = record.location or job.location
    job.application_url = record.application_url or job.application_url
    job.canonical_url = record.source_url
    job.source_external_id = record.external_id
    job.posted_at = record.posted_at
    job.last_seen_at = timezone.now()
    job.save()
    persist_job_structure(job, source_payload=record.payload)
    from core.domain.embeddings import refresh_job_embedding
    from core.domain.matching import recompute_match

    refresh_job_embedding(job)
    recompute_match(job)
    return job, True


def execute_source_run(run: SourceRun) -> SourceRun:
    run.status = 'running'
    run.started_at = timezone.now()
    run.log = []
    run.save(update_fields=['status', 'started_at', 'log', 'updated_at'])
    try:
        records = connector_for(run.source).fetch()
        run.discovered_count = len(records)
        for record in records:
            try:
                _, created = upsert_source_record(run.source, record)
                if created:
                    run.imported_count += 1
                else:
                    run.updated_count += 1
            except Exception as exc:
                run.error_count += 1
                run.log.append({'level': 'error', 'message': str(exc)[:500], 'external_id': record.external_id})
        run.status = 'partial' if run.error_count else 'succeeded'
    except Exception as exc:
        run.status = 'failed'
        run.error_count += 1
        run.log.append({'level': 'error', 'message': str(exc)[:500]})
    run.completed_at = timezone.now()
    run.save()
    source = run.source
    source.last_run_at = run.completed_at
    source.last_status = run.status
    source.last_message = f'{run.imported_count} new, {run.updated_count} refreshed, {run.error_count} errors.'
    source.save(update_fields=['last_run_at', 'last_status', 'last_message', 'updated_at'])
    return run
