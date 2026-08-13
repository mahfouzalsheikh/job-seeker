from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from core.domain.documents import document_html, prepare_application_materials, render_application_bundle
from core.domain.matching import recompute_match
from core.domain.orchestration import create_concierge_run, decide_approval, execute_agent_run
from core.domain.sourcing import validate_public_url
from core.models import (
    AgentRun,
    Application,
    ApprovalRequest,
    Artifact,
    CandidateProfile,
    ConversationMessage,
    JobPosting,
    JobRequirement,
    JobSource,
    ProfileFact,
    Resume,
    SourceRun,
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

    def test_chat_understands_top_role_follow_up_and_keeps_job_context(self):
        recompute_match(self.job)
        thread = None

        recommendation = create_concierge_run(self.user, message='Give me the top one please')
        thread = recommendation.thread
        self.assertEqual(recommendation.agent, 'matching')
        execute_agent_run(recommendation)

        answer = ConversationMessage.objects.filter(thread=thread, role='assistant').latest('created_at')
        self.assertIn('Top recommendation', answer.content)
        self.assertIn(self.job.title, answer.content)
        self.assertEqual(answer.metadata['job_id'], self.job.id)
        self.assertEqual(len(answer.metadata['actions']), 2)

        preparation = create_concierge_run(self.user, message='Prepare it', thread=thread)
        self.assertEqual(preparation.agent, 'documents')
        self.assertEqual(preparation.input['job_id'], self.job.id)
        execute_agent_run(preparation)

        approval = ApprovalRequest.objects.get(run=preparation)
        self.assertEqual(approval.payload['job_id'], self.job.id)

    @override_settings(GOTENBERG_URL='', MEDIA_ROOT='/tmp/job-seeker-test-media')
    def test_rendering_has_recoverable_html_fallback(self):
        application = Application.objects.create(owner=self.user, job=self.job, status='preparing')
        prepare_application_materials(self.user, self.job, application=application)

        artifacts = render_application_bundle(self.user, application=application)

        self.assertEqual(len(artifacts), 2)
        self.assertTrue(all(artifact.kind.endswith('_html') for artifact in artifacts))
        self.assertTrue(all(artifact.file for artifact in artifacts))
        self.assertEqual(Artifact.objects.count(), 2)

    def test_resume_design_is_stored_and_rendered_consistently(self):
        application = Application.objects.create(owner=self.user, job=self.job, status='preparing')
        materials = prepare_application_materials(self.user, self.job, application=application)
        resume = materials['resume']
        design = resume.content_json['design']

        self.assertIn(design['template'], {'modern', 'classic', 'minimal'})
        self.assertIn(design['density'], {'compact', 'balanced', 'spacious'})
        rendered = document_html(resume.title, resume.content_markdown, kind='resume', design=design)
        self.assertIn(f"size: {design['page_size']}", rendered)
        self.assertIn(design['accent'], rendered)
        self.assertIn('<h1>', rendered)


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

    def test_onboarding_agent_adapts_and_builds_a_ready_profile(self):
        response = self.client.get('/api/profile/onboarding/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['step']['id'], 'welcome')

        def answer(step, answers=None):
            result = self.client.post('/api/profile/onboarding/', {'step': step, 'answers': answers or {}}, format='json')
            self.assertEqual(result.status_code, status.HTTP_200_OK, result.data)
            return result

        self.assertEqual(answer('welcome').data['step']['id'], 'source')
        self.assertEqual(answer('source', {'skip': True}).data['step']['id'], 'direction')
        self.assertEqual(answer('direction', {
            'headline': 'Product-minded platform engineer',
            'target_roles': ['Staff Platform Engineer'],
            'target_industries': ['Developer tools'],
        }).data['step']['id'], 'logistics')
        self.assertEqual(answer('logistics', {
            'location': 'Toronto, Canada',
            'authorized_countries': ['Canada'],
            'work_modes': ['remote', 'hybrid'],
            'employment_types': ['full-time'],
            'minimum_compensation': 150000,
            'compensation_currency': 'CAD',
        }).data['step']['id'], 'strengths')
        self.assertEqual(answer('strengths', {
            'skills': ['Python', 'Platform architecture'],
            'capability': 'Builds dependable systems and helps teams make sound technical decisions.',
        }).data['step']['id'], 'impact')
        self.assertEqual(answer('impact', {
            'title': 'Improved deployment recovery',
            'story': 'Led a reliability program that reduced deployment recovery time by 40 percent across the platform.',
        }).data['step']['id'], 'preferences')
        self.assertEqual(answer('preferences', {
            'ideal': ['High ownership', 'Calm collaboration'],
            'avoid': ['Always-on culture'],
        }).data['step']['id'], 'summary')
        review = answer('summary', {
            'professional_summary': 'Product-minded platform engineer who builds dependable systems and helps teams make clear technical decisions.',
        })
        self.assertEqual(review.data['step']['id'], 'review')
        self.assertTrue(review.data['readiness']['ready'])
        self.assertEqual(review.data['readiness']['score'], 100)

        completed = answer('complete')
        self.assertFalse(completed.data['needs_onboarding'])
        self.assertIsNotNone(completed.data['profile']['onboarding_completed_at'])

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

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_profile_source_is_ingested_and_becomes_canonical_resume(self):
        response = self.client.post('/api/profile/documents/', {
            'kind': 'resume',
            'title': 'Integration resume',
            'raw_text': 'Senior Python engineer who built Django APIs with PostgreSQL and Celery.',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        from core.models import ProfileDocument

        document = ProfileDocument.objects.get(owner=self.owner, pk=response.data['id'])
        self.assertEqual(document.status, 'ready')
        self.assertTrue(ProfileFact.objects.filter(owner=self.owner, source_document=document).exists())
        self.assertTrue(Resume.objects.filter(owner=self.owner, kind='canonical').exists())

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_manual_source_run_reaches_a_terminal_success_state(self):
        source = JobSource.objects.create(owner=self.owner, name='Manual QA', kind='manual', config={})

        response = self.client.post(f'/api/sources/{source.id}/run/', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        run = SourceRun.objects.get(owner=self.owner, source=source)
        source.refresh_from_db()
        self.assertEqual(run.status, 'succeeded')
        self.assertEqual(source.last_status, 'succeeded')

    def test_application_requires_an_approved_resume_before_applied(self):
        job = JobPosting.objects.create(
            owner=self.owner, title='QA Engineer', description_text='Python Django', content_hash='qa-guard',
        )
        resume = Resume.objects.create(owner=self.owner, title='Draft', kind='tailored', target_job=job)
        application = Application.objects.create(owner=self.owner, job=job, resume=resume, status='materials_ready')

        blocked = self.client.patch(f'/api/applications/{application.id}/', {'status': 'applied'}, format='json')
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)

        resume.approved = True
        resume.save(update_fields=['approved'])
        allowed = self.client.patch(f'/api/applications/{application.id}/', {'status': 'applied'}, format='json')
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(allowed.data['applied_at'])

    def test_rejecting_a_material_approval_cancels_without_side_effects(self):
        job = JobPosting.objects.create(
            owner=self.owner, title='Do Not Prepare', description_text='Python', content_hash='qa-reject',
        )
        run = AgentRun.objects.create(owner=self.owner, agent='documents', objective='Prepare', status='waiting_approval')
        approval = ApprovalRequest.objects.create(
            owner=self.owner, run=run, kind='prepare_application', title='Prepare', prompt='Proceed?', payload={'job_id': job.id},
        )

        response = self.client.post(f'/api/approvals/{approval.id}/decide/', {'approved': False}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        self.assertEqual(run.status, 'cancelled')
        self.assertFalse(Application.objects.filter(owner=self.owner, job=job).exists())


class SourceSafetyTests(SimpleTestCase):
    def test_private_source_addresses_are_rejected(self):
        from unittest.mock import patch

        with patch('core.domain.sourcing.socket.getaddrinfo', return_value=[(None, None, None, None, ('127.0.0.1', 80))]):
            with self.assertRaisesMessage(ValueError, 'public network address'):
                validate_public_url('http://localhost/jobs.xml')
