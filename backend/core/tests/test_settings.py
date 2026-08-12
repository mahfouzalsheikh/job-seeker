from django.conf import settings
from django.test import SimpleTestCase


class ChannelLayerSettingsTests(SimpleTestCase):
    def test_blocking_channel_reads_have_no_socket_deadline(self):
        host = settings.CHANNEL_LAYERS['default']['CONFIG']['hosts'][0]

        self.assertIsNone(host['socket_timeout'])
        self.assertEqual(host['socket_connect_timeout'], 5)
