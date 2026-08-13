from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Run migrations under a PostgreSQL advisory lock so concurrent containers start safely.'

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            call_command('migrate', interactive=False)
            return
        lock_id = 739_214_608
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(%s)', [lock_id])
            try:
                call_command('migrate', interactive=False)
            finally:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [lock_id])
