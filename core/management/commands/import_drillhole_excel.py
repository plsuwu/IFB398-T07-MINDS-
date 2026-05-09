from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.importers import run_drillhole_import
from core.models import Organisation, Process


class Command(BaseCommand):
    help = "Import drillhole collar, survey, lithology, and assay data from a .xlsx workbook."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the .xlsx workbook.")
        parser.add_argument("--organisation", required=True, help="Exact Organisation name.")
        parser.add_argument("--process", required=True, help="Exact Process name within that organisation.")
        parser.add_argument("--dry-run", action="store_true", default=False,
                            help="Parse and validate without writing to the database.")
        parser.add_argument("--update", action="store_true", default=False,
                            help="Update existing Drillhole records matched by HOLEID.")

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        try:
            org = Organisation.objects.get(name=options["organisation"])
        except Organisation.DoesNotExist:
            raise CommandError(f"Organisation '{options['organisation']}' not found.")
        except Organisation.MultipleObjectsReturned:
            raise CommandError(f"Multiple organisations match '{options['organisation']}'.")

        try:
            process = Process.objects.get(name=options["process"], organisation=org)
        except Process.DoesNotExist:
            raise CommandError(f"Process '{options['process']}' not found in '{org.name}'.")

        self.stdout.write(f"Opening workbook: {file_path}")

        result = run_drillhole_import(
            file_path,
            org=org,
            process=process,
            dry_run=options["dry_run"],
            update=options["update"],
            warn=self.stderr.write,
        )

        c = result["counters"]
        dry_label = " [DRY RUN — no data written]" if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"\nImport complete{dry_label}"))
        self.stdout.write(
            f"  Drillhole collars : +{c['collars_created']} created, "
            f"{c['collars_updated']} updated, {c['collars_skipped']} skipped, "
            f"{c['collars_errors']} errors"
        )
        self.stdout.write(f"  Survey readings  : +{c['surveys_created']} created, {c['surveys_errors']} errors")
        self.stdout.write(f"  Lithology rows   : +{c['litho_created']} created, {c['litho_errors']} errors")
        self.stdout.write(f"  Assay rows       : +{c['assay_created']} created, {c['assay_errors']} errors")
