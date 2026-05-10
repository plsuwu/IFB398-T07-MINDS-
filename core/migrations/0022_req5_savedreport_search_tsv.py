from django.contrib.postgres.search import SearchVectorField
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # required for CREATE INDEX CONCURRENTLY

    dependencies = [
        ('core', '0021_req3_report_composer'),
    ]

    operations = [
        # 1. Add search_tsv column to saved_reports
        migrations.AddField(
            model_name='savedreport',
            name='search_tsv',
            field=SearchVectorField(blank=True, null=True),
        ),

        # 2. Create the PL/pgSQL trigger function
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION saved_reports_tsv_update()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    NEW.search_tsv :=
                        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(NEW.content_md, '')), 'B');
                    RETURN NEW;
                END;
                $$;

                DROP TRIGGER IF EXISTS saved_reports_tsv_trigger ON saved_reports;

                CREATE TRIGGER saved_reports_tsv_trigger
                BEFORE INSERT OR UPDATE ON saved_reports
                FOR EACH ROW EXECUTE FUNCTION saved_reports_tsv_update();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS saved_reports_tsv_trigger ON saved_reports;
                DROP FUNCTION IF EXISTS saved_reports_tsv_update();
            """,
        ),

        # 3. Create GIN index for fast FTS lookups
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS saved_reports_search_tsv_gin
                ON saved_reports USING GIN(search_tsv);
            """,
            reverse_sql="DROP INDEX IF EXISTS saved_reports_search_tsv_gin;",
        ),

        # 4. Backfill existing rows
        migrations.RunSQL(
            sql="""
                UPDATE saved_reports
                SET search_tsv =
                    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                    setweight(to_tsvector('english', coalesce(content_md, '')), 'B');
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
