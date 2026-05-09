from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_drillhole_comments_drillhole_company_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='drillhole',
            name='prospect',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='drillholes',
                to='core.prospect',
            ),
        ),
    ]
