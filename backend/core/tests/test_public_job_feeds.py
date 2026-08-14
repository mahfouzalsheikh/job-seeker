from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.domain.sourcing import ArbeitnowConnector, JobicyConnector, connector_for


class PublicJobFeedConnectorTests(SimpleTestCase):
    def source(self, connector, **config):
        return SimpleNamespace(kind='api', config={'connector': connector, **config})

    def test_jobicy_preserves_structured_job_metadata(self):
        connector = JobicyConnector(self.source(
            'jobicy', count=12, geo='canada', industry='engineering', tag='platform engineer',
        ))
        response = {'jobs': [{
            'id': 149241,
            'url': 'https://jobicy.com/jobs/149241-platform-engineer',
            'jobTitle': 'Platform Engineer',
            'companyName': 'Northstar',
            'jobGeo': 'Canada',
            'jobType': ['Full-Time'],
            'jobLevel': 'Senior',
            'jobDescription': '<p>Build dependable platform services.</p>',
            'pubDate': '2026-08-14T04:45:02+00:00',
            'salaryMin': 180000,
            'salaryMax': 220000,
            'salaryCurrency': 'CAD',
            'salaryPeriod': 'yearly',
        }]}

        with patch.object(connector, 'get_json', return_value=response) as get_json:
            records = connector.fetch()

        self.assertIn('geo=canada', get_json.call_args.args[0])
        self.assertIn('tag=platform+engineer', get_json.call_args.args[0])
        self.assertEqual(records[0].company, 'Northstar')
        self.assertEqual(records[0].location, 'Canada')
        self.assertIn('CAD 180000 - 220000 yearly', records[0].description)
        self.assertEqual(records[0].posted_at.isoformat(), '2026-08-14T04:45:02+00:00')
        self.assertEqual(records[0].payload['_source_attribution'], 'Jobicy')

    def test_arbeitnow_applies_remote_and_relevance_caps(self):
        connector = ArbeitnowConnector(self.source(
            'arbeitnow', pages=1, max_results=1, remote_only=True,
            keywords=['platform', 'backend'],
        ))
        response = {'data': [
            {
                'slug': 'onsite-role', 'title': 'Platform Engineer', 'company_name': 'OfficeCo',
                'location': 'Berlin', 'remote': False, 'description': 'Platform work',
                'url': 'https://www.arbeitnow.com/jobs/onsite-role', 'created_at': 1786708828,
                'tags': ['Engineering'],
            },
            {
                'slug': 'remote-role', 'title': 'Backend Lead', 'company_name': 'RemoteCo',
                'location': 'Europe', 'remote': True, 'description': '<p>Lead backend systems.</p>',
                'url': 'https://www.arbeitnow.com/jobs/remote-role', 'created_at': 1786708828,
                'tags': ['Software Development'],
            },
        ]}

        with patch.object(connector, 'get_json', return_value=response):
            records = connector.fetch()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].external_id, 'remote-role')
        self.assertEqual(records[0].company, 'RemoteCo')
        self.assertEqual(records[0].payload['_source_attribution'], 'Arbeitnow')

    def test_connector_factory_recognizes_both_public_feeds(self):
        self.assertIsInstance(connector_for(self.source('jobicy')), JobicyConnector)
        self.assertIsInstance(connector_for(self.source('arbeitnow')), ArbeitnowConnector)
