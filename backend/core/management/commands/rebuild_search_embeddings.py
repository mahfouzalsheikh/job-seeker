from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.tasks import refresh_profile_search_task


class Command(BaseCommand):
    help = 'Rebuild pgvector candidate, profile-fact, and job embeddings, then recompute matches.'

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Only rebuild one username or email.')
        parser.add_argument('--force', action='store_true', help='Regenerate vectors even when their content hash is current.')

    def handle(self, *args, **options):
        users = get_user_model().objects.filter(candidate_profile__isnull=False).order_by('id')
        username = (options.get('username') or '').strip()
        if username:
            users = users.filter(username=username) | users.filter(email=username)
        if not users.exists():
            raise CommandError('No candidate profiles matched.')
        total_profiles = 0
        total_jobs = 0
        for user in users.distinct():
            result = refresh_profile_search_task(user.id, force=options['force'])
            total_profiles += 1
            total_jobs += result['matches']
            self.stdout.write(
                f"{user.get_username()}: {result['provider']} / {result['model']}; "
                f"{result['embedded_facts']} facts; {result['matches']} matches"
            )
        self.stdout.write(self.style.SUCCESS(f'Rebuilt {total_profiles} profile(s) and scored {total_jobs} job(s).'))
