from django.conf import settings
from django.test import SimpleTestCase


class ChannelLayerSettingsTests(SimpleTestCase):
    def test_blocking_channel_reads_have_no_socket_deadline(self):
        host = settings.CHANNEL_LAYERS['default']['CONFIG']['hosts'][0]

        self.assertIsNone(host['socket_timeout'])
        self.assertEqual(host['socket_connect_timeout'], 5)


class StaticFilesSettingsTests(SimpleTestCase):
    def test_whitenoise_serves_files_collected_during_image_build(self):
        security_middleware = settings.MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
        whitenoise_middleware = settings.MIDDLEWARE.index('whitenoise.middleware.WhiteNoiseMiddleware')

        self.assertEqual(whitenoise_middleware, security_middleware + 1)
        self.assertEqual(
            settings.STORAGES['staticfiles']['BACKEND'],
            'whitenoise.storage.CompressedStaticFilesStorage',
        )
