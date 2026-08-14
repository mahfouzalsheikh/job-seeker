from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('core', '0005_pgvector_semantic_matching')]

    operations = [
        migrations.RemoveField(model_name='profilefact', name='embedding'),
        migrations.RemoveField(model_name='jobposting', name='embedding'),
        migrations.RemoveField(model_name='profilechunk', name='embedding'),
    ]
