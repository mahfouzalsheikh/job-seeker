# Job Search Studio Proposal

Date: 2026-06-25

## Summary

Job Search Studio is a private job-search workbench that uses one canonical resume plus unstructured personal context to find suitable jobs, rank fit, customize application materials, and track application outcomes.

The application should follow the same technology direction as the sibling Drawing Algorithms project:

- Frontend: Angular 17, standalone components, Angular Router, RxJS, Angular forms
- Backend: Django, Django REST Framework, Django auth/JWT pattern, Python 3.12
- Async work: Celery, Redis, Celery Beat
- Realtime updates: Django Channels with Redis channel layer
- Data: PostgreSQL
- Deployment: Docker Compose, Nginx, Gunicorn/Daphne style service split
- AI provider: OpenAI API from the backend only
- UI style: dense operational workbench, persistent side navigation, compact cards, filters, status chips, tables, detail panes

The first version should focus on reliable data modeling and reviewable AI outputs. Resume customization must be evidence-backed: the app should not invent experience or claims that are not present in the user's source material.

## Goals

- Centralize the user's resume, experience, notes, conversations, achievements, preferences, and job-search constraints.
- Import jobs from accessible sources and manual paste/URL workflows.
- Normalize and rank jobs by semantic match, hard constraints, career goals, and application strategy.
- Generate tailored resumes and application notes from verified profile facts.
- Track applications, statuses, contacts, deadlines, follow-ups, interviews, outcomes, and artifacts.
- Use application outcomes to recommend next actions and improve the search strategy.

## Non-Goals For MVP

- Fully automated applying on behalf of the user.
- Scraping sites that prohibit scraping or require bypassing authentication, anti-bot systems, or terms of service.
- Multi-user SaaS billing, team workspaces, or marketplace features.
- Replacing human review of resume content.
- Guaranteeing job placement or interview outcomes.

## Product Principles

- Evidence first: every generated resume claim should link back to a stored source fact.
- User control: generated materials are drafts until reviewed and approved.
- Low-friction ingestion: support resume upload, pasted notes, conversations, and manual job imports.
- Explainable matching: fit scores must include reasons, gaps, and confidence.
- Operational UI: the app should feel like a serious workbench, not a marketing site.
- Compliance-first discovery: prefer official APIs, company career pages, ATS feeds, RSS, and manual import where scraping is not appropriate.

## User Personas

### Primary User

A technical job seeker who wants to apply to many roles without losing quality or consistency.

Needs:

- Keep a master resume and facts repository.
- Find jobs that are actually worth applying to.
- Tailor resumes quickly without hallucinated claims.
- Track status and follow-up timing.
- Learn which role types and resume variants are working.

### Future User

A career coach or trusted collaborator who may review application strategy and materials.

Needs:

- Read-only or comment-only access.
- Clear audit trail of generated changes.
- Ability to compare variants and outcomes.

## System Overview

```text
                         +----------------------+
                         |      Angular UI      |
                         |  Workbench + Forms   |
                         +----------+-----------+
                                    |
                                    | REST + WebSocket
                                    v
             +----------------------+----------------------+
             |              Django / DRF API               |
             | Auth, profile, jobs, resumes, applications  |
             +-----------+----------------------+-----------+
                         |                      |
                         | ORM                  | task enqueue
                         v                      v
                  +-------------+        +---------------+
                  | PostgreSQL  |        | Redis/Celery  |
                  | app data    |        | async workers |
                  +------+------+        +-------+-------+
                         |                       |
                         | vectors/metadata      | scraping, parsing,
                         |                       | embeddings, matching
                         v                       v
                  +-------------+        +---------------+
                  | Vector data |        | OpenAI API    |
                  | pgvector or |        | generation,   |
                  | equivalent  |        | embeddings    |
                  +-------------+        +---------------+
```

## Core Capabilities

### 1. Profile Knowledge Base

The app should create a structured, searchable representation of the user's background.

Inputs:

- Canonical resume upload: PDF, DOCX, Markdown, or text
- LinkedIn profile export or pasted profile text
- Freeform notes
- Chat/conversation transcripts
- Achievement logs
- Project descriptions
- Performance review snippets
- Career preferences and constraints

Stored outputs:

- Profile facts
- Skills
- Roles and responsibilities
- Projects
- Achievements
- Metrics
- Domains
- Tools and technologies
- Source snippets
- Confidence scores
- Embeddings for semantic search

Important rule:

Generated materials can only use facts that exist in the knowledge base or are explicitly added by the user during review.

### 2. Job Discovery

The app should support multiple discovery paths:

- Manual job URL import
- Paste job description
- Company career-page monitors where allowed
- ATS/job-board connectors where accessible
- RSS/API feeds where available
- Saved search configuration
- Scheduled refreshes through Celery Beat

Each imported job should be normalized into a structured record:

- Title
- Company
- Location
- Remote/hybrid/on-site
- Compensation if available
- Seniority
- Required skills
- Preferred skills
- Responsibilities
- Domain
- Recruiter/contact fields
- Source URL
- Posting age
- Application URL
- Extraction confidence

### 3. Matching And Ranking

The ranking system should combine deterministic filters and semantic scoring.

Deterministic filters:

- Location compatibility
- Remote policy
- Work authorization
- Compensation minimums
- Seniority band
- Required years of experience
- Required credentials
- Excluded companies or sectors

AI/semantic signals:

- Resume-to-job semantic similarity
- Skill overlap
- Project relevance
- Domain relevance
- Experience depth
- Leadership fit
- Growth direction fit
- Missing requirement severity
- Confidence level

The UI should expose the match explanation rather than only showing a number.

### 4. Resume Customization

Resume customization should generate structured change plans first, not directly overwrite documents.

Flow:

1. Select a job.
2. App retrieves relevant profile facts and existing resume sections.
3. Model proposes a resume tailoring plan.
4. App validates that every proposed claim is supported by source facts.
5. User reviews section diffs and warnings.
6. User accepts, edits, or rejects changes.
7. App exports PDF, DOCX, Markdown, or text.

Resume outputs:

- Tailored resume version
- Change diff against canonical resume
- Keyword coverage report
- ATS risk report
- Evidence map
- Unsupported claim report
- Exported artifacts

### 5. Application Tracker

The tracker should combine kanban-style status movement with a detailed application record.

Suggested statuses:

- Discovered
- Saved
- Resume Ready
- Applied
- Follow-Up Due
- Recruiter Screen
- Technical Screen
- Onsite / Final
- Offer
- Rejected
- Archived

Tracked data:

- Job
- Company
- Source
- Resume version used
- Cover letter or notes
- Application date
- Contacts
- Follow-up dates
- Interview dates
- Compensation notes
- Outcome
- Outcome reason
- User notes
- Generated artifacts

### 6. Strategy Advisor

The strategy layer should use application history to recommend next actions.

Examples:

- "Backend platform roles are converting better than AI product roles."
- "Your highest-match saved jobs are aging past 7 days."
- "Resume variant B has better recruiter-screen conversion."
- "You are applying to too many roles with unresolved Kubernetes gaps."
- "Follow up with these 4 contacts this week."
- "Add stronger quantified evidence for distributed systems work."

## OpenAI Usage

OpenAI should be accessed only from the Django backend. API keys should stay in backend environment variables and never reach the browser.

Recommended usage:

- Embeddings for profile facts, resume chunks, job descriptions, requirements, and match retrieval.
- Responses API for generation workflows.
- Structured Outputs for job extraction, profile extraction, resume change plans, match reports, and strategy reports.
- Batch API for bulk embedding refreshes or low-priority match recomputation.
- Background or async task handling through Celery for long-running operations.

References:

- OpenAI embeddings: https://developers.openai.com/api/docs/guides/embeddings
- OpenAI Responses API: https://developers.openai.com/api/reference/resources/responses/methods/create/
- OpenAI Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI Batch API: https://developers.openai.com/api/docs/guides/batch

## Suggested Backend Modules

```text
backend/
  manage.py
  jobsearch/
    settings.py
    urls.py
    asgi.py
    celery.py
  core/
    models.py
    serializers.py
    views.py
    tasks.py
    consumers.py
    realtime_events.py
    socket_auth.py
  profile_kb/
    ingestion.py
    parsing.py
    chunking.py
    facts.py
    embeddings.py
    evidence.py
  jobs/
    importers.py
    extractors.py
    sources.py
    dedupe.py
    scoring.py
    scrapers/
      base.py
      company_pages.py
      ats_greenhouse.py
      ats_lever.py
  resumes/
    canonical.py
    tailoring.py
    validation.py
    exports.py
    ats.py
  applications/
    workflow.py
    strategy.py
    reminders.py
  ai/
    client.py
    schemas.py
    prompts.py
    usage.py
    evals.py
```

## Suggested Frontend Structure

```text
frontend/src/app/
  app.component.ts
  app.routes.ts
  pages/
    dashboard.component.ts
    profile.component.ts
    matches.component.ts
    job-detail.component.ts
    resume-lab.component.ts
    pipeline.component.ts
    application-detail.component.ts
    sources.component.ts
    strategy.component.ts
    artifacts.component.ts
    settings.component.ts
    login.component.ts
  components/
    fit-score.component.ts
    evidence-panel.component.ts
    resume-diff.component.ts
    status-chip.component.ts
    job-import-modal.component.ts
    source-config-form.component.ts
    profile-fact-editor.component.ts
  services/
    api.service.ts
    auth.service.ts
    auth.guard.ts
    auth.interceptor.ts
    realtime.service.ts
    profile.store.ts
    matches.store.ts
    resume-lab.store.ts
    pipeline.store.ts
```

## Data Model Sketch

```text
User
  id
  email
  name

ProfileDocument
  id
  owner
  kind: resume | note | conversation | profile | project | review
  title
  raw_file
  raw_text
  metadata
  created_at

ProfileChunk
  id
  document
  text
  token_count
  embedding
  metadata

ProfileFact
  id
  owner
  fact_type: skill | achievement | role | project | metric | preference
  title
  statement
  normalized_value
  confidence
  source_document
  source_chunk
  verified_by_user

Resume
  id
  owner
  kind: canonical | tailored
  title
  content_json
  content_markdown
  parent_resume
  target_job
  created_at

ResumeClaim
  id
  resume
  text
  profile_fact
  support_status: supported | user_confirmed | unsupported

JobSource
  id
  owner
  kind: manual | company_page | ats | api | rss
  name
  config
  enabled
  last_run_at

JobPosting
  id
  owner
  source
  title
  company
  location
  remote_policy
  description_text
  extracted_json
  source_url
  application_url
  content_hash
  embedding
  posted_at
  discovered_at

JobMatch
  id
  job
  owner
  score
  hard_filter_status
  explanation_json
  missing_requirements
  supporting_facts
  confidence
  computed_at

Application
  id
  owner
  job
  status
  resume
  applied_at
  follow_up_at
  outcome
  notes
  created_at
  updated_at

ApplicationEvent
  id
  application
  event_type
  happened_at
  notes
  metadata

Artifact
  id
  owner
  application
  kind: resume_pdf | resume_docx | cover_letter | note | export
  file
  metadata
```

## API Surface Sketch

```text
Auth
  POST   /api/auth/login/
  POST   /api/auth/refresh/
  POST   /api/auth/logout/

Profile
  GET    /api/profile/documents/
  POST   /api/profile/documents/
  GET    /api/profile/facts/
  PATCH  /api/profile/facts/:id/
  POST   /api/profile/ingest/

Jobs
  GET    /api/jobs/
  POST   /api/jobs/import/
  GET    /api/jobs/:id/
  POST   /api/jobs/:id/recompute-match/

Sources
  GET    /api/sources/
  POST   /api/sources/
  PATCH  /api/sources/:id/
  POST   /api/sources/:id/run/

Matches
  GET    /api/matches/
  GET    /api/matches/:id/
  POST   /api/matches/recompute/

Resumes
  GET    /api/resumes/
  GET    /api/resumes/:id/
  POST   /api/resumes/:id/tailor/
  POST   /api/resumes/:id/export/

Applications
  GET    /api/applications/
  POST   /api/applications/
  GET    /api/applications/:id/
  PATCH  /api/applications/:id/
  POST   /api/applications/:id/events/

Strategy
  GET    /api/strategy/summary/
  POST   /api/strategy/recompute/

Realtime
  WS     /ws/realtime/
```

## Main Navigation

The app should use a persistent side nav similar to Drawing Algorithms Studio.

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Dashboard                                    |
| o Realtime connected      |                                              |
|                           | Today                                        |
| Dashboard                 | +------------+ +------------+ +------------+ |
| Profile                   | | Matches    | | Followups  | | Interviews | |
| Matches                   | | 42         | | 5          | | 3          | |
| Resume Lab                | +------------+ +------------+ +------------+ |
| Pipeline                  |                                              |
| Sources                   | Recommended Next Actions                     |
| Strategy                  | +------------------------------------------+ |
| Artifacts                 | | Apply: Senior Backend Engineer, 91 fit   | |
| Settings                  | | Customize: AI Platform Engineer          | |
|                           | | Follow up: Northstar recruiter           | |
| Logout                    | +------------------------------------------+ |
+---------------------------+----------------------------------------------+
```

## Flow 1: Onboarding And Profile Ingestion

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Profile Setup                                |
|                           |                                              |
| Dashboard                 | Step 1 of 4: Canonical Resume                |
| Profile              *    | +------------------------------------------+ |
| Matches                   | | Upload resume                             | |
| Resume Lab                | | [ Choose file ] resume.pdf                | |
| Pipeline                  | |                                          | |
| Sources                   | | Parse status: Ready                       | |
| Strategy                  | | Extracted sections: Summary, Experience, | |
|                           | | Skills, Projects, Education              | |
|                           | +------------------------------------------+ |
|                           |                                              |
|                           | [Back]                         [Continue]   |
+---------------------------+----------------------------------------------+
```

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Profile Setup                                |
|                           |                                              |
| Profile              *    | Step 2 of 4: Add Context                     |
|                           | +-------------------+ +--------------------+ |
|                           | | Paste notes       | | Upload transcript  | |
|                           | |                   | |                    | |
|                           | | Projects, wins,   | | Chat exports,      | |
|                           | | preferences, etc. | | reviews, stories   | |
|                           | +-------------------+ +--------------------+ |
|                           |                                              |
|                           | Recent sources                               |
|                           | +------------------------------------------+ |
|                           | | project_notes.md          parsed          | |
|                           | | career_preferences.txt    parsed          | |
|                           | +------------------------------------------+ |
|                           |                                              |
|                           | [Back]                         [Continue]   |
+---------------------------+----------------------------------------------+
```

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Profile Facts                                |
|                           |                                              |
| Profile              *    | Filters: [All facts] [Needs review] [Skills] |
|                           |                                              |
|                           | +------------------------------------------+ |
|                           | | Django REST Framework                     | |
|                           | | Type: Skill                               | |
|                           | | Evidence: resume.pdf, project_notes.md    | |
|                           | | Confidence: High            [Verify]      | |
|                           | +------------------------------------------+ |
|                           | +------------------------------------------+ |
|                           | | Built async pipelines with Celery/Redis   | |
|                           | | Type: Achievement                         | |
|                           | | Evidence: resume.pdf line group 4         | |
|                           | | Confidence: High            [Verify]      | |
|                           | +------------------------------------------+ |
+---------------------------+----------------------------------------------+
```

## Flow 2: Job Discovery

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Sources                                      |
|                           |                                              |
| Sources              *    | +----------------+ +-----------------------+ |
|                           | | Manual Import  | | Company Monitor       | |
|                           | | Paste URL or   | | Watch allowed career  | |
|                           | | job text       | | pages and feeds       | |
|                           | +----------------+ +-----------------------+ |
|                           |                                              |
|                           | Active Sources                               |
|                           | +------+-------------------+--------+------+ |
|                           | | On   | Source            | Last   | Jobs | |
|                           | +------+-------------------+--------+------+ |
|                           | | yes  | Greenhouse saved  | 09:10  | 18   | |
|                           | | yes  | Company pages     | 08:50  | 11   | |
|                           | | no   | RSS backend roles | Jun 22 | 44   | |
|                           | +------+-------------------+--------+------+ |
|                           |                                              |
|                           | [Add Source] [Run All Enabled]              |
+---------------------------+----------------------------------------------+
```

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Import Job                                   |
|                           |                                              |
| Sources              *    | +------------------------------------------+ |
|                           | | Source URL                                | |
|                           | | https://company.example/jobs/123          | |
|                           | |                                          | |
|                           | | Or paste description                      | |
|                           | | +--------------------------------------+ | |
|                           | | | Senior Backend Engineer...           | | |
|                           | | +--------------------------------------+ | |
|                           | |                                          | |
|                           | | [Extract Job]                            | |
|                           | +------------------------------------------+ |
|                           |                                              |
|                           | Extraction Preview                          |
|                           | +------------------------------------------+ |
|                           | | Title: Senior Backend Engineer           | |
|                           | | Company: Acme                            | |
|                           | | Remote: Canada/US                        | |
|                           | | Required: Python, Django, Postgres       | |
|                           | | Confidence: High                         | |
|                           | +------------------------------------------+ |
|                           |                                              |
|                           | [Cancel]                         [Save Job] |
+---------------------------+----------------------------------------------+
```

## Flow 3: Match Review

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Matches                                      |
|                           |                                              |
| Matches              *    | Filters                                      |
|                           | [Remote] [Backend] [Score >= 75] [New only] |
|                           |                                              |
|                           | +-----------------------------+------------+ |
|                           | | Job                         | Fit        | |
|                           | +-----------------------------+------------+ |
|                           | | Senior Backend Engineer     | 91 High    | |
|                           | | AI Platform Engineer        | 86 High    | |
|                           | | Platform API Lead           | 82 Medium  | |
|                           | | Data Engineer               | 64 Low     | |
|                           | +-----------------------------+------------+ |
|                           |                                              |
|                           | Selected: Senior Backend Engineer            |
|                           | +------------------------------------------+ |
|                           | | Fit score: 91                             | |
|                           | | Strong evidence:                          | |
|                           | | - Django/DRF production work              | |
|                           | | - Celery/Redis async systems              | |
|                           | | - OpenAI API integration                  | |
|                           | |                                          | |
|                           | | Gaps:                                     | |
|                           | | - Kubernetes not explicit in resume       | |
|                           | | - No recent pgvector mention              | |
|                           | |                                          | |
|                           | | [Customize Resume] [Save] [Reject]        | |
|                           | +------------------------------------------+ |
+---------------------------+----------------------------------------------+
```

## Flow 4: Resume Lab

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Resume Lab                                   |
|                           |                                              |
| Resume Lab           *    | Target Job: Senior Backend Engineer, Acme    |
|                           |                                              |
|                           | +----------------+-------------------------+ |
|                           | | Requirement    | Resume Evidence         | |
|                           | +----------------+-------------------------+ |
|                           | | Django/DRF     | Supported: resume, note  | |
|                           | | Celery/Redis   | Supported: resume        | |
|                           | | OpenAI APIs    | Supported: project note  | |
|                           | | Kubernetes     | Weak evidence            | |
|                           | +----------------+-------------------------+ |
|                           |                                              |
|                           | Tailoring Plan                               |
|                           | +------------------------------------------+ |
|                           | | Summary: emphasize backend platform work  | |
|                           | | Experience: move async systems bullet up  | |
|                           | | Skills: add OpenAI API if user approves   | |
|                           | | Risk: Kubernetes claim unsupported        | |
|                           | +------------------------------------------+ |
|                           |                                              |
|                           | [Generate Draft] [Edit Plan] [Cancel]       |
+---------------------------+----------------------------------------------+
```

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Resume Draft Review                          |
|                           |                                              |
| Resume Lab           *    | +----------------------+-------------------+ |
|                           | | Canonical Resume     | Tailored Draft    | |
|                           | +----------------------+-------------------+ |
|                           | | Backend engineer...  | Backend engineer  | |
|                           | | Built APIs...        | Built Django/DRF  | |
|                           | | Celery pipelines...  | Celery/Redis...   | |
|                           | +----------------------+-------------------+ |
|                           |                                              |
|                           | Validation                                   |
|                           | +------------------------------------------+ |
|                           | | Required keywords: 18 / 22                | |
|                           | | Unsupported claims: 0                     | |
|                           | | Weak claims: 1                            | |
|                           | | Length: 1 page                            | |
|                           | | ATS risk: Low                             | |
|                           | +------------------------------------------+ |
|                           |                                              |
|                           | [Accept Draft] [Export PDF] [Export DOCX]   |
+---------------------------+----------------------------------------------+
```

## Flow 5: Application Pipeline

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Pipeline                                     |
|                           |                                              |
| Pipeline             *    | +------------+------------+------------+---+ |
|                           | | Saved      | Resume     | Applied    |   | |
|                           | |            | Ready      |            |   | |
|                           | +------------+------------+------------+---+ |
|                           | | Acme       | Northstar  | Stripe     |   | |
|                           | | Orbit      | VectorLab  | Shopify    |   | |
|                           | | Helio      |            | Datadog    |   | |
|                           | +------------+------------+------------+---+ |
|                           | | Follow-Up  | Recruiter  | Interview  |   | |
|                           | | Due        | Screen     |            |   | |
|                           | +------------+------------+------------+---+ |
|                           | | Pine       | OpenAI     | Anthropic  |   | |
|                           | | Wave       | Render     | GitHub     |   | |
|                           | +------------+------------+------------+---+ |
+---------------------------+----------------------------------------------+
```

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Application Detail                           |
|                           |                                              |
| Pipeline             *    | Senior Backend Engineer, Acme                |
|                           | Status: Applied                              |
|                           |                                              |
|                           | +----------------------+-------------------+ |
|                           | | Job Info             | Activity          | |
|                           | | Fit: 91              | Jun 25 Applied    | |
|                           | | Source: Company page | Jun 24 Resume out | |
|                           | | Remote: Canada/US    | Jun 24 Saved      | |
|                           | +----------------------+-------------------+ |
|                           |                                              |
|                           | Artifacts                                    |
|                           | +------------------------------------------+ |
|                           | | acme_backend_resume.pdf                   | |
|                           | | acme_application_notes.md                 | |
|                           | +------------------------------------------+ |
|                           |                                              |
|                           | [Move Status] [Add Note] [Schedule Followup] |
+---------------------------+----------------------------------------------+
```

## Flow 6: Strategy Advisor

```text
+---------------------------+----------------------------------------------+
| Job Search Studio         | Strategy                                     |
|                           |                                              |
| Strategy             *    | Search Health                                |
|                           | +------------+------------+----------------+ |
|                           | | Apply rate | Response   | Interview rate | |
|                           | | 11 / week  | 18%        | 6%             | |
|                           | +------------+------------+----------------+ |
|                           |                                              |
|                           | Recommendations                              |
|                           | +------------------------------------------+ |
|                           | | 1. Prioritize backend platform roles.     | |
|                           | |    They have the strongest match and best | |
|                           | |    response rate so far.                  | |
|                           | |                                          | |
|                           | | 2. Add quantified evidence for scale.     | |
|                           | |    7 high-fit jobs ask for distributed    | |
|                           | |    systems depth.                         | |
|                           | |                                          | |
|                           | | 3. Follow up on 5 applications this week. | |
|                           | +------------------------------------------+ |
|                           |                                              |
|                           | [Refresh Strategy] [Create Tasks]           |
+---------------------------+----------------------------------------------+
```

## Realtime Events

Use Channels to keep the UI updated while background jobs run.

Events:

- profile_ingestion_started
- profile_ingestion_progress
- profile_ingestion_finished
- source_run_started
- source_run_progress
- source_run_finished
- job_extracted
- match_recomputed
- resume_tailoring_started
- resume_tailoring_finished
- application_updated
- strategy_recomputed

Example event:

```json
{
  "type": "match_recomputed",
  "job_id": 42,
  "match_id": 108,
  "score": 91,
  "confidence": "high"
}
```

## AI Validation Requirements

### Job Extraction Schema

The model should return structured job data with required fields and confidence values.

Required fields:

- title
- company
- location
- remote_policy
- responsibilities
- required_skills
- preferred_skills
- seniority
- compensation
- application_url
- confidence

### Resume Tailoring Schema

The model should return a change plan before producing a final resume.

Required fields:

- summary_changes
- experience_changes
- skills_changes
- project_changes
- keyword_coverage
- unsupported_claims
- weak_claims
- evidence_links
- risk_notes

### Guardrails

- Reject unsupported claims by default.
- Mark weakly supported claims for user review.
- Do not fabricate company names, metrics, dates, titles, certifications, or technologies.
- Do not change canonical resume without explicit user action.
- Store all generation inputs, outputs, schema validation results, and cost metadata.

## Scraping And Source Requirements

The source system should be conservative.

Rules:

- Respect robots.txt where applicable.
- Respect site terms and rate limits.
- Prefer official APIs and ATS feeds.
- Support manual import for restricted sites.
- Store source URL and extraction timestamp.
- Dedupe by canonical URL, normalized title/company, and content hash.
- Record source failures and warnings.
- Let the user disable sources.

Initial source targets:

- Manual paste/import
- Company career pages where allowed
- Greenhouse job board pages
- Lever job board pages
- RSS feeds
- User-maintained URL lists

## Search And Matching Requirements

The app should support:

- Keyword search
- Semantic search
- Filters by score, source, company, seniority, location, remote policy, compensation, and status
- Exclusion lists
- Saved searches
- Match refresh when profile facts change
- Match refresh when jobs are updated

Recommended scoring shape:

```text
Final score =
  hard constraint gate
  + semantic similarity
  + required skill coverage
  + seniority fit
  + domain fit
  + preference fit
  - missing critical requirements
  - weak evidence penalties
```

## Artifact Requirements

Generated artifacts:

- Tailored resume PDF
- Tailored resume DOCX
- Tailored resume Markdown
- Cover letter draft
- Recruiter message draft
- Interview prep notes
- Application notes
- Strategy report

Artifact metadata:

- Target job
- Resume version
- Source facts used
- Generation model
- Prompt version
- Created timestamp
- User approval state

## Security And Privacy

- Keep OpenAI API keys only in backend environment variables.
- Never expose raw API prompts or keys to the browser.
- Store uploaded documents privately.
- Avoid logging full resume text in application logs.
- Add retention controls for documents, jobs, generated outputs, and AI logs.
- Add export/delete account flows before any broader deployment.
- Limit source connector credentials and encrypt secrets at rest if external accounts are added.

## Observability

Track:

- Task durations
- Source run failures
- Extraction confidence
- Match recomputation counts
- AI token/cost usage
- Schema validation failures
- Resume unsupported-claim counts
- Application conversion rates
- Follow-up completion rates

## MVP Release Plan

### Phase 1: Foundation

- Django project, Angular project, Docker Compose
- Auth
- Persistent side nav shell
- Profile document upload
- Resume text extraction
- Profile fact extraction
- Basic REST API
- Realtime task progress

### Phase 2: Jobs And Matching

- Manual job import
- Job extraction
- Job list and detail pages
- Embeddings for profile chunks and job postings
- Initial match scoring
- Match explanation panel

### Phase 3: Resume Lab

- Canonical resume editor/viewer
- Tailoring plan generation
- Evidence validation
- Diff review
- PDF/DOCX/Markdown export
- Artifact storage

### Phase 4: Application Tracker

- Application records
- Pipeline board
- Status changes
- Events and notes
- Follow-up dates
- Artifact linking

### Phase 5: Sources And Strategy

- Source configuration
- Scheduled imports
- Dedupe
- Strategy dashboard
- Outcome analytics
- Recommended next actions

## Acceptance Criteria For MVP

- User can upload a canonical resume and verify extracted profile facts.
- User can import a job manually from text or URL.
- App computes a match score with a readable explanation.
- User can generate a tailored resume draft for a job.
- Draft includes evidence links and flags unsupported claims.
- User can export a reviewed resume.
- User can create an application record from a job.
- User can move the application through statuses.
- Realtime progress appears during ingestion, matching, and resume generation.
- All OpenAI calls happen from the backend.

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Hallucinated resume claims | Evidence-backed claim validation, unsupported-claim blocking |
| Scraping restrictions | Prefer APIs/manual imports, per-source compliance controls |
| Poor match explanations | Store structured explanations, show evidence and gaps |
| Slow bulk processing | Celery workers, batch jobs, cached embeddings |
| Cost growth | Usage logging, model tiers, batch processing, limits |
| Sensitive data exposure | Backend-only OpenAI calls, private storage, minimal logging |
| Resume formatting complexity | Start with Markdown/PDF templates before complex designer features |

## Open Questions

- Should the canonical resume be stored as structured JSON, Markdown, or both?
- Which export formats are required first: PDF, DOCX, Markdown, plain text?
- Which job sources are highest priority for the first scraper/connectors?
- Should profile facts require manual verification before they can be used in generated resumes?
- Should there be separate resume variants for different target role families?
- Should the app track networking contacts separately from applications?

## Recommended MVP Scope

Build the smallest complete loop first:

```text
Upload resume
  -> extract and verify facts
  -> import job manually
  -> compute match
  -> generate tailored resume draft
  -> review evidence and diff
  -> export artifact
  -> create application
  -> track outcome
  -> use outcome in strategy
```

After that loop works, add scheduled sources and broader automation.

