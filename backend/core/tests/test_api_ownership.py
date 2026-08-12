from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Application, JobPosting, JobSource, ProfileDocument, ProfileFact, Resume


class OwnedRelationApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='owner', password='password')
        self.other = User.objects.create_user(username='other', password='password')
        self.client.force_authenticate(self.owner)

        self.owner_source = JobSource.objects.create(owner=self.owner, name='Owner source', kind='manual')
        self.other_source = JobSource.objects.create(owner=self.other, name='Other source', kind='manual')
        self.owner_job = JobPosting.objects.create(
            owner=self.owner,
            source=self.owner_source,
            title='Owner job',
            description_text='Python role',
            content_hash='owner-job',
        )
        self.other_job = JobPosting.objects.create(
            owner=self.other,
            source=self.other_source,
            title='Other job',
            description_text='Go role',
            content_hash='other-job',
        )
        self.owner_resume = Resume.objects.create(
            owner=self.owner,
            kind='canonical',
            title='Owner resume',
            content_markdown='# Owner',
        )
        self.other_resume = Resume.objects.create(
            owner=self.other,
            kind='canonical',
            title='Other resume',
            content_markdown='# Other',
        )
        self.owner_application = Application.objects.create(
            owner=self.owner,
            job=self.owner_job,
            resume=self.owner_resume,
        )
        self.other_application = Application.objects.create(
            owner=self.other,
            job=self.other_job,
            resume=self.other_resume,
        )

    def assert_field_rejected(self, response, field):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn(field, response.data)

    def test_job_cannot_reference_another_owners_source(self):
        response = self.client.post('/api/jobs/', {
            'source': self.other_source.id,
            'title': 'Cross-owner job',
            'description_text': 'Python API role',
        }, format='json')
        self.assert_field_rejected(response, 'source')

    def test_resume_cannot_reference_another_owners_job_or_parent(self):
        response = self.client.post('/api/resumes/', {
            'kind': 'tailored',
            'title': 'Cross-owner resume',
            'content_markdown': '# Test',
            'parent_resume': self.other_resume.id,
            'target_job': self.other_job.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn('parent_resume', response.data)
        self.assertIn('target_job', response.data)

    def test_application_cannot_reference_another_owners_job_or_resume(self):
        response = self.client.post('/api/applications/', {
            'job': self.other_job.id,
            'resume': self.other_resume.id,
            'status': 'saved',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn('job', response.data)
        self.assertIn('resume', response.data)

        response = self.client.patch(
            f'/api/applications/{self.owner_application.id}/',
            {'resume': self.other_resume.id},
            format='json',
        )
        self.assert_field_rejected(response, 'resume')

    def test_event_cannot_reference_another_owners_application(self):
        response = self.client.post('/api/application-events/', {
            'application': self.other_application.id,
            'event_type': 'note',
            'happened_at': timezone.now().isoformat(),
            'notes': 'Cross-owner note',
        }, format='json')
        self.assert_field_rejected(response, 'application')

    def test_artifact_cannot_reference_another_owners_records(self):
        response = self.client.post('/api/artifacts/', {
            'application': self.other_application.id,
            'resume': self.other_resume.id,
            'kind': 'note',
            'title': 'Cross-owner artifact',
            'content_text': 'Should not be accepted',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn('application', response.data)
        self.assertIn('resume', response.data)

    def test_owner_relations_remain_writable(self):
        response = self.client.post('/api/applications/', {
            'job': self.owner_job.id,
            'resume': self.owner_resume.id,
            'status': 'saved',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        response = self.client.post('/api/artifacts/', {
            'application': response.data['id'],
            'resume': self.owner_resume.id,
            'kind': 'note',
            'title': 'Owner artifact',
            'content_text': 'Allowed',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_foreign_objects_are_not_addressable(self):
        paths = [
            f'/api/sources/{self.other_source.id}/',
            f'/api/jobs/{self.other_job.id}/',
            f'/api/resumes/{self.other_resume.id}/',
            f'/api/applications/{self.other_application.id}/',
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ProfileFactApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username='fact-owner', password='password')
        self.other = User.objects.create_user(username='fact-other', password='password')
        self.client.force_authenticate(self.owner)
        self.owner_document = ProfileDocument.objects.create(
            owner=self.owner,
            kind='note',
            title='Owner document',
            raw_text='Owner profile text',
        )
        self.other_document = ProfileDocument.objects.create(
            owner=self.other,
            kind='note',
            title='Other document',
            raw_text='Other profile text',
        )
        self.fact = ProfileFact.objects.create(
            owner=self.owner,
            fact_type='skill',
            title='Python',
            statement='Builds Python services.',
            source_document=self.owner_document,
        )

    def test_source_provenance_cannot_be_reassigned(self):
        response = self.client.patch(f'/api/profile/facts/{self.fact.id}/', {
            'title': 'Advanced Python',
            'source_document': self.other_document.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.fact.refresh_from_db()
        self.assertEqual(self.fact.title, 'Advanced Python')
        self.assertEqual(self.fact.source_document_id, self.owner_document.id)
