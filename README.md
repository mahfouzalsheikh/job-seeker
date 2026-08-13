# Forth

Your next move, fully staffed. Forth is a private, agentic career operating system for candidate intelligence, compliant sourcing, explainable matching, application operations, and evidence-backed materials.

The stack intentionally follows the sibling Drawing Algorithms project:

- Angular 21 frontend
- Django / Django REST Framework backend
- PostgreSQL
- Redis
- Celery workers and beat
- Django Channels realtime updates
- Gotenberg PDF rendering
- Docker Compose and Nginx
- OpenAI API called from the backend only

## MVP Capabilities

- Upload or paste profile material, including a canonical resume.
- Extract profile facts and verify them.
- Manually import job descriptions or job URLs.
- Extract structured job metadata.
- Compute match scores with evidence and gaps.
- Generate tailored resume drafts from verified/profile facts and canonical resume content.
- Review validation notes, weak claims, and unsupported claims.
- Export resume markdown.
- Create application records from jobs.
- Move applications through a pipeline.
- Maintain a living search brief with target roles, industries, authorization, work modes, compensation, and explicit preference strength.
- Run Greenhouse, Lever, Ashby, and RSS discovery connectors with durable source-run history.
- Review decomposed fit signals separately from hard eligibility gates.
- Collaborate with six bounded specialist workflows through the Forth Concierge.
- Approve consequential actions through a durable human-in-the-loop queue.
- Generate both resumes and cover letters, validate claims, and render final PDFs through Gotenberg.
- View strategy recommendations based on matches, profile quality, and application history.

## Product Loop

```text
Candidate evidence + explicit preferences
  -> scheduled compliant discovery
  -> freshness, versioning, normalization, and dedupe
  -> eligibility gate + decomposed fit score + citations
  -> user approves an opportunity
  -> resume + cover-letter plan and draft
  -> claim review and document approval
  -> HTML + Gotenberg PDF artifacts
  -> tracked application, follow-up, interview, and outcome
```

The specialist roles are Profile Steward, Sourcing Scout, Match Analyst, Application Coach, Document Tailor, and Forth Concierge. They are durable workflows over typed Django domain operations—not independent services with private state.

## Local Docker Run

The local `.env` file has been copied from the Drawing Algorithms project for OpenAI credentials and then narrowed to this app's runtime keys.

```bash
docker compose up --build
```

Open the app at:

```text
http://localhost:8021
```

Choose **Create your workspace** to register with an email address and password.
Forth signs you in immediately and opens the Profile Steward onboarding flow; local
development does not require email verification.

Default local admin user created by the container:

```text
username: admin
password: adminpass
```

## Demo Data

Hydrate the local app with representative demo data:

```bash
docker compose exec web python manage.py seed_demo --username admin
```

The command is idempotent for demo rows. It clears only rows tagged as demo data for the selected user, then recreates:

- profile source material
- verified and unverified profile facts
- job sources
- imported job postings
- match scores with evidence and gaps
- canonical and tailored resumes
- application pipeline records
- activity events
- markdown artifacts

## Local Development

Backend:

```bash
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Frontend:

```bash
cd frontend
npm install
npm start
```

The Angular dev server runs on `http://localhost:4200`. For full API access in development, use the Docker/Nginx entrypoint or add a local proxy configuration.

## Important Constraints

- OpenAI keys must stay in backend environment variables.
- Generated resume claims should be reviewed before use.
- Discovery is limited to manual imports and configured public ATS/RSS endpoints; the system does not bypass authentication, anti-bot controls, or site terms.
- The deterministic fallback path keeps the app usable even if OpenAI calls fail.

## Primary Experience

```text
Today
  -> review a short priority queue and due actions
Concierge
  -> ask questions, delegate bounded work, decide approvals
Opportunities
  -> inspect eligibility, score signals, evidence, and gaps
Candidate Profile
  -> maintain search brief, preferences, facts, and source evidence
Applications
  -> move through stages with versioned events and next actions
Document Studio
  -> review resume and cover letter, approve claims, render PDF bundle
```

## User Guide

The standalone, responsive guide is available in the running app at
`/forth-user-guide.html` and in the repository at
[`frontend/src/forth-user-guide.html`](frontend/src/forth-user-guide.html).

## Quality Checks

```bash
# Backend unit and integration coverage
python backend/manage.py test core.tests

# Production frontend build
npm --prefix frontend run build

# Browser journeys at desktop, tablet, and mobile sizes
npm --prefix frontend run test:e2e

# Production dependency audit
npm --prefix frontend audit --omit=dev
```

The browser suite expects the Docker stack at `http://127.0.0.1:8021` and the
local `admin` / `adminpass` account. Override the origin with `E2E_BASE_URL`.
