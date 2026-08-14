from django.db import migrations, models
import pgvector.django.vector


def enable_vector(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')


def create_vector_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS core_job_semantic_hnsw '
            'ON core_jobposting USING hnsw (semantic_embedding vector_cosine_ops) '
            'WHERE semantic_embedding IS NOT NULL'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS core_fact_semantic_hnsw '
            'ON core_profilefact USING hnsw (semantic_embedding vector_cosine_ops) '
            'WHERE semantic_embedding IS NOT NULL'
        )


def drop_vector_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP INDEX IF EXISTS core_job_semantic_hnsw')
        cursor.execute('DROP INDEX IF EXISTS core_fact_semantic_hnsw')


class Migration(migrations.Migration):
    dependencies = [('core', '0004_onboardingresponse')]

    operations = [
        migrations.RunPython(enable_vector, migrations.RunPython.noop),
        migrations.AddField(
            model_name='candidateprofile',
            name='embedding_content_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name='candidateprofile',
            name='embedding_model',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='candidateprofile',
            name='embedding_provider',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='candidateprofile',
            name='embedding_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='candidateprofile',
            name='semantic_embedding',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=1536, null=True),
        ),
        migrations.AddField(
            model_name='jobposting',
            name='embedding_content_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name='jobposting',
            name='embedding_model',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='jobposting',
            name='embedding_provider',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='jobposting',
            name='embedding_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='jobposting',
            name='semantic_embedding',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=1536, null=True),
        ),
        migrations.AddField(
            model_name='profilefact',
            name='embedding_content_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name='profilefact',
            name='embedding_model',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='profilefact',
            name='embedding_provider',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='profilefact',
            name='embedding_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profilefact',
            name='semantic_embedding',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=1536, null=True),
        ),
        migrations.AlterField(
            model_name='matchsignal',
            name='kind',
            field=models.CharField(
                choices=[
                    ('eligibility', 'Eligibility'), ('skills', 'Skills'),
                    ('evidence', 'Experience evidence'), ('semantic', 'Semantic fit'),
                    ('direction', 'Role direction'), ('domain', 'Domain relevance'),
                    ('logistics', 'Logistics'), ('risk', 'Risk'),
                ],
                db_index=True,
                max_length=24,
            ),
        ),
        migrations.RunPython(create_vector_indexes, drop_vector_indexes),
    ]
