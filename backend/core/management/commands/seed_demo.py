from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.ai import cosine_similarity, detect_skills, heuristic_embedding, keywords, stable_hash
from core.models import (
    Application,
    ApplicationEvent,
    Artifact,
    CandidatePreference,
    CandidateProfile,
    ConversationMessage,
    ConversationThread,
    JobMatch,
    JobPosting,
    JobSource,
    ProfileChunk,
    ProfileDocument,
    ProfileFact,
    Resume,
)


DEMO_META = {'demo': True}


class Command(BaseCommand):
    help = 'Seed demo data for Forth without making OpenAI API calls.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin')

    @transaction.atomic
    def handle(self, *args, **options):
        username = options['username']
        user = self.ensure_user(username)
        self.clear_demo_data(user)
        self.create_candidate_context(user)
        sources = self.create_sources(user)
        document = self.create_profile(user)
        facts = list(ProfileFact.objects.filter(owner=user, metadata__demo=True))
        canonical = self.create_canonical_resume(user, document)
        jobs = self.create_jobs(user, sources)
        from core.domain.matching import recompute_match

        matches = [recompute_match(job) for job in jobs]
        resumes = self.create_tailored_resumes(user, canonical, jobs)
        self.create_applications(user, jobs, resumes)
        self.create_artifacts(user, resumes)
        self.create_concierge(user)
        self.stdout.write(self.style.SUCCESS(
            f'Seeded demo data for {username}: '
            f'{len(facts)} facts, {len(jobs)} jobs, {len(matches)} matches, {len(resumes) + 1} resumes.'
        ))

    def ensure_user(self, username: str):
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user:
            return user
        return User.objects.create_superuser(
            username=username,
            email=f'{username}@example.com',
            password='adminpass',
        )

    def clear_demo_data(self, user) -> None:
        ConversationThread.objects.filter(owner=user, context__demo=True).delete()
        CandidatePreference.objects.filter(owner=user, rationale__contains='[demo]').delete()
        Artifact.objects.filter(owner=user, metadata__demo=True).delete()
        ApplicationEvent.objects.filter(owner=user, metadata__demo=True).delete()
        Application.objects.filter(owner=user, notes__contains='[demo]').delete()
        Resume.objects.filter(owner=user, content_json__demo=True).delete()
        JobMatch.objects.filter(owner=user, explanation_json__demo=True).delete()
        JobPosting.objects.filter(owner=user, extracted_json__demo=True).delete()
        ProfileFact.objects.filter(owner=user, metadata__demo=True).delete()
        ProfileChunk.objects.filter(owner=user, metadata__demo=True).delete()
        ProfileDocument.objects.filter(owner=user, metadata__demo=True).delete()
        JobSource.objects.filter(owner=user, config__demo=True).delete()

    def create_candidate_context(self, user) -> None:
        CandidateProfile.objects.update_or_create(
            owner=user,
            defaults={
                'headline': 'Senior backend and AI platform engineer',
                'professional_summary': 'Product-minded platform engineer who builds dependable APIs, asynchronous workflows, and reviewable AI systems.',
                'target_roles': ['Staff Platform Engineer', 'Senior Backend Engineer', 'Product Engineer'],
                'target_industries': ['Developer tools', 'AI platforms', 'Workflow automation'],
                'location': 'Toronto, Canada',
                'authorized_countries': ['Canada'],
                'work_modes': ['remote', 'hybrid'],
                'employment_types': ['full-time'],
                'minimum_compensation': 150000,
                'compensation_currency': 'CAD',
                'excluded_companies': [],
                'completeness': 90,
                'last_reviewed_at': timezone.now(),
            },
        )
        rows = [
            ('role', 'Hands-on technical work', 'must'),
            ('work_mode', 'Remote or hybrid', 'strong'),
            ('culture', 'Strong engineering practices', 'strong'),
            ('role', 'Pure people management', 'avoid'),
        ]
        for category, label, importance in rows:
            CandidatePreference.objects.create(
                owner=user, category=category, label=label, importance=importance,
                value={'label': label}, verified_by_user=True, rationale='Seeded for the demo journey. [demo]',
            )

    def create_sources(self, user) -> dict[str, JobSource]:
        now = timezone.now()
        rows = [
            ('manual', 'Manual Imports', {'demo': True, 'description': 'Pasted job descriptions and URLs'}),
            ('ats', 'Greenhouse Watchlist', {'demo': True, 'provider': 'greenhouse', 'query': 'backend platform'}),
            ('company_page', 'Target Company Pages', {'demo': True, 'companies': ['Northstar', 'VectorLab', 'Atlas Cloud']}),
            ('rss', 'Remote Backend RSS', {'demo': True, 'keywords': ['django', 'platform', 'ai']}),
        ]
        result = {}
        for kind, name, config in rows:
            source = JobSource.objects.create(
                owner=user,
                kind=kind,
                name=name,
                config=config,
                enabled=True,
                last_run_at=now - timedelta(hours=len(result) + 1),
                last_status='success',
                last_message='Demo source seeded with representative jobs.',
            )
            result[name] = source
        return result

    def create_profile(self, user) -> ProfileDocument:
        raw_text = """Senior backend and AI platform engineer with 10+ years building production systems.

Built Django REST Framework APIs backed by PostgreSQL, Redis, Celery, and Docker for high-volume internal tools.
Integrated OpenAI APIs, embeddings, structured extraction, and retrieval workflows into product features.
Led migration of legacy synchronous workflows to async Celery pipelines, reducing manual operations and improving reliability.
Designed Angular operational dashboards for non-technical users with dense filters, status chips, and realtime task progress.
Owned observability work using structured logs, metrics, incident review, and pragmatic production runbooks.
Collaborated with product, design, and operations teams to ship data-heavy applications with clear review flows.
Prefers remote or hybrid backend/platform roles in Canada or US time zones with strong engineering practices.
"""
        document = ProfileDocument.objects.create(
            owner=user,
            kind='resume',
            title='Demo Canonical Resume Source',
            raw_text=raw_text,
            status='ready',
            status_message='Demo source material loaded.',
            metadata=DEMO_META,
        )
        chunk = ProfileChunk.objects.create(
            owner=user,
            document=document,
            text=raw_text,
            token_count=len(raw_text.split()),
            embedding=heuristic_embedding(raw_text),
            metadata={**DEMO_META, 'index': 0},
        )
        fact_rows = [
            ('skill', 'Python', 'Production Python backend development across APIs, automation, and data-heavy services.', 'high', True),
            ('skill', 'Django REST Framework', 'Built and maintained Django REST Framework APIs for operational products.', 'high', True),
            ('skill', 'PostgreSQL', 'Designed relational models, filters, and reporting queries on PostgreSQL-backed systems.', 'high', True),
            ('skill', 'Redis and Celery', 'Built async task workflows with Redis and Celery for long-running background work.', 'high', True),
            ('skill', 'OpenAI API', 'Integrated OpenAI APIs for extraction, generation, embeddings, and reviewable AI workflows.', 'high', True),
            ('skill', 'Angular', 'Built Angular workbench interfaces with filters, cards, detail panes, and realtime status.', 'medium', True),
            ('achievement', 'Async Pipeline Migration', 'Led migration from synchronous operations to Celery-backed async pipelines with progress tracking.', 'high', True),
            ('achievement', 'AI Review Workflow', 'Designed AI-assisted workflows where generated output is reviewed, validated, and linked to source evidence.', 'high', True),
            ('achievement', 'Operational Dashboard UX', 'Created dense dashboards for repeated operational workflows instead of marketing-style pages.', 'medium', True),
            ('achievement', 'Production Reliability', 'Improved reliability through structured logging, status tracking, and pragmatic recovery flows.', 'medium', False),
            ('preference', 'Remote Backend Platform Roles', 'Prefers remote or hybrid backend/platform roles aligned with Canada or US time zones.', 'high', True),
            ('constraint', 'Evidence-Backed Resume Claims', 'Resume content should avoid unsupported claims and preserve source evidence.', 'high', True),
        ]
        for fact_type, title, statement, confidence, verified in fact_rows:
            ProfileFact.objects.create(
                owner=user,
                fact_type=fact_type,
                title=title,
                statement=statement,
                confidence=confidence,
                source_document=document,
                source_chunk=chunk,
                verified_by_user=verified,
                lifecycle='verified' if verified else 'proposed',
                evidence_quote=statement,
                embedding=heuristic_embedding(f'{title}\n{statement}'),
                metadata=DEMO_META,
            )
        return document

    def create_canonical_resume(self, user, document: ProfileDocument) -> Resume:
        content = """# Demo Candidate

## Summary

Senior backend and AI platform engineer focused on Django, Python, async systems, and reviewable AI workflows.

## Experience

### Backend / Platform Engineer

- Built Django REST Framework APIs backed by PostgreSQL, Redis, Celery, and Docker.
- Integrated OpenAI APIs for structured extraction, generation, embeddings, and retrieval workflows.
- Led migration of operational workflows to background task pipelines with realtime status visibility.
- Designed dense Angular workbench interfaces for repeated operational workflows.

## Skills

Python, Django REST Framework, PostgreSQL, Redis, Celery, Docker, Angular, OpenAI API, embeddings, operational dashboards
"""
        return Resume.objects.create(
            owner=user,
            kind='canonical',
            title='Demo Canonical Resume',
            content_markdown=content,
            content_json={**DEMO_META, 'source_document_id': document.id},
            validation={'demo': True, 'risk_notes': []},
            approved=True,
        )

    def create_jobs(self, user, sources: dict[str, JobSource]) -> list[JobPosting]:
        job_rows = [
            {
                'source': sources['Greenhouse Watchlist'],
                'title': 'Senior Backend Engineer, AI Platform',
                'company': 'Northstar Systems',
                'location': 'Remote - Canada / US',
                'remote_policy': 'remote',
                'seniority': 'Senior',
                'compensation': '$165k - $205k CAD',
                'status': 'saved',
                'source_url': 'https://example.com/northstar/backend-ai-platform',
                'text': """Senior Backend Engineer for an AI platform team. Requirements include Python, Django REST Framework, PostgreSQL, Redis, Celery, Docker, OpenAI API integrations, embeddings, structured extraction, and building reliable async workflows. Angular experience is a plus. Remote Canada or US time zones.""",
                'required_skills': ['Python', 'Django REST Framework', 'PostgreSQL', 'Redis', 'Celery', 'OpenAI API'],
                'preferred_skills': ['Angular', 'embeddings', 'Docker'],
            },
            {
                'source': sources['Target Company Pages'],
                'title': 'Staff Platform Engineer',
                'company': 'VectorLab',
                'location': 'Toronto / Remote Hybrid',
                'remote_policy': 'hybrid',
                'seniority': 'Staff',
                'compensation': '$180k - $230k CAD',
                'status': 'new',
                'source_url': 'https://example.com/vectorlab/staff-platform',
                'text': """Staff Platform Engineer to lead backend architecture, reliability, internal developer platforms, observability, and high-scale APIs. The role values Python, PostgreSQL, Redis, distributed systems, Kubernetes, Terraform, and mentoring engineers.""",
                'required_skills': ['Python', 'PostgreSQL', 'Redis', 'distributed systems', 'observability'],
                'preferred_skills': ['Kubernetes', 'Terraform'],
            },
            {
                'source': sources['Manual Imports'],
                'title': 'Product Engineer, Workflow Automation',
                'company': 'Atlas Cloud',
                'location': 'Remote',
                'remote_policy': 'remote',
                'seniority': 'Senior',
                'compensation': '$150k - $190k CAD',
                'status': 'saved',
                'source_url': 'https://example.com/atlas/workflow-automation',
                'text': """Product Engineer for workflow automation tools. Build Angular interfaces, Django APIs, background jobs, user-facing review flows, and integrations with LLM providers. Strong product sense and operational UX experience required.""",
                'required_skills': ['Angular', 'Django', 'Celery', 'LLM', 'API'],
                'preferred_skills': ['OpenAI', 'workflow automation'],
            },
            {
                'source': sources['Remote Backend RSS'],
                'title': 'Data Platform Engineer',
                'company': 'Mercury Retail',
                'location': 'New York',
                'remote_policy': 'onsite',
                'seniority': 'Senior',
                'compensation': '$170k - $210k USD',
                'status': 'new',
                'source_url': 'https://example.com/mercury/data-platform',
                'text': """Data Platform Engineer requiring Spark, Airflow, dbt, warehouse modeling, Python, Kubernetes, and on-site collaboration in New York. Backend API experience is helpful but not the primary focus.""",
                'required_skills': ['Python', 'Kubernetes', 'Airflow', 'dbt', 'Spark'],
                'preferred_skills': ['backend APIs'],
            },
            {
                'source': sources['Greenhouse Watchlist'],
                'title': 'Backend API Lead',
                'company': 'Helio Health',
                'location': 'Remote - Canada',
                'remote_policy': 'remote',
                'seniority': 'Lead',
                'compensation': '$155k - $195k CAD',
                'status': 'new',
                'source_url': 'https://example.com/helio/backend-api-lead',
                'text': """Backend API Lead to own Django services, API design, PostgreSQL schemas, Redis caching, Celery jobs, security reviews, and engineering delivery for a healthcare operations product.""",
                'required_skills': ['Django', 'API', 'PostgreSQL', 'Redis', 'Celery', 'security'],
                'preferred_skills': ['healthcare operations'],
            },
        ]
        jobs = []
        for row in job_rows:
            extracted = {
                'demo': True,
                'title': row['title'],
                'company': row['company'],
                'location': row['location'],
                'remote_policy': row['remote_policy'],
                'seniority': row['seniority'],
                'compensation': row['compensation'],
                'application_url': row['source_url'],
                'responsibilities': [line.strip() for line in row['text'].split('.') if line.strip()][:4],
                'required_skills': row['required_skills'],
                'preferred_skills': row['preferred_skills'],
                'confidence': 'high',
            }
            job = JobPosting.objects.create(
                owner=user,
                source=row['source'],
                title=row['title'],
                company=row['company'],
                location=row['location'],
                remote_policy=row['remote_policy'],
                seniority=row['seniority'],
                compensation=row['compensation'],
                description_text=row['text'],
                extracted_json=extracted,
                source_url=row['source_url'],
                application_url=row['source_url'],
                content_hash=stable_hash(f'demo:{user.pk}:{row["source_url"]}'),
                embedding=heuristic_embedding(row['text']),
                status=row['status'],
                discovered_at=timezone.now() - timedelta(days=len(jobs)),
            )
            jobs.append(job)
        return jobs

    def create_match(self, user, job: JobPosting, facts: list[ProfileFact]) -> JobMatch:
        fact_text = '\n'.join(f'{fact.title}: {fact.statement}' for fact in facts)
        semantic = (cosine_similarity(heuristic_embedding(fact_text), job.embedding) + 1) / 2
        job_skills = job.extracted_json.get('required_skills') or detect_skills(job.description_text)
        profile_text = fact_text.lower()
        covered = [skill for skill in job_skills if skill.lower() in profile_text]
        missing = [skill for skill in job_skills if skill not in covered]
        lexical = len(set(keywords(job.description_text)) & set(keywords(fact_text))) / max(1, len(set(keywords(job.description_text))))
        skill_score = len(covered) / max(1, len(job_skills))
        score = round((semantic * 35) + (skill_score * 45) + (lexical * 20))
        if job.remote_policy == 'remote':
            score += 4
        if job.remote_policy == 'onsite':
            score -= 12
        score = max(28, min(96, score))
        supporting = []
        for fact in facts:
            overlap = [skill for skill in covered if skill.lower() in f'{fact.title} {fact.statement}'.lower()]
            if overlap:
                supporting.append({
                    'fact_id': fact.id,
                    'title': fact.title,
                    'statement': fact.statement,
                    'skills': overlap,
                })
            if len(supporting) >= 6:
                break
        confidence = 'high' if score >= 80 else 'medium' if score >= 60 else 'low'
        return JobMatch.objects.create(
            owner=user,
            job=job,
            score=score,
            hard_filter_status='pass' if job.remote_policy != 'onsite' else 'review',
            explanation_json={
                'demo': True,
                'semantic_score': round(semantic, 3),
                'skill_score': round(skill_score, 3),
                'lexical_score': round(lexical, 3),
                'covered_skills': covered,
                'job_skills': job_skills,
                'summary': self.match_summary(score, covered, missing, job.remote_policy),
            },
            missing_requirements=missing,
            supporting_facts=supporting,
            confidence=confidence,
        )

    def match_summary(self, score: int, covered: list[str], missing: list[str], remote_policy: str) -> str:
        fit = 'Strong match' if score >= 80 else 'Possible match' if score >= 60 else 'Weak match'
        location = ' Remote policy is favorable.' if remote_policy == 'remote' else ' Location needs review.' if remote_policy == 'onsite' else ''
        return f'{fit}: {len(covered)} key requirements supported, {len(missing)} visible gaps.{location}'

    def create_tailored_resumes(self, user, canonical: Resume, jobs: list[JobPosting]) -> list[Resume]:
        selected_jobs = jobs[:3]
        resumes = []
        for job in selected_jobs:
            skills = job.extracted_json.get('required_skills', [])
            markdown = f"""# Demo Candidate

## Targeted Summary

Senior backend engineer positioned for {job.title} at {job.company}, emphasizing {', '.join(skills[:4])}.

## Relevant Experience

- Built Django REST Framework APIs backed by PostgreSQL, Redis, Celery, and Docker.
- Integrated OpenAI APIs and embeddings into reviewable, evidence-backed workflows.
- Designed Angular operational dashboards with dense filters, status chips, and realtime task progress.
- Led async workflow improvements that made long-running operations easier to monitor and recover.

## Skills Matched To Role

{', '.join(skills)}
"""
            unsupported = ['Kubernetes leadership'] if 'Kubernetes' in skills else []
            weak = [skill for skill in skills if skill.lower() in {'kubernetes', 'terraform', 'spark', 'dbt'}]
            resume = Resume.objects.create(
                owner=user,
                kind='tailored',
                title=f'{job.company} - {job.title}',
                content_markdown=markdown,
                content_json={**DEMO_META, 'target_job_id': job.id},
                parent_resume=canonical,
                target_job=job,
                validation={
                    'generator': 'demo_seed',
                    'summary_changes': [
                        'Reordered summary toward backend platform and AI workflow evidence.',
                        'Highlighted async systems and reviewable AI integrations.',
                    ],
                    'keyword_coverage': [skill for skill in skills if skill not in weak],
                    'unsupported_claims': unsupported,
                    'weak_claims': weak,
                    'evidence_links': ['Django REST Framework', 'Redis and Celery', 'OpenAI API', 'Operational Dashboard UX'],
                    'risk_notes': ['Demo draft for review; do not submit without editing personal details.'],
                },
                approved=job == selected_jobs[0],
            )
            resumes.append(resume)
        return resumes

    def create_applications(self, user, jobs: list[JobPosting], resumes: list[Resume]) -> None:
        now = timezone.now()
        rows = [
            (jobs[0], resumes[0], 'applied', now - timedelta(days=2), now + timedelta(days=4), 'Applied with tailored AI platform resume. [demo]', 'Maya Chen', 'maya@example.com'),
            (jobs[1], resumes[1], 'resume_ready', None, now + timedelta(days=1), 'Resume draft needs Kubernetes wording review. [demo]', '', ''),
            (jobs[2], resumes[2], 'recruiter_screen', now - timedelta(days=8), now + timedelta(days=2), 'Recruiter screen booked; prepare workflow automation stories. [demo]', 'Sam Patel', 'sam@example.com'),
            (jobs[4], None, 'saved', None, None, 'Looks strong for API leadership; tailor resume next. [demo]', '', ''),
            (jobs[3], None, 'rejected', now - timedelta(days=14), None, 'Archived because onsite data-platform focus is weak fit. [demo]', '', ''),
        ]
        for index, (job, resume, status, applied_at, follow_up_at, notes, contact_name, contact_email) in enumerate(rows):
            app = Application.objects.create(
                owner=user,
                job=job,
                resume=resume,
                status=status,
                applied_at=applied_at,
                follow_up_at=follow_up_at,
                notes=notes,
                contact_name=contact_name,
                contact_email=contact_email,
            )
            events = [
                ('created', now - timedelta(days=10 - index), f'Demo application created for {job.company}.'),
                ('status_changed', now - timedelta(days=8 - index), f'Status set to {status}.'),
            ]
            if status in {'applied', 'recruiter_screen', 'rejected'}:
                events.append(('outcome_note', now - timedelta(days=3 - index), notes.replace(' [demo]', '')))
            for event_type, happened_at, event_notes in events:
                ApplicationEvent.objects.create(
                    owner=user,
                    application=app,
                    event_type=event_type,
                    happened_at=happened_at,
                    notes=event_notes,
                    metadata=DEMO_META,
                )

    def create_artifacts(self, user, resumes: list[Resume]) -> None:
        for resume in resumes:
            Artifact.objects.create(
                owner=user,
                resume=resume,
                kind='resume_markdown',
                title=f'{resume.title} Markdown Export',
                content_text=resume.content_markdown,
                metadata={**DEMO_META, 'source': 'seed_demo'},
            )

    def create_concierge(self, user) -> None:
        thread = ConversationThread.objects.create(
            owner=user, title='Forth concierge', context=DEMO_META,
        )
        ConversationMessage.objects.create(
            owner=user,
            thread=thread,
            role='assistant',
            content='I found several promising roles and ranked them against your verified evidence. The strongest opportunities are ready for review.',
            metadata={'agent': 'concierge', **DEMO_META},
        )
