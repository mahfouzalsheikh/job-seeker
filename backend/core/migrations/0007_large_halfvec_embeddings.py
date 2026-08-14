from django.db import migrations
import pgvector.django.halfvec


EMBEDDED_MODELS = ('CandidateProfile', 'ProfileFact', 'JobPosting')


def clear_embeddings_and_drop_indexes(apps, schema_editor):
    for model_name in EMBEDDED_MODELS:
        apps.get_model('core', model_name).objects.update(
            semantic_embedding=None,
            embedding_model='',
            embedding_provider='',
            embedding_content_hash='',
            embedding_updated_at=None,
        )
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP INDEX IF EXISTS core_job_semantic_hnsw')
        cursor.execute('DROP INDEX IF EXISTS core_fact_semantic_hnsw')


def create_halfvec_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'CREATE INDEX core_job_semantic_hnsw '
            'ON core_jobposting USING hnsw (semantic_embedding halfvec_cosine_ops) '
            'WHERE semantic_embedding IS NOT NULL'
        )
        cursor.execute(
            'CREATE INDEX core_fact_semantic_hnsw '
            'ON core_profilefact USING hnsw (semantic_embedding halfvec_cosine_ops) '
            'WHERE semantic_embedding IS NOT NULL'
        )


class Migration(migrations.Migration):
    dependencies = [('core', '0006_remove_legacy_json_embeddings')]

    operations = [
        migrations.RunPython(clear_embeddings_and_drop_indexes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='candidateprofile',
            name='semantic_embedding',
            field=pgvector.django.halfvec.HalfVectorField(blank=True, dimensions=3072, null=True),
        ),
        migrations.AlterField(
            model_name='profilefact',
            name='semantic_embedding',
            field=pgvector.django.halfvec.HalfVectorField(blank=True, dimensions=3072, null=True),
        ),
        migrations.AlterField(
            model_name='jobposting',
            name='semantic_embedding',
            field=pgvector.django.halfvec.HalfVectorField(blank=True, dimensions=3072, null=True),
        ),
        migrations.RunPython(create_halfvec_indexes, clear_embeddings_and_drop_indexes),
    ]
