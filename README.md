# Job Search Studio

Private job-search workbench for profile ingestion, job matching, resume tailoring, application tracking, and strategy feedback.

The stack intentionally follows the sibling Drawing Algorithms project:

- Angular 17 frontend
- Django / Django REST Framework backend
- PostgreSQL
- Redis
- Celery workers and beat
- Django Channels realtime updates
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
- View strategy recommendations based on matches, profile quality, and application history.

## Local Docker Run

The local `.env` file has been copied from the Drawing Algorithms project for OpenAI credentials and then narrowed to this app's runtime keys.

```bash
docker compose up --build
```

Open the app at:

```text
http://localhost:8021
```

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
- Scraping is not automated in the MVP beyond source records and task hooks. Manual job import is implemented first to avoid compliance issues.
- The deterministic fallback path keeps the app usable even if OpenAI calls fail.

## Current MVP Loop

```text
Profile
  -> add resume or notes
  -> extract facts
  -> verify facts

Matches
  -> paste job description
  -> extract job
  -> compute score
  -> review gaps and evidence

Resume Lab
  -> generate tailored draft
  -> review validation
  -> approve/export markdown

Pipeline
  -> create application
  -> update status and follow-up

Strategy
  -> review next-action guidance
```
