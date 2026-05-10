import uuid
import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_req5_savedreport_search_tsv'),
    ]

    operations = [
        # 6.1 — optional polygon boundary on Prospect
        migrations.AddField(
            model_name='prospect',
            name='area_geom',
            field=django.contrib.gis.db.models.fields.PolygonField(
                blank=True,
                help_text='Optional area boundary for the prospect',
                null=True,
                srid=4326,
            ),
        ),

        # 6.3 — Sample model
        migrations.CreateModel(
            name='Sample',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=64)),
                ('sample_type', models.CharField(
                    blank=True, max_length=16,
                    choices=[
                        ('ROCK_CHIP', 'Rock Chip'), ('SOIL', 'Soil'),
                        ('STREAM_SED', 'Stream Sediment'), ('TRENCH', 'Trench'),
                        ('CORE', 'Drill Core'), ('CHANNEL', 'Channel'),
                    ],
                )),
                ('sample_number', models.CharField(blank=True, max_length=64)),
                ('location', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('depth', models.FloatField(blank=True, null=True)),
                ('description', models.TextField(blank=True)),
                ('collected_by', models.CharField(blank=True, max_length=128)),
                ('collected_at', models.DateField(blank=True, null=True)),
                ('laboratory', models.CharField(blank=True, max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organisation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='core.organisation',
                )),
                ('process', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='core.process',
                )),
                ('prospect', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='samples',
                    to='core.prospect',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # 6.3 — Survey model
        migrations.CreateModel(
            name='Survey',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=128)),
                ('survey_type', models.CharField(
                    blank=True, max_length=16,
                    choices=[
                        ('GEOPHYSICS', 'Geophysics'), ('SOIL_GRID', 'Soil Grid'),
                        ('MAPPING', 'Geological Mapping'), ('REMOTE', 'Remote Sensing'),
                    ],
                )),
                ('contractor', models.CharField(blank=True, max_length=128)),
                ('date_from', models.DateField(blank=True, null=True)),
                ('date_to', models.DateField(blank=True, null=True)),
                ('description', models.TextField(blank=True)),
                ('geom', django.contrib.gis.db.models.fields.PolygonField(
                    blank=True, help_text='Coverage area of the survey', null=True, srid=4326,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organisation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='core.organisation',
                )),
                ('process', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='core.process',
                )),
                ('prospect', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='surveys',
                    to='core.prospect',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
