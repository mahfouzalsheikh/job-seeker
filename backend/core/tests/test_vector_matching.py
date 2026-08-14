from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.ai import embed_text_result
from core.domain.embeddings import (
    job_embedding_text,
    profile_embedding_text,
    refresh_fact_embedding,
    refresh_job_embedding,
    refresh_profile_embedding,
)
from core.domain.matching import recompute_match
from core.models import CandidateProfile, JobPosting, JobRequirement, ProfileFact


@override_settings(OPENAI_API_KEY='', OPENAI_EMBEDDING_DIMENSIONS=1536)
class VectorMatchingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='vector-user', password='password')
        self.profile = CandidateProfile.objects.create(
            owner=self.user,
            headline='Staff platform engineer',
            professional_summary='Builds reliable distributed developer platforms.',
            target_roles=['Staff Platform Engineer'],
            work_modes=['remote'],
        )
        self.fact = ProfileFact.objects.create(
            owner=self.user,
            fact_type='achievement',
            title='Reliable platform delivery',
            statement='Led Python, Django, PostgreSQL, and Celery platform delivery.',
            verified_by_user=True,
            lifecycle='verified',
        )
        self.job = JobPosting.objects.create(
            owner=self.user,
            title='Staff Platform Engineer',
            company='Northstar',
            remote_policy='remote',
            description_text='Lead a reliable Python and Django platform backed by PostgreSQL and Celery.',
            content_hash='vector-job',
        )
        JobRequirement.objects.create(
            owner=self.user,
            job=self.job,
            kind='required',
            category='skill',
            text='Python',
            normalized_value='python',
            is_hard=True,
            weight=90,
        )

    def test_canonical_text_includes_candidate_and_job_evidence(self):
        self.assertIn('Staff platform engineer', profile_embedding_text(self.user))
        self.assertIn('Reliable platform delivery', profile_embedding_text(self.user))
        self.assertIn('required skill: Python', job_embedding_text(self.job))

    def test_refresh_persists_fixed_width_pgvector_values_and_metadata(self):
        refresh_fact_embedding(self.fact)
        refresh_profile_embedding(self.user)
        refresh_job_embedding(self.job)
        self.fact.refresh_from_db()
        self.profile.refresh_from_db()
        self.job.refresh_from_db()

        for item in (self.fact, self.profile, self.job):
            self.assertEqual(len(item.semantic_embedding), 1536)
            self.assertEqual(item.embedding_provider, 'local_fallback')
            self.assertTrue(item.embedding_content_hash)
            self.assertIsNotNone(item.embedding_updated_at)

    def test_match_uses_dedicated_semantic_signal_and_nearest_fact(self):
        refresh_fact_embedding(self.fact)
        match = recompute_match(self.job)

        semantic = match.signals.get(kind='semantic')
        self.assertGreater(semantic.score, 0)
        self.assertEqual(semantic.weight, 25)
        self.assertEqual(match.explanation_json['score_version'], '2026-08-v3-pgvector')
        self.assertEqual(match.explanation_json['embedding_provider'], 'local_fallback')
        self.assertIn(self.fact.id, [item['fact_id'] for item in match.supporting_facts])

    def test_changed_job_content_invalidates_embedding_hash(self):
        refresh_job_embedding(self.job)
        self.job.refresh_from_db()
        original_hash = self.job.embedding_content_hash
        self.job.description_text += ' Own Kubernetes infrastructure and observability.'
        self.job.save(update_fields=['description_text', 'updated_at'])

        refresh_job_embedding(self.job)
        self.job.refresh_from_db()
        self.assertNotEqual(self.job.embedding_content_hash, original_hash)

    @patch('core.ai._openai_available', return_value=True)
    @patch('core.ai.openai_client')
    def test_openai_embedding_uses_configured_model_and_fixed_dimensions(self, client_factory, _available):
        client = Mock()
        client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.25] * 1536)],
        )
        client_factory.return_value = client

        result = embed_text_result('Staff platform engineering')

        self.assertEqual(result.provider, 'openai')
        self.assertEqual(result.model, 'text-embedding-3-small')
        self.assertEqual(len(result.vector), 1536)
        client.embeddings.create.assert_called_once_with(
            model='text-embedding-3-small',
            input='Staff platform engineering',
            dimensions=1536,
        )
