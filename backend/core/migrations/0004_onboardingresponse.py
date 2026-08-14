from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_candidateprofile_onboarding_completed_at_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OnboardingResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('question_id', models.CharField(max_length=120)),
                ('target', models.CharField(db_index=True, max_length=48)),
                ('question', models.JSONField(blank=True, default=dict)),
                ('answer', models.JSONField(blank=True, default=dict)),
                ('skipped', models.BooleanField(default=False)),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at', 'id'],
                'indexes': [models.Index(fields=['owner', 'target'], name='core_onboar_owner_i_5bf9d1_idx')],
                'constraints': [models.UniqueConstraint(fields=('owner', 'question_id'), name='unique_owner_onboarding_question')],
            },
        ),
    ]
