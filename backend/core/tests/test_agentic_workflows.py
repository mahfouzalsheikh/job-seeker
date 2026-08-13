from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from core.domain.documents import prepare_application_materials, render_application_bundle
from core.domain.matching import recompute_match
from core.domain.orchestration import create_concierge_run, decide_approval, execute_agent_run
from core.domain.sourcing import validate_public_url
from core.models import (
    Application,
    ApprovalRequest,
    Artifact,
    CandidateProfile,
    ConversationMessage,
    JobPosting,
    JobRequirement,
    ProfileFact,
    Resume,
)


class AgenticWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='agent-user', password='password')
        CandidateProfile.objects.create(
            owner=self.user,
            headline='Senior platform engineer',
            target_roles=['Staff Platform Engineer'],
            location='Toronto, Canada',
            authorized_countries=['Canada'],
            work_modes=['remote', 'hybrid'],
            minimum_compensation=150000,
        )
        ProfileFact.objects.create(
            owner=self.user,
            fact_type='achievement',
            title='Platform reliability',
            statement='Built Python and Django services with Celery and PostgreSQL for reliable platform workflows.',
            confidence='high',
            verified_by_user=True,
            lifecycle='verified',
        )
        self.job = JobPosting.objects.create(
            owner=self.user,
            title='Staff Platform Engineer',
            company='Northstar',
            location='Toronto, Canada',
            remote_policy='hybrid',
            compensation='CAD 170,000–190,000',
            description_text='Build Python Django platform services using PostgreSQL and Celery.',
            content_hash='agentic-job',
            freshness_status='fresh',
        )
        for skill in ['Python', 'Django', 'PostgreSQL', 'Celery']:
            JobRequirement.objects.create(
                owner=self.user, job=self.job, kind='required', category='skill', text=skill,
                normalized_value=skill.lower(), is_hard=True, weight=90,
            )
        Resume.objects.create(
            owner=self.user,
            kind='canonical',
            title='Canonical Resume',
            content_markdown='# Candidate\n\n## Experience\n\n- Built Python and Django services with Celery and PostgreSQL for reliable platform workflows.',
        )

    def test_match_decomposes_fit_and_eligibility(self):
        match = recompute_match(self.job)

        self.assertEqual(match.hard_filter_status, 'pass')
        self.assertGreaterEqual(match.score, 70)
        self.assertEqual(match.signals.count(), 5)
        self.assertTrue(match.supporting_facts)
        self.assertIn('score_version', match.explanation_json)

    def test_document_workflow_waits_for_approval_then_prepares_materials(self):
        run = create_concierge_run(self.user, message='Prepare my strongest opportunity')
        execute_agent_run(run)
        run.refresh_from_db()

        self.assertEqual(run.status, 'waiting_approval')
        approval = ApprovalRequest.objects.get(run=run)
        decide_approval(approval, approved=True)

        application = Application.objects.get(owner=self.user, job=self.job)
        self.assertEqual(application.status, 'materials_ready')
        self.assertIsNotNone(application.resume_id)
        self.assertTrue(self.job.cover_letters.exists())
        run.refresh_from_db()
        self.assertEqual(run.status, 'succeeded')

    @override_settings(GOTENBERG_URL='', MEDIA_ROOT='/tmp/job-seeker-test-media')
    def test_rendering_has_recoverable_html_fallback(self):
        application = Application.objects.create(owner=self.user, job=self.job, status='preparing')
        prepare_application_materials(self.user, self.job, application=application)

        artifacts = render_application_bundle(self.user, application=application)

        self.assertEqual(len(artifacts), 2)
        self.assertTrue(all(artifact.kind.endswith('_html') for artifact in artifacts))
        self.assertTrue(all(artifact.file for artifact in artifacts))
        self.assertEqual(Artifact.objects.count(), 2)


class AgenticApiOwnershipTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner-agentic', password='password')
        self.other = User.objects.create_user(username='other-agentic', password='password')
        self.client.force_authenticate(self.owner)
        self.other_approval = ApprovalRequest.objects.create(
            owner=self.other, kind='verify_fact', title='Other approval', prompt='No access', payload={},
        )

    def test_candidate_profile_is_owner_scoped_and_created_lazily(self):
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(CandidateProfile.objects.filter(owner=self.owner).exists())

        response = self.client.patch('/api/profile/', {'target_roles': ['Platform Engineer']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['target_roles'], ['Platform Engineer'])

    def test_foreign_approval_cannot_be_addressed(self):
        response = self.client.post(f'/api/approvals/{self.other_approval.id}/decide/', {'approved': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_concierge_creates_message_and_run(self):
        response = self.client.post('/api/conversations/', {'title': 'Concierge', 'status': 'active', 'context': {}}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        thread_id = response.data['id']

        with self.settings(CELERY_TASK_ALWAYS_EAGER=True):
            response = self.client.post(f'/api/conversations/{thread_id}/send/', {'content': 'What should I focus on today?'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(ConversationMessage.objects.filter(owner=self.owner, thread_id=thread_id, role='user').exists())


class SourceSafetyTests(SimpleTestCase):
    def test_private_source_addresses_are_rejected(self):
        from unittest.mock import patch

        with patch('core.domain.sourcing.socket.getaddrinfo', return_value=[(None, None, None, None, ('127.0.0.1', 80))]):
            with self.assertRaisesMessage(ValueError, 'public network address'):
                validate_public_url('http://localhost/jobs.xml')
