from __future__ import annotations

import os
import re
import uuid

from django.conf import settings
from django.db import models


def safe_upload_to(prefix: str, filename: str) -> str:
    _, ext = os.path.splitext(filename or '')
    suffix = (ext or '').lower()[:16]
    return f'{prefix}/{uuid.uuid4().hex}{suffix}'


def profile_document_upload_to(instance, filename):
    return safe_upload_to('profile_documents', filename)


def artifact_upload_to(instance, filename):
    stem = os.path.splitext(os.path.basename(filename or 'artifact'))[0]
    stem = re.sub(r'[^0-9A-Za-z]+', '-', stem).strip('-').lower()[:80] or 'artifact'
    _, ext = os.path.splitext(filename or '')
    return f'artifacts/{stem}-{uuid.uuid4().hex}{(ext or "").lower()[:16]}'


class OwnedModel(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ProfileDocument(OwnedModel):
    KIND_CHOICES = [
        ('resume', 'Resume'),
        ('note', 'Note'),
        ('conversation', 'Conversation'),
        ('profile', 'Profile'),
        ('project', 'Project'),
        ('review', 'Review'),
    ]
    STATUS_CHOICES = [
        ('new', 'New'),
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]

    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default='note', db_index=True)
    title = models.CharField(max_length=220)
    upload = models.FileField(upload_to=profile_document_upload_to, blank=True)
    raw_text = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default='new', db_index=True)
    status_message = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['owner', 'kind']),
            models.Index(fields=['owner', 'status']),
        ]

    def __str__(self) -> str:
        return self.title


class ProfileChunk(OwnedModel):
    document = models.ForeignKey(ProfileDocument, on_delete=models.CASCADE, related_name='chunks')
    text = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    embedding = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['document_id', 'id']
        indexes = [models.Index(fields=['owner', 'document'])]


class ProfileFact(OwnedModel):
    FACT_CHOICES = [
        ('skill', 'Skill'),
        ('achievement', 'Achievement'),
        ('role', 'Role'),
        ('project', 'Project'),
        ('metric', 'Metric'),
        ('preference', 'Preference'),
        ('constraint', 'Constraint'),
        ('education', 'Education'),
    ]

    fact_type = models.CharField(max_length=32, choices=FACT_CHOICES, default='achievement', db_index=True)
    title = models.CharField(max_length=220)
    statement = models.TextField()
    normalized_value = models.CharField(max_length=220, blank=True)
    confidence = models.CharField(max_length=24, default='medium')
    source_document = models.ForeignKey(ProfileDocument, null=True, blank=True, on_delete=models.SET_NULL, related_name='facts')
    source_chunk = models.ForeignKey(ProfileChunk, null=True, blank=True, on_delete=models.SET_NULL, related_name='facts')
    verified_by_user = models.BooleanField(default=False, db_index=True)
    embedding = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['fact_type', 'title', '-id']
        indexes = [
            models.Index(fields=['owner', 'fact_type']),
            models.Index(fields=['owner', 'verified_by_user']),
        ]

    def __str__(self) -> str:
        return self.title


class JobSource(OwnedModel):
    KIND_CHOICES = [
        ('manual', 'Manual'),
        ('company_page', 'Company Page'),
        ('ats', 'ATS'),
        ('api', 'API'),
        ('rss', 'RSS'),
    ]

    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default='manual', db_index=True)
    name = models.CharField(max_length=220)
    config = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True, db_index=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=32, blank=True)
    last_message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['name', 'id']
        indexes = [models.Index(fields=['owner', 'enabled'])]

    def __str__(self) -> str:
        return self.name


class JobPosting(OwnedModel):
    REMOTE_CHOICES = [
        ('unknown', 'Unknown'),
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
        ('onsite', 'On-site'),
    ]

    source = models.ForeignKey(JobSource, null=True, blank=True, on_delete=models.SET_NULL, related_name='jobs')
    title = models.CharField(max_length=240)
    company = models.CharField(max_length=220, blank=True)
    location = models.CharField(max_length=220, blank=True)
    remote_policy = models.CharField(max_length=24, choices=REMOTE_CHOICES, default='unknown', db_index=True)
    seniority = models.CharField(max_length=120, blank=True)
    compensation = models.CharField(max_length=160, blank=True)
    description_text = models.TextField()
    extracted_json = models.JSONField(default=dict, blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    application_url = models.URLField(max_length=1000, blank=True)
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    embedding = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=24, default='new', db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    discovered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-discovered_at', '-id']
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['owner', 'remote_policy']),
            models.Index(fields=['owner', 'company']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['owner', 'content_hash'], name='core_jobposting_owner_content_hash_uniq'),
        ]

    def __str__(self) -> str:
        company = f' at {self.company}' if self.company else ''
        return f'{self.title}{company}'


class JobMatch(OwnedModel):
    job = models.OneToOneField(JobPosting, on_delete=models.CASCADE, related_name='match')
    score = models.PositiveSmallIntegerField(default=0, db_index=True)
    hard_filter_status = models.CharField(max_length=32, default='pass')
    explanation_json = models.JSONField(default=dict, blank=True)
    missing_requirements = models.JSONField(default=list, blank=True)
    supporting_facts = models.JSONField(default=list, blank=True)
    confidence = models.CharField(max_length=24, default='medium')
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-score', '-computed_at']
        indexes = [
            models.Index(fields=['owner', '-score']),
            models.Index(fields=['owner', 'confidence']),
        ]

    def __str__(self) -> str:
        return f'{self.job}: {self.score}'


class Resume(OwnedModel):
    KIND_CHOICES = [
        ('canonical', 'Canonical'),
        ('tailored', 'Tailored'),
    ]

    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default='canonical', db_index=True)
    title = models.CharField(max_length=220)
    content_markdown = models.TextField()
    content_json = models.JSONField(default=dict, blank=True)
    parent_resume = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='variants')
    target_job = models.ForeignKey(JobPosting, null=True, blank=True, on_delete=models.SET_NULL, related_name='resumes')
    validation = models.JSONField(default=dict, blank=True)
    approved = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['owner', 'kind']),
            models.Index(fields=['owner', 'approved']),
        ]

    def __str__(self) -> str:
        return self.title


class ResumeClaim(OwnedModel):
    SUPPORT_CHOICES = [
        ('supported', 'Supported'),
        ('user_confirmed', 'User Confirmed'),
        ('unsupported', 'Unsupported'),
    ]

    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='claims')
    text = models.TextField()
    profile_fact = models.ForeignKey(ProfileFact, null=True, blank=True, on_delete=models.SET_NULL, related_name='resume_claims')
    support_status = models.CharField(max_length=32, choices=SUPPORT_CHOICES, default='unsupported', db_index=True)

    class Meta:
        ordering = ['resume_id', 'id']


class Application(OwnedModel):
    STATUS_CHOICES = [
        ('discovered', 'Discovered'),
        ('saved', 'Saved'),
        ('resume_ready', 'Resume Ready'),
        ('applied', 'Applied'),
        ('follow_up_due', 'Follow-Up Due'),
        ('recruiter_screen', 'Recruiter Screen'),
        ('technical_screen', 'Technical Screen'),
        ('onsite_final', 'Onsite / Final'),
        ('offer', 'Offer'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
    ]

    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='saved', db_index=True)
    resume = models.ForeignKey(Resume, null=True, blank=True, on_delete=models.SET_NULL, related_name='applications')
    applied_at = models.DateTimeField(null=True, blank=True)
    follow_up_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    contact_name = models.CharField(max_length=160, blank=True)
    contact_email = models.EmailField(blank=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['owner', 'follow_up_at']),
        ]

    def __str__(self) -> str:
        return f'{self.job} ({self.status})'


class ApplicationEvent(OwnedModel):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=64, db_index=True)
    happened_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-happened_at', '-id']
        indexes = [models.Index(fields=['application', 'event_type'])]


class Artifact(OwnedModel):
    KIND_CHOICES = [
        ('resume_pdf', 'Resume PDF'),
        ('resume_docx', 'Resume DOCX'),
        ('resume_markdown', 'Resume Markdown'),
        ('cover_letter', 'Cover Letter'),
        ('note', 'Note'),
        ('export', 'Export'),
    ]

    application = models.ForeignKey(Application, null=True, blank=True, on_delete=models.SET_NULL, related_name='artifacts')
    resume = models.ForeignKey(Resume, null=True, blank=True, on_delete=models.SET_NULL, related_name='artifacts')
    kind = models.CharField(max_length=40, choices=KIND_CHOICES, default='note', db_index=True)
    title = models.CharField(max_length=220)
    file = models.FileField(upload_to=artifact_upload_to, blank=True)
    content_text = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['owner', 'kind'])]

