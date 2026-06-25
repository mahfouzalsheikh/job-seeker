from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings


SKILL_HINTS = [
    'python', 'django', 'django rest framework', 'drf', 'fastapi', 'flask',
    'postgres', 'postgresql', 'mysql', 'sqlite', 'redis', 'celery', 'rabbitmq',
    'aws', 'gcp', 'azure', 'docker', 'kubernetes', 'terraform', 'linux',
    'openai', 'llm', 'embeddings', 'rag', 'machine learning', 'ai',
    'typescript', 'javascript', 'angular', 'react', 'vue', 'node',
    'rest', 'graphql', 'api', 'microservices', 'distributed systems',
    'observability', 'prometheus', 'grafana', 'elasticsearch',
    'security', 'oauth', 'jwt', 'ci/cd', 'github actions',
]


STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'have',
    'in', 'into', 'is', 'it', 'of', 'on', 'or', 'our', 'that', 'the', 'their',
    'this', 'to', 'with', 'you', 'your', 'we', 'will', 'work', 'team',
}


@dataclass
class AIResult:
    data: dict[str, Any]
    source: str


def stable_hash(text: str) -> str:
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def clean_text(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def keywords(text: str, *, limit: int = 80) -> list[str]:
    tokens = re.findall(r'[A-Za-z][A-Za-z0-9+#./-]{1,}', (text or '').lower())
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        token = token.strip('.,;:()[]{}')
        if token in STOP_WORDS or token in seen or len(token) < 2:
            continue
        seen.add(token)
        result.append(token)
        if len(result) >= limit:
            break
    return result


def detect_skills(text: str) -> list[str]:
    lowered = f' {clean_text(text).lower()} '
    found = []
    for skill in SKILL_HINTS:
        pattern = skill.lower()
        if re.search(rf'(?<![a-z0-9]){re.escape(pattern)}(?![a-z0-9])', lowered):
            found.append(skill.title() if skill not in {'drf', 'api', 'rag', 'llm'} else skill.upper())
    return sorted(dict.fromkeys(found), key=str.lower)


def chunk_text(text: str, *, max_chars: int = 1200) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n+', text or '') if p.strip()]
    chunks: list[str] = []
    current = ''
    for paragraph in paragraphs or [text]:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f'{current}\n\n{paragraph}'.strip()
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
            continue
        for start in range(0, len(paragraph), max_chars):
            chunks.append(paragraph[start:start + max_chars])
        current = ''
    if current:
        chunks.append(current)
    return chunks[:60]


def heuristic_embedding(text: str, *, dimensions: int = 128) -> list[float]:
    vector = [0.0] * dimensions
    for token in keywords(text, limit=300):
        digest = hashlib.blake2b(token.encode('utf-8'), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], 'big') % dimensions
        sign = 1 if digest[4] % 2 == 0 else -1
        vector[idx] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    width = min(len(left), len(right))
    dot = sum(float(left[i]) * float(right[i]) for i in range(width))
    left_norm = math.sqrt(sum(float(left[i]) ** 2 for i in range(width))) or 1.0
    right_norm = math.sqrt(sum(float(right[i]) ** 2 for i in range(width))) or 1.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def openai_client():
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except Exception:
        return None
    return OpenAI(api_key=api_key)


def embed_text(text: str) -> list[float]:
    cleaned = clean_text(text)
    client = openai_client()
    if client and cleaned:
        try:
            response = client.embeddings.create(
                model=getattr(settings, 'OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'),
                input=cleaned[:12000],
            )
            return [float(value) for value in response.data[0].embedding]
        except Exception:
            pass
    return heuristic_embedding(cleaned)


def generate_json(system: str, user: str, schema: dict[str, Any] | None = None) -> AIResult | None:
    client = openai_client()
    if not client:
        return None
    try:
        text_format: dict[str, Any] = {'type': 'json_object'}
        if schema:
            text_format = {
                'type': 'json_schema',
                'name': schema.get('name', 'job_search_schema'),
                'schema': schema.get('schema', schema),
                'strict': True,
            }
        response = client.responses.create(
            model=getattr(settings, 'OPENAI_TEXT_MODEL', 'gpt-4.1-mini'),
            input=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            text={'format': text_format},
        )
        raw = getattr(response, 'output_text', '') or ''
        if not raw:
            raw = response.output[0].content[0].text
        return AIResult(data=json.loads(raw), source='openai')
    except Exception:
        return None


def extract_profile_facts(text: str, *, title: str = '') -> AIResult:
    cleaned = clean_text(text)
    schema = {
        'name': 'profile_facts',
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'facts': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'fact_type': {'type': 'string'},
                            'title': {'type': 'string'},
                            'statement': {'type': 'string'},
                            'confidence': {'type': 'string'},
                        },
                        'required': ['fact_type', 'title', 'statement', 'confidence'],
                    },
                },
            },
            'required': ['facts'],
        },
    }
    generated = generate_json(
        'Extract only factual career information from the user text. Do not invent details.',
        f'Document title: {title}\n\nText:\n{cleaned[:14000]}',
        schema,
    )
    if generated:
        return generated

    facts: list[dict[str, str]] = []
    for skill in detect_skills(cleaned):
        facts.append({
            'fact_type': 'skill',
            'title': skill,
            'statement': f'Experience includes {skill}.',
            'confidence': 'medium',
        })
    for line in re.split(r'[\n.;]+', text or ''):
        line = clean_text(line)
        if len(line) < 24:
            continue
        lowered = line.lower()
        fact_type = 'achievement' if any(word in lowered for word in ['built', 'created', 'led', 'improved', 'launched', 'designed']) else 'role'
        facts.append({
            'fact_type': fact_type,
            'title': line[:80],
            'statement': line[:600],
            'confidence': 'medium',
        })
        if len(facts) >= 25:
            break
    return AIResult(data={'facts': facts[:40]}, source='heuristic')


def extract_job(text: str, *, source_url: str = '') -> AIResult:
    cleaned = clean_text(text)
    schema = {
        'name': 'job_extraction',
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'title': {'type': 'string'},
                'company': {'type': 'string'},
                'location': {'type': 'string'},
                'remote_policy': {'type': 'string'},
                'seniority': {'type': 'string'},
                'compensation': {'type': 'string'},
                'application_url': {'type': 'string'},
                'responsibilities': {'type': 'array', 'items': {'type': 'string'}},
                'required_skills': {'type': 'array', 'items': {'type': 'string'}},
                'preferred_skills': {'type': 'array', 'items': {'type': 'string'}},
                'confidence': {'type': 'string'},
            },
            'required': [
                'title', 'company', 'location', 'remote_policy', 'seniority',
                'compensation', 'application_url', 'responsibilities',
                'required_skills', 'preferred_skills', 'confidence',
            ],
        },
    }
    generated = generate_json(
        'Extract structured job-posting data. Use empty strings or arrays when fields are not present.',
        f'Source URL: {source_url}\n\nJob text:\n{cleaned[:16000]}',
        schema,
    )
    if generated:
        return generated

    lines = [clean_text(line) for line in (text or '').splitlines() if clean_text(line)]
    title = lines[0][:220] if lines else 'Imported Job'
    company = ''
    for line in lines[1:6]:
        if re.search(r'\b(company|about us|employer)\b', line.lower()):
            continue
        if len(line) <= 80:
            company = line
            break
    skills = detect_skills(cleaned)
    location_match = re.search(r'\b(remote|hybrid|onsite|on-site|canada|united states|us|toronto|montreal|vancouver)\b', cleaned, re.I)
    remote_policy = 'unknown'
    if re.search(r'\bremote\b', cleaned, re.I):
        remote_policy = 'remote'
    elif re.search(r'\bhybrid\b', cleaned, re.I):
        remote_policy = 'hybrid'
    elif re.search(r'\bonsite|on-site\b', cleaned, re.I):
        remote_policy = 'onsite'
    return AIResult(
        data={
            'title': title,
            'company': company,
            'location': location_match.group(0) if location_match else '',
            'remote_policy': remote_policy,
            'seniority': 'senior' if re.search(r'\bsenior|staff|lead|principal\b', cleaned, re.I) else '',
            'compensation': '',
            'application_url': source_url,
            'responsibilities': [line for line in lines if len(line) > 40][:8],
            'required_skills': skills,
            'preferred_skills': [],
            'confidence': 'medium',
        },
        source='heuristic',
    )


def tailor_resume(
    *,
    canonical_markdown: str,
    job_title: str,
    job_text: str,
    facts: list[dict[str, Any]],
) -> AIResult:
    facts_text = '\n'.join(f'- {fact.get("title")}: {fact.get("statement")}' for fact in facts[:80])
    schema = {
        'name': 'resume_tailoring',
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'title': {'type': 'string'},
                'content_markdown': {'type': 'string'},
                'summary_changes': {'type': 'array', 'items': {'type': 'string'}},
                'keyword_coverage': {'type': 'array', 'items': {'type': 'string'}},
                'unsupported_claims': {'type': 'array', 'items': {'type': 'string'}},
                'weak_claims': {'type': 'array', 'items': {'type': 'string'}},
                'evidence_links': {'type': 'array', 'items': {'type': 'string'}},
                'risk_notes': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': [
                'title', 'content_markdown', 'summary_changes', 'keyword_coverage',
                'unsupported_claims', 'weak_claims', 'evidence_links', 'risk_notes',
            ],
        },
    }
    generated = generate_json(
        'Tailor the resume only using the supplied canonical resume and evidence facts. Do not invent claims.',
        (
            f'Target job: {job_title}\n\nJob description:\n{job_text[:9000]}\n\n'
            f'Evidence facts:\n{facts_text[:9000]}\n\nCanonical resume:\n{canonical_markdown[:12000]}'
        ),
        schema,
    )
    if generated:
        return generated

    job_skills = detect_skills(job_text)
    resume = canonical_markdown.strip() or '# Resume\n\nAdd your canonical resume content first.'
    inserted = ''
    if job_skills:
        inserted = '\n\n## Targeted Skills\n\n' + ', '.join(job_skills[:16])
    content = f'{resume}{inserted}\n'
    covered = [skill for skill in job_skills if re.search(re.escape(skill), resume, re.I)]
    weak = [skill for skill in job_skills if skill not in covered][:8]
    return AIResult(
        data={
            'title': f'{job_title} Tailored Resume',
            'content_markdown': content,
            'summary_changes': ['Added a targeted skills section based on the job description.'] if inserted else [],
            'keyword_coverage': covered,
            'unsupported_claims': [],
            'weak_claims': weak,
            'evidence_links': [str(fact.get('title')) for fact in facts[:12]],
            'risk_notes': ['Heuristic draft: review carefully before applying.'],
        },
        source='heuristic',
    )

