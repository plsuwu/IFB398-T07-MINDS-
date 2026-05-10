import hashlib
import os
import random
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.models import (
    ApprovalWorkflow,
    AuditLog,
    DocLink,
    Document,
    DocumentView,
    Drillhole,
    Organisation,
    Process,
    Prospect,
    Tenement,
    UserProfile,
)

from .test_document_content import (
    compliance_content,
    environmental_content,
    internal_content,
    jorc_content,
    technical_content,
    valmin_content,
)

fake = Faker()
User = get_user_model()


NUM_ORGANISATIONS = 3
NUM_USERS_PER_ORG = 4
NUM_PROCESSES_PER_ORG = 3
NUM_DRILLHOLES_PER_PROCESS = 4
NUM_PROSPECTS_PER_PROCESS = 2
NUM_TENEMENTS_PER_PROCESS = 2
NUM_DOCUMENTS_PER_PROCESS = 3
NUM_APPROVAL_WORKFLOWS = 6
NUM_AUDIT_LOGS = 20
NUM_DOCUMENT_VIEWS = 15

ORG_MODES = ["EXPLORATION", "MINING"]
PROCESS_MODES = ["PROJECT", "OPERATION"]
COMMODITIES = ["Gold", "Iron Ore", "Copper", "Lithium", "Nickel", "Zinc", "Coal"]
DOC_TYPES = ["JORC", "VALMIN", "TECHNICAL", "ENVIRONMENTAL", "COMPLIANCE", "INTERNAL"]
CONFIDENTIALITY_LEVELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
CLEARANCE_LEVELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
ROLES = ["GEOLOGIST", "MANAGER", "ANALYST", "ADMIN", "FIELD_TECH"]
DEPARTMENTS = ["Exploration", "Mining Ops", "Compliance", "Geology", "Environment"]
WORKFLOW_TYPES = ["JORC", "VALMIN"]
WORKFLOW_STATUSES = ["PENDING", "APPROVED", "REJECTED"]
AUDIT_ACTIONS = ["CREATE", "UPDATE", "DELETE", "VIEW"]
TAG_POOL = list(range(1, 20))

AU_LAT_RANGE = (-35.0, -18.0)
AU_LON_RANGE = (115.0, 150.0)

DOCTYPE_GENERATORS = {
    "JORC": jorc_content,
    "VALMIN": valmin_content,
    "TECHNICAL": technical_content,
    "ENVIRONMENTAL": environmental_content,
    "COMPLIANCE": compliance_content,
    "INTERNAL": internal_content,
}


def generate_pdf(doc_type, org, process, commodity, output_path):
    generator = DOCTYPE_GENERATORS.get(doc_type, internal_content)
    title, sections = generator(org, process, commodity or "Gold")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=25 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            spaceAfter=6 * mm,
            spaceBefore=10 * mm,
        )
    )

    story = []

    story.append(Spacer(1, 40 * mm))
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(f"Prepared for: {org.name}", styles["Normal"]))
    story.append(Paragraph(f"Project: {process.name}", styles["Normal"]))
    story.append(
        Paragraph(
            f"Date: {fake.date_this_year().strftime('%d %B %Y')}", styles["Normal"]
        )
    )
    story.append(
        Paragraph(
            f"Classification: {random.choice(CONFIDENTIALITY_LEVELS)}", styles["Normal"]
        )
    )
    story.append(Spacer(1, 20 * mm))

    meta_data = [
        ["Document Type", doc_type],
        ["Commodity", commodity or "N/A"],
        ["Organisation", org.name or "N/A"],
        ["Project / Operation", process.name or "N/A"],
        ["Prepared By", fake.name()],
        ["Reviewed By", fake.name()],
    ]
    meta_table = Table(meta_data, colWidths=[55 * mm, 100 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8e8e8")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 30 * mm))

    for heading, paragraphs in sections:
        story.append(Paragraph(heading, styles["SectionHeading"]))
        for para_text in paragraphs:
            story.append(Paragraph(para_text, styles["Normal"]))
            story.append(Spacer(1, 3 * mm))

    doc.build(story)
    return file_sha256(str(output_path))


def random_point():
    lat = random.uniform(*AU_LAT_RANGE)
    lon = random.uniform(*AU_LON_RANGE)

    return Point(lon, lat, srid=4326)


def random_multipolygon():
    cy = random.uniform(*AU_LAT_RANGE)
    cx = random.uniform(*AU_LON_RANGE)
    d = 0.05

    p = Polygon(
        (
            (cx - d, cy - d),
            (cx + d, cy - d),
            (cx + d, cy + d),
            (cx - d, cy + d),
            (cx - d, cy - d),
        ),
        srid=4326,
    )

    return MultiPolygon(p, srid=4326)


def file_sha256(path: str) -> str:
    """Compute SHA-256 of file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def fake_sha256():
    return hashlib.sha256(fake.binary(length=64)).hexdigest()


class Command(BaseCommand):
    APP_LABEL = "core"
    DOCS_DIR = Path(settings.TEST_MEDIA_ROOT) / "docs"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", dest="flush", default=False)
        parser.add_argument(
            "--no-pdfs", action="store_false", dest="gen_pdf", default=True
        )

    def _log(self, msg):
        self.stdout.write(self.style.SUCCESS(f"{msg}"))

    FLUSH_MODELS = [
        DocLink,
        DocumentView,
        AuditLog,
        ApprovalWorkflow,
        Document,
        Drillhole,
        Prospect,
        Tenement,
        Process,
        UserProfile,
        Organisation,
    ]

    def _flush(self):
        for model in self.FLUSH_MODELS:
            count, _ = model.objects.all().delete()
            self.stdout.write(f"deleted: {count} rows - {model.__name__}")

        user_count, _ = User.objects.all().delete()
        self.stdout.write(f"deleted: {user_count} users")

        group_count, _ = Group.objects.all().delete()
        self.stdout.write(f"deleted: {group_count} groups")

        if self.DOCS_DIR.exists():
            pdf_count = 0
            for pdf in self.DOCS_DIR.glob("*.pdf"):
                pdf.unlink()
                pdf_count += 1
            self.stdout.write(f"deleted: {pdf_count} PDFs (PDF dir: {self.DOCS_DIR})")

        self.stdout.write(self.style.WARNING("flushed app data\n"))

    def _create_groups(self):
        from django.db.models import Q

        group_perms = {
            "Viewers": ["view_"],
            "Editors": ["view_", "add_", "change_"],
            "Managers": ["view_", "add_", "change_", "delete_"],
        }
        groups = {}
        for group_name, prefixes in group_perms.items():
            try:
                group, created = Group.objects.get_or_create(name=group_name)
                q = Q()
                for prefix in prefixes:
                    q |= Q(codename__startswith=prefix)
                perm_ids = list(
                    Permission.objects.filter(q, content_type__app_label=self.APP_LABEL)
                    .distinct()
                    .values_list("pk", flat=True)
                )
                group.permissions.set(perm_ids)
                groups[group_name] = group
                self.stdout.write(
                    f"    {group_name}: {len(perm_ids)} permissions"
                    f" ({'created' if created else 'exists'})"
                )
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f"    FAILED on {group_name}: {exc}")
                )
        self._log(f"created: {len(groups)} groups")
        return groups

    def _create_organisations(self):
        orgs = []

        for _ in range(NUM_ORGANISATIONS):
            org = Organisation.objects.create(
                id=uuid.uuid4(),
                name=fake.company()[:32],
                mode=random.choice(ORG_MODES),
            )
            orgs.append(org)
        self._log(f"created: {len(orgs)} organisations")

        return orgs

    def _create_users(self, orgs, groups):
        users = []
        su, _ = User.objects.get_or_create(
            username="admin",
            defaults=dict(
                email="admin@example.com",
                first_name="Admin",
                last_name="User",
                is_superuser=True,
                is_staff=True,
            ),
        )
        if _:
            su.set_password("admin123")
            su.save()
        users.append(su)
        self._log("created: admin / admin123")

        for org in orgs:
            for i in range(NUM_USERS_PER_ORG):
                is_manager = i == 0
                first = fake.first_name()
                last = fake.last_name()

                suffix = fake.unique.random_int(min=100, max=9999)
                username = f"{first.lower()}.{last.lower()}.{suffix}"[:150]

                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@{fake.free_email_domain()}",
                    password="testpass123",
                    first_name=first,
                    last_name=last,
                    is_staff=is_manager,
                )

                group_key = (
                    "Managers" if is_manager else random.choice(["Viewers", "Editors"])
                )
                user.groups.add(groups[group_key])

                UserProfile.objects.update_or_create(
                    user=user,
                    defaults=dict(
                        organisation=org,
                        role="MANAGER" if is_manager else random.choice(ROLES),
                        clearance_level=random.choice(CLEARANCE_LEVELS),
                        department=random.choice(DEPARTMENTS),
                        phone=fake.phone_number()[:32],
                        employee_id=f"EMP-{fake.unique.random_int(min=1000, max=9999)}",
                        can_approve_jorc=is_manager,
                        can_approve_valmin=is_manager,
                    ),
                )
                users.append(user)

        # Create one Competent Person per org (named account for JORC governance)
        for org in orgs:
            cp_username = f"competent.person.{org.name.lower().replace(' ', '_')[:20]}"
            cp_user, created = User.objects.get_or_create(
                username=cp_username[:150],
                defaults=dict(
                    email=f"{cp_username}@example.com",
                    first_name="Competent",
                    last_name="Person",
                    is_staff=True,
                ),
            )
            if created:
                cp_user.set_password("testpass123")
                cp_user.save()
            UserProfile.objects.update_or_create(
                user=cp_user,
                defaults=dict(
                    organisation=org,
                    role=UserProfile.RoleChoices.COMPETENT_PERSON,
                    clearance_level=UserProfile.ClearanceLevel.JORC_APPROVED,
                    can_approve_jorc=True,
                    can_approve_valmin=False,
                    employee_id=f"CP-{fake.unique.random_int(min=1000, max=9999)}",
                ),
            )
            users.append(cp_user)
            self._log(f"created: Competent Person for {org.name} — {cp_username} / testpass123")

        self._log(f"created: {len(users)} users + profiles")
        return users

    def _create_processes(self, orgs):
        processes = []
        for org in orgs:
            for _ in range(NUM_PROCESSES_PER_ORG):
                p = Process.objects.create(
                    id=uuid.uuid4(),
                    name=f"{fake.city()} {random.choice(['Mine', 'Project', 'Prospect'])}",
                    mode=random.choice(PROCESS_MODES),
                    organisation=org,
                    commodity=random.choice(COMMODITIES),
                    geom=random_multipolygon(),
                )
                processes.append(p)
        self._log(f"created: {len(processes)} processes")
        return processes

    def _create_drillholes(self, processes):
        holes = []
        for proc in processes:
            for i in range(NUM_DRILLHOLES_PER_PROCESS):
                h = Drillhole.objects.create(
                    id=uuid.uuid4(),
                    name=f"DH-{proc.name[:8].upper().replace(' ', '')}-{i + 1:03d}",
                    organisation=proc.organisation,
                    process=proc,
                    azimuth=round(random.uniform(0, 360), 2),
                    dip=round(random.uniform(-90, 0), 2),
                    depth=round(random.uniform(50, 800), 2),
                    collar_location=random_point(),
                )
                holes.append(h)
        self._log(f"created: {len(holes)} drillholes")
        return holes

    def _create_prospects(self, processes):
        MINERALISATION_STYLES = [
            "shear-hosted gold", "orogenic gold", "porphyry copper-gold",
            "IOCG", "epithermal gold-silver", "skarn", "VMS", "sediment-hosted copper",
        ]
        EXPLORATION_TARGETS = [
            "extend the known resource along strike",
            "test the depth extent of the mineralised corridor",
            "identify additional lodes beneath the transported cover",
            "delineate the footprint of the anomaly for drill targeting",
            "confirm continuity of the high-grade shoot identified in Phase 1",
        ]

        prospects = []
        for proc in processes:
            for _ in range(NUM_PROSPECTS_PER_PROCESS):
                style = random.choice(MINERALISATION_STYLES)
                commodity = proc.commodity or "gold"
                hypothesis = (
                    f"Structural mapping and geochemical sampling indicate a {style} "
                    f"mineralisation system associated with the regional fault corridor. "
                    f"Elevated {commodity} values in rock chips and soils define a "
                    f"{round(random.uniform(0.5, 4.0), 1)} km trend with anomalous "
                    f"pathfinder elements suggestive of a significant discovery."
                )
                objective = (
                    f"The primary objective is to {random.choice(EXPLORATION_TARGETS)} "
                    f"and establish an inferred resource base sufficient to support a "
                    f"maiden drilling programme. Secondary objective: assess metallurgical "
                    f"recovery potential for {commodity}."
                )
                pr = Prospect.objects.create(
                    id=uuid.uuid4(),
                    name=f"{fake.last_name()} {random.choice(['Lode', 'Reef', 'Deposit', 'Zone'])}",
                    organisation=proc.organisation,
                    process=proc,
                    hypothesis=hypothesis,
                    objective=objective,
                    geom=random_point(),
                )
                prospects.append(pr)
        self._log(f"created: {len(prospects)} prospects")
        return prospects

    def _create_tenements(self, processes):
        tenements = []
        for proc in processes:
            for j in range(NUM_TENEMENTS_PER_PROCESS):
                t = Tenement.objects.create(
                    id=uuid.uuid4(),
                    name=f"ML-{random.randint(1000, 9999)}/{random.randint(1, 99):02d}",
                    organisation=proc.organisation,
                    process=proc,
                    geom=random_multipolygon(),
                )
                tenements.append(t)
        self._log(f"created: {len(tenements)} tenements")
        return tenements

    def _create_documents(self, processes, users):
        self.DOCS_DIR.mkdir(parents=True, exist_ok=True)

        docs = []

        for proc in processes:
            org_users = [
                u
                for u in users
                if hasattr(u, "userprofile")
                and getattr(u.userprofile, "organisation_id", None)
                == proc.organisation_id
            ]
            if not org_users:
                org_users = users[:1]

            for _ in range(NUM_DOCUMENTS_PER_PROCESS):
                doc_id = uuid.uuid4()
                doc_type = random.choice(DOC_TYPES)

                filename = f"{doc_type.lower()}_{doc_id.hex[:8]}.pdf"
                canonical_path = self.DOCS_DIR / filename
                rel_path = f"docs/{filename}"  # relative to 'settings.TEST_MEDIA_ROOT directory'

                checksum = generate_pdf(
                    doc_type=doc_type,
                    org=proc.organisation,
                    process=proc,
                    commodity=proc.commodity,
                    output_path=str(canonical_path),
                )

                d = Document.objects.create(
                    id=doc_id,
                    title=fake.sentence(nb_words=5)[:64],
                    file=rel_path,
                    tags=sorted(random.sample(TAG_POOL, k=random.randint(1, 4))),
                    timestamp=fake.date_between(start_date="-2y", end_date="today"),
                    doc_type=doc_type,
                    confidentiality=random.choice(CONFIDENTIALITY_LEVELS),
                    checksum_sha256=checksum,
                    created_by=random.choice(org_users),
                    organisation=proc.organisation,
                    process=proc,
                )
                docs.append(d)
        self._log(f"created: {len(docs)} documents")
        return docs

    def _create_approval_workflows(self, docs, users):
        ct = ContentType.objects.get_for_model(Document)
        managers = [u for u in users if u.is_staff]
        workflows = []
        for doc in random.sample(docs, k=min(NUM_APPROVAL_WORKFLOWS, len(docs))):
            submitted = timezone.now() - timedelta(days=random.randint(1, 60))
            status = random.choice(WORKFLOW_STATUSES)
            wf = ApprovalWorkflow.objects.create(
                object_id=doc.id,
                content_type=ct,
                workflow_type=random.choice(WORKFLOW_TYPES),
                status=status,
                submission_notes=fake.paragraph(nb_sentences=2),
                approval_notes=fake.paragraph(nb_sentences=1)
                if status != "PENDING"
                else "",
                submitted_at=submitted,
                submitted_by=random.choice(users),
                reviewed_at=submitted + timedelta(days=random.randint(1, 14))
                if status != "PENDING"
                else None,
                approved_by=random.choice(managers) if status != "PENDING" else None,
            )
            workflows.append(wf)
        self._log(f"created: {len(workflows)} approval workflows")

    def _create_audit_logs(self, docs, users):
        ct = ContentType.objects.get_for_model(Document)
        for _ in range(NUM_AUDIT_LOGS):
            doc = random.choice(docs)
            AuditLog.objects.create(
                action=random.choice(AUDIT_ACTIONS),
                object_id=doc.id,
                content_type=ct,
                user=random.choice(users),
                description=fake.sentence(),
                ip_address=fake.ipv4_private(),
                user_agent=fake.user_agent(),
                timestamp=timezone.now() - timedelta(days=random.randint(0, 90)),
            )

        self._log("created: audit log entries")

    def _create_document_views(self, docs, users):
        for _ in range(NUM_DOCUMENT_VIEWS):
            DocumentView.objects.create(
                document=random.choice(docs),
                user=random.choice(users),
                viewed_at=timezone.now() - timedelta(days=random.randint(0, 30)),
                ip_address=fake.ipv4_private(),
            )
        self._log("created: document views")

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("seeding database\n"))

        self._log(options)

        if options["flush"]:
            self._flush()
            return

        groups = self._create_groups()
        orgs = self._create_organisations()
        users = self._create_users(orgs, groups)
        processes = self._create_processes(orgs)
        drillholes = self._create_drillholes(processes)
        prospects = self._create_prospects(processes)
        tenements = self._create_tenements(processes)

        if options["gen_pdf"]:
            docs = self._create_documents(processes, users)

            self._create_approval_workflows(docs, users)
            self._create_audit_logs(docs, users)
            self._create_document_views(docs, users)

        else:
            docs = []

        total = sum(
            [
                len(orgs),
                len(users),
                len(processes),
                len(drillholes),
                len(prospects),
                len(tenements),
                len(docs),
                NUM_APPROVAL_WORKFLOWS,
                NUM_AUDIT_LOGS,
                NUM_DOCUMENT_VIEWS,
            ]
        )
        self.stdout.write(self.style.SUCCESS(f"complete: {total} objects created\n"))
