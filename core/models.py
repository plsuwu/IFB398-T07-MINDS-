# from django.utils import timezone
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


class ChoiceValidationMixin:
    """
    Automatically handle validation of choice fields
    """

    def clean(self):
        super().clean()
        for field in self._meta.fields:
            if field.choices:
                field_value = getattr(self, field.name)
                valid_choices = [choice[0] for choice in field.choices]
                if field_value not in valid_choices:
                    raise ValidationError(
                        {
                            field.name: f"invalid value for {field.name}"
                            f"(expected one of {valid_choices})"
                        }
                    )


class AutoCleanMixin:
    """
    Override `save()` method to run `full_clean()` prior to calling `save()`
    """

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ValidatedChoiceModel(ChoiceValidationMixin, AutoCleanMixin, models.Model):
    """
    Abstract base Model to handle automatic choice validation
    """

    class Meta:
        abstract = True


# class Organisation(models.Model):
class Organisation(ValidatedChoiceModel):
    class Mode(models.TextChoices):
        EXPLORATION = "EXPLORATION", _("Exploration")
        MINING = "MINING", _("Mining")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, null=False)
    name = models.CharField(max_length=32, null=True)
    mode = models.CharField(choices=Mode, default=Mode.EXPLORATION)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(mode__in=["EXPLORATION", "MINING"]),
                name="valid_organisation_mode",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.mode})" if self.name else f"Organisation ({self.mode})"

    def __repr__(self):
        return f"Organisation(id={self.id},name={self.name},mode={self.mode})"


# TODO:
#  I feel like this is better named something like 'Campaign' or 'Activity' for
#  the sake of clarity
class Process(ValidatedChoiceModel):
    class ProcessType(models.TextChoices):
        PROJECT = "PROJECT", _("Project")
        OPERATION = "OPERATION", _("Operation")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, null=False)
    name = models.CharField(max_length=64, null=True)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, null=True, blank=True)
    mode = models.CharField(choices=ProcessType, default=ProcessType.PROJECT)

    geom = models.MultiPolygonField(srid=4326, null=True, blank=True)
    commodity = models.CharField(max_length=64, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(mode__in=["PROJECT", "OPERATION"]),
                name="valid_process_mode",
            )
        ]

    def __str__(self):
        return self.name if self.name else f"Process {self.id}"

    def __repr__(self):
        return (
            f"Process(id={self.id},name={self.name},organisation={self.organisation},"
            f"mode={self.mode},geom={self.geom},commodity={self.commodity},"
            f"created_at={self.created_at},updated_at={self.updated_at})"
        )


class Prospect(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, null=False)
    name = models.CharField(max_length=64, null=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    process = models.ForeignKey(Process, on_delete=models.CASCADE)

    hypothesis = models.TextField()
    objective = models.TextField()

    # Geospatial field — prospect location (point) or area (polygon)
    geom = models.PointField(srid=4326, null=True, blank=True)
    area_geom = models.PolygonField(
        srid=4326, null=True, blank=True,
        help_text="Optional area boundary for the prospect"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        errors = {}
        if not self.hypothesis or not self.hypothesis.strip():
            errors["hypothesis"] = "A geological hypothesis is required."
        if not self.objective or not self.objective.strip():
            errors["objective"] = "An exploration objective is required."
        if not self.geom:
            errors["geom"] = "A mapped location is required."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def __repr__(self):
        return (
            f"Prospect(id={self.id},name={self.name},organisation={self.organisation},"
            f"process={self.process},created_at={self.created_at},updated_at={self.updated_at})"
        )


class Tenement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, null=False)
    name = models.CharField(max_length=64, null=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    process = models.ForeignKey(Process, on_delete=models.CASCADE)

    # Geospatial field - tenement boundaries (mining lease/exploration license)
    geom = models.MultiPolygonField(srid=4326, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def __repr__(self):
        return (
            f"Tenement(id={self.id},name={self.name},organisation={self.organisation},"
            f"process={self.process},created_at={self.created_at},updated_at={self.updated_at}"
        )


class Drillhole(models.Model):

    class DrillType(models.TextChoices):
        RC  = "RC",  _("Reverse Circulation")
        DDH = "DDH", _("Diamond Drill Hole")
        RAB = "RAB", _("Rotary Air Blast")
        AC  = "AC",  _("Air Core")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, null=False)
    name = models.CharField(max_length=64, null=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    process = models.ForeignKey(Process, on_delete=models.CASCADE)
    prospect = models.ForeignKey(
        'Prospect',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drillholes',
    )

    # Geospatial — collar point in WGS84
    collar_location = models.PointField(srid=4326, null=True, blank=True)

    # Original drillhole survey data (collar reading)
    depth   = models.FloatField(null=True, blank=True, help_text="Total depth in meters")
    azimuth = models.FloatField(null=True, blank=True, help_text="Bearing true north (0-360 degrees)")
    dip     = models.FloatField(null=True, blank=True, help_text="Dip angle (-90 to 90 degrees, negative = downward)")

    # Extended collar metadata (populated by import command)
    drill_type     = models.CharField(max_length=8, choices=DrillType.choices, blank=True)
    company        = models.CharField(max_length=128, blank=True)
    drill_company  = models.CharField(max_length=128, blank=True)
    current_epm    = models.CharField(max_length=64, blank=True)
    original_epm   = models.CharField(max_length=64, blank=True)
    year_report    = models.PositiveSmallIntegerField(null=True, blank=True)
    company_report = models.CharField(max_length=64, blank=True)
    elevation      = models.FloatField(null=True, blank=True, help_text="Collar elevation (RL) in metres")
    date_commenced = models.DateField(null=True, blank=True)
    date_completed = models.DateField(null=True, blank=True)
    hole_id_original = models.CharField(max_length=64, blank=True)
    comments       = models.TextField(blank=True)

    # Coordinate provenance — raw source values before WGS84 transformation
    source_crs      = models.CharField(max_length=32, blank=True, help_text="e.g. EPSG:28356")
    source_easting  = models.FloatField(null=True, blank=True)
    source_northing = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def __repr__(self):
        return (
            f"Drillhole(id={self.id},name={self.name},organisation={self.organisation},"
            f"process={self.process},created_at={self.created_at},updated_at={self.updated_at}"
        )


class DrillholeSurvey(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    drillhole = models.ForeignKey(Drillhole, on_delete=models.CASCADE, related_name="surveys")
    depth     = models.FloatField(help_text="Metres down hole")
    dip       = models.FloatField(null=True, blank=True, help_text="Dip angle in degrees")
    azimuth_tn  = models.FloatField(null=True, blank=True, help_text="Azimuth true north (0-360)")
    azimuth_mag = models.FloatField(null=True, blank=True, help_text="Azimuth magnetic (0-360)")
    comment   = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ["drillhole", "depth"]

    def __str__(self):
        return f"{self.drillhole.name} @ {self.depth}m"


class LithologyInterval(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    drillhole = models.ForeignKey(Drillhole, on_delete=models.CASCADE, related_name="lithology")
    from_depth = models.FloatField()
    to_depth   = models.FloatField()
    lithology  = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    mineralisation   = models.CharField(max_length=128, blank=True)
    hardness         = models.CharField(max_length=64, blank=True)
    weathering       = models.CharField(max_length=64, blank=True)
    acid_reaction    = models.CharField(max_length=64, blank=True)
    colour           = models.CharField(max_length=64, blank=True)
    oxidation        = models.CharField(max_length=64, blank=True)
    mineralisation_b = models.CharField(max_length=128, blank=True,
                           help_text="Second mineralisation column from source (col L)")
    mineralisation_2 = models.CharField(max_length=128, blank=True)
    alteration       = models.CharField(max_length=128, blank=True)
    alteration_2     = models.CharField(max_length=128, blank=True)
    veins            = models.CharField(max_length=128, blank=True)
    recovery_pct     = models.CharField(max_length=32, blank=True)
    core_size        = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["drillhole", "from_depth"]

    def __str__(self):
        return f"{self.drillhole.name} {self.from_depth}–{self.to_depth}m: {self.lithology}"


class AssayResult(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True)
    drillhole = models.ForeignKey(Drillhole, on_delete=models.CASCADE, related_name="assays")
    from_depth = models.FloatField()
    to_depth   = models.FloatField()
    lab_batch_number = models.CharField(max_length=64, blank=True)
    sample_number    = models.CharField(max_length=64, blank=True)
    comment          = models.CharField(max_length=256, blank=True)

    # Assay values — nullable floats; negative values denote below-detection-limit
    au_ppm       = models.FloatField(null=True, blank=True)
    au_ppm_check1 = models.FloatField(null=True, blank=True)
    au_ppm_check2 = models.FloatField(null=True, blank=True)
    cu_ppm  = models.FloatField(null=True, blank=True)
    pb_ppm  = models.FloatField(null=True, blank=True)
    zn_ppm  = models.FloatField(null=True, blank=True)
    ag_ppm  = models.FloatField(null=True, blank=True)
    as_ppm  = models.FloatField(null=True, blank=True)
    bi_ppm  = models.FloatField(null=True, blank=True)
    cd_ppm  = models.FloatField(null=True, blank=True)
    sb_ppm  = models.FloatField(null=True, blank=True)
    mn_ppm  = models.FloatField(null=True, blank=True)
    mo_ppm  = models.FloatField(null=True, blank=True)
    pt_ppb  = models.FloatField(null=True, blank=True)
    pd_ppb  = models.FloatField(null=True, blank=True)

    # Analysis metadata
    laboratory  = models.CharField(max_length=64, blank=True)
    au_method   = models.CharField(max_length=32, blank=True)
    cu_method   = models.CharField(max_length=32, blank=True)
    cu_method_2 = models.CharField(max_length=32, blank=True)
    pb_method   = models.CharField(max_length=32, blank=True)
    zn_method   = models.CharField(max_length=32, blank=True)
    ag_method   = models.CharField(max_length=32, blank=True)
    as_method   = models.CharField(max_length=32, blank=True)
    bi_method   = models.CharField(max_length=32, blank=True)
    cd_method   = models.CharField(max_length=32, blank=True)
    sb_method   = models.CharField(max_length=32, blank=True)
    mn_method   = models.CharField(max_length=32, blank=True)
    mo_method   = models.CharField(max_length=32, blank=True)
    pt_method   = models.CharField(max_length=32, blank=True)
    pd_method   = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["drillhole", "from_depth"]

    def __str__(self):
        return f"{self.drillhole.name} {self.from_depth}–{self.to_depth}m"


class Document(models.Model):
    REPORTING_STAGE_CHOICES = [
        ("EARLY_EXPLORATION", "Early Exploration"),
        ("RESOURCE_DEFINITION", "Resource Definition"),
        ("FEASIBILITY", "Feasibility"),
        ("DEVELOPMENT", "Development / Mining"),
        ("REHABILITATION", "Rehabilitation / Closure"),
    ]

    id = models.UUIDField(default=uuid.uuid4, unique=True, null=False, primary_key=True)
    title = models.CharField(max_length=64)

    # filename = models.FileField(upload_to="docs/")
    file = models.FileField(upload_to="docs/")
    extracted_text = models.TextField(blank=True, default="")
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, null=True, blank=True)
    process = models.ForeignKey(Process, null=True, on_delete=models.SET_NULL, blank=True)
    tags = ArrayField(models.IntegerField(), default=list, blank=True)
    analysis_text = models.TextField(blank=True, default="")
    
    timestamp = models.DateField(null=True)
    doc_type = models.CharField(max_length=64, blank=True)
    confidentiality = models.CharField(max_length=64, default="internal")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True
    )

    checksum_sha256 = models.CharField(max_length=64, db_index=True, blank=True)
    search_tsv = SearchVectorField(null=True, blank=True)   # populated by DB trigger
    extracted_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Versioning
    version_number  = models.PositiveIntegerField(default=1)
    parent_document = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='versions'
    )
    is_latest = models.BooleanField(default=True, db_index=True)

    # Extended metadata
    tenement = models.ForeignKey(
        'Tenement', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='documents'
    )
    commodity      = models.CharField(max_length=64, blank=True)
    reporting_stage = models.CharField(
        max_length=32, blank=True,
        choices=REPORTING_STAGE_CHOICES,
    )
    author_name = models.CharField(
        max_length=128, blank=True,
        help_text="Free-text author name for imported or legacy documents",
    )

    @classmethod
    def create_version(cls, parent: 'Document', new_file, user) -> 'Document':
        """Upload a new file version; marks parent as non-latest."""
        from .utils import sha256_file, extract_text, chunk_text
        checksum = sha256_file(new_file)
        if cls.objects.filter(checksum_sha256=checksum).exists():
            raise ValueError("Identical file already exists.")
        parent.is_latest = False
        parent.save(update_fields=["is_latest"])
        doc = cls.objects.create(
            title=parent.title,
            file=new_file,
            organisation=parent.organisation,
            process=parent.process,
            tags=parent.tags,
            timestamp=parent.timestamp,
            doc_type=parent.doc_type,
            confidentiality=parent.confidentiality,
            created_by=user,
            checksum_sha256=checksum,
            version_number=parent.version_number + 1,
            parent_document=parent,
            is_latest=True,
            tenement=parent.tenement,
            commodity=parent.commodity,
            reporting_stage=parent.reporting_stage,
            author_name=parent.author_name,
        )
        text = extract_text(new_file)
        doc.extracted_text = text or ""
        doc.save(update_fields=["extracted_text"])
        if text:
            chunks = chunk_text(text)
            DocumentChunk.objects.bulk_create([
                DocumentChunk(
                    document=doc,
                    chunk_index=i,
                    text=chunk,
                    process=doc.process,
                    doc_type=doc.doc_type,
                    timestamp=doc.timestamp,
                )
                for i, chunk in enumerate(chunks)
            ])
        return doc

    def get_version_family(self):
        """Return all versions in this document's chain, ordered by version_number."""
        root = self
        visited = set()
        while root.parent_document_id and root.pk not in visited:
            visited.add(root.pk)
            root = root.parent_document
        chain = []
        queue = [root]
        seen = set()
        while queue:
            current = queue.pop(0)
            if current.pk in seen:
                break
            seen.add(current.pk)
            chain.append(current)
            for child in current.versions.select_related("created_by").order_by("version_number"):
                if child.pk not in seen:
                    queue.append(child)
        return sorted(chain, key=lambda d: d.version_number)

    def save(self, *args, **kwargs):
        # Compute SHA-256 checksum if file exists and checksum not already set
        if self.file and not self.checksum_sha256:
            from .utils import sha256_file
            self.checksum_sha256 = sha256_file(self.file)
        # Ensure extracted_text is never NULL
        if self.extracted_text is None:
            self.extracted_text = ""
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Delete the file from storage (MinIO) before deleting the database record
        if self.file:
            try:
                self.file.delete(save=False)
            except Exception as e:
                # Log the error but continue with deletion
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete file {self.file.name} from storage: {e}")
        super().delete(*args, **kwargs)

    def __str__(self):
        return self.title

    def __repr__(self):
        return (
            f"Document(id={self.id},title={self.title},filepath={self.file},"
            f"organisation={self.organisation},process={self.process},"
            f"doc_type={self.doc_type},confidentiality={self.confidentiality},"
            f"checksum_sha256={self.checksum_sha256},created_by={self.created_by},"
            f"created_at={self.created_at},"
        )

class DocumentChunk(models.Model):
    """
    Stores document text split into overlapping chucnks for RAG retrival.
    Metadata fields are copied from the parent doc for fast filtering.
    """

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()

    # copy from parent doc for fast filter
    process = models.ForeignKey(
        Process,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    doc_type = models.CharField(max_length=64, blank=True)
    timestamp = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["document", "chunk_index"]
        indexes = [
            models.Index(fields=["process"], name='core_docume_process_f5b3f3_idx'),
            models.Index(fields=["doc_type"], name='core_docume_doc_typ_499972_idx'),
            models.Index(fields=["timestamp"], name='core_docume_timesta_294cd6_idx'),
        ]
    
    def __str__(self):
        return f"{self.document.title} - chunk {self.chunk_index}"


# USER PROFILE & PERMISSIONS ---------------------------------

class UserProfile(models.Model):
    """Extended user attributes for mining/exploration governance"""

    class RoleChoices(models.TextChoices):
        # Exploration roles
        GEOLOGIST_EXPL = "GEOLOGIST_EXPL", _("Geologist (Exploration)")
        FIELD_LEAD = "FIELD_LEAD", _("Field Lead")
        DATA_MANAGER = "DATA_MANAGER", _("Data Manager")

        # Mining roles
        GEOLOGIST_MINE = "GEOLOGIST_MINE", _("Mine Geologist")
        METALLURGIST = "METALLURGIST", _("Metallurgist")
        OPERATIONS_MANAGER = "OPS_MANAGER", _("Operations Manager")

        # Admin/Other
        ADMIN = "ADMIN", _("Administrator")
        VIEWER = "VIEWER", _("Viewer Only")

        # Governance (cross-cutting)
        COMPETENT_PERSON = "COMPETENT_PERSON", _("Competent Person")

    class ClearanceLevel(models.TextChoices):
        PUBLIC = "PUBLIC", _("Public")
        INTERNAL = "INTERNAL", _("Internal")
        CONFIDENTIAL = "CONFIDENTIAL", _("Confidential")
        JORC_APPROVED = "JORC_APPROVED", _("JORC Approved Personnel")

    # Core fields
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, null=True, blank=True)
    role = models.CharField(max_length=32, choices=RoleChoices.choices, default=RoleChoices.VIEWER)
    clearance_level = models.CharField(
        max_length=32,
        choices=ClearanceLevel.choices,
        default=ClearanceLevel.INTERNAL
    )

    # Optional metadata - We need to decide if this is needed*********
    department = models.CharField(max_length=64, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    employee_id = models.CharField(max_length=32, blank=True, unique=True, null=True)

    # Workflow permissions
    can_approve_jorc = models.BooleanField(default=False, help_text="Can approve JORC compliance workflows")
    can_approve_valmin = models.BooleanField(default=False, help_text="Can approve VALMIN compliance workflows")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    def is_exploration_role(self):
        """Check if user has an exploration role"""
        return self.role in [
            self.RoleChoices.GEOLOGIST_EXPL,
            self.RoleChoices.FIELD_LEAD,
            self.RoleChoices.DATA_MANAGER,
        ]

    def is_mining_role(self):
        """Check if user has a mining role"""
        return self.role in [
            self.RoleChoices.GEOLOGIST_MINE,
            self.RoleChoices.METALLURGIST,
            self.RoleChoices.OPERATIONS_MANAGER,
        ]

    def can_access_document(self, document):
        """Attribute-based access control for documents"""
        # Same organisation check
        if document.organisation and document.organisation != self.organisation:
            return False

        # Clearance level check
        doc_clearance_hierarchy = {
            'public': 0,
            'internal': 1,
            'confidential': 2,
            'jorc_restricted': 3,
        }
        user_clearance_hierarchy = {
            self.ClearanceLevel.PUBLIC: 0,
            self.ClearanceLevel.INTERNAL: 1,
            self.ClearanceLevel.CONFIDENTIAL: 2,
            self.ClearanceLevel.JORC_APPROVED: 3,
        }

        doc_level = doc_clearance_hierarchy.get(document.confidentiality.lower() if document.confidentiality else 'internal', 0)
        user_level = user_clearance_hierarchy.get(self.clearance_level, 0)

        return user_level >= doc_level


class SavedReport(models.Model):
    """An AI generated report, editable and savable into the database."""

    class ChangeReason(models.TextChoices):
        GENERATED   = "GENERATED",   _("AI Generated")
        MANUAL_EDIT = "MANUAL_EDIT", _("Manual Edit")
        REGENERATED = "REGENERATED", _("Regenerated")

    class Status(models.TextChoices):
        DRAFT        = "DRAFT",        _("Draft")
        UNDER_REVIEW = "UNDER_REVIEW", _("Under Review")
        APPROVED     = "APPROVED",     _("Approved")
        PUBLISHED    = "PUBLISHED",    _("Published")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    process = models.ForeignKey(
        Process, on_delete=models.SET_NULL, null=True, blank=True, related_name="saved_reports"
    )
    prospect = models.ForeignKey(
        'Prospect',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports',
    )
    organisation = models.ForeignKey(
        Organisation, on_delete=models.SET_NULL, null=True, blank=True
    )
    title = models.CharField(max_length=256)
    content_md = models.TextField()
    search_tsv = SearchVectorField(null=True, blank=True)  # populated by DB trigger
    clearance_level = models.CharField(
        max_length=32,
        choices=UserProfile.ClearanceLevel.choices,
        default="INTERNAL",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version_number = models.PositiveIntegerField(default=1)
    content_hash   = models.CharField(max_length=64, blank=True)
    change_reason  = models.CharField(
        max_length=16, choices=ChangeReason.choices, default=ChangeReason.GENERATED
    )
    change_summary = models.TextField(blank=True)
    parent_version = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_versions'
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    source_documents = models.ManyToManyField(
        'Document', blank=True, related_name='cited_in_reports'
    )
    approval_workflow = models.OneToOneField(
        'ApprovalWorkflow', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='report'
    )

    class Meta:
        db_table = "saved_reports"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.created_at:%Y-%m-%d})"
    
    @classmethod
    def create_version(cls, parent: 'SavedReport', content_md: str, user, reason: str, summary=""):
        import hashlib
        content_hash = hashlib.sha256(content_md.encode()).hexdigest()

        # Don't save if content hasn't changed
        if parent.content_hash == content_hash:
            return parent

        return cls.objects.create(
            process=parent.process,
            prospect=parent.prospect,
            organisation=parent.organisation,
            title=parent.title,
            content_md=content_md,
            content_hash=content_hash,
            clearance_level=parent.clearance_level,
            created_by=user,
            version_number=parent.version_number + 1,
            change_reason=reason,
            change_summary=summary,
            parent_version=parent,
        )


# Autocreate profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, raw, **kwargs):
    if created and not raw:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


# AUDIT TRAIL ---------------------------------

class AuditLog(models.Model):
    """Track all user actions for compliance (JORC/VALMIN requirements)"""

    class ActionType(models.TextChoices):
        CREATE = "CREATE", _("Created")
        VIEW = "VIEW", _("Viewed")
        EDIT = "EDIT", _("Edited")
        APPROVE = "APPROVE", _("Approved")
        REJECT = "REJECT", _("Rejected")
        DELETE = "DELETE", _("Deleted")
        DOWNLOAD = "DOWNLOAD", _("Downloaded")

    # Who made the changes
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    # What was changed
    action = models.CharField(max_length=16, choices=ActionType.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Context
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # When changes were made 
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['content_type', 'object_id'], name='audit_logs_content_b0ef47_idx'),
            models.Index(fields=['user', 'action'], name='audit_logs_user_id_d685f3_idx'),
            models.Index(fields=['timestamp'], name='audit_logs_timesta_423be6_idx'),
        ]

    def __str__(self):
        user_name = self.user.username if self.user else "Unknown"
        return f"{user_name} {self.action} {self.content_object} at {self.timestamp}"


# APPROVAL WORKFLOWS ---------------------------------
class ApprovalWorkflow(models.Model):
    """JORC/VALMIN approval workflows"""

    class WorkflowType(models.TextChoices):
        JORC = "JORC", _("JORC Compliance")
        VALMIN = "VALMIN", _("VALMIN Compliance")
        GENERAL = "GENERAL", _("General Approval")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending Review")
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")
        REVISION_REQUIRED = "REVISION", _("Revision Required")

    # WHich items needs approval
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Workflow details
    workflow_type = models.CharField(max_length=16, choices=WorkflowType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    # Which users are associated 
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workflow_submissions')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='workflow_approvals')

    # Context
    submission_notes = models.TextField(blank=True)
    approval_notes = models.TextField(blank=True)

    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'approval_workflows'
        ordering = ['-submitted_at']
        verbose_name = 'Approval Workflow'
        verbose_name_plural = 'Approval Workflows'

    def __str__(self):
        return f"{self.workflow_type} - {self.status} - {self.content_object}"

    def can_approve(self, user):
        """Check if user can approve this workflow"""
        if not hasattr(user, 'profile'):
            return False

        profile = user.profile

        if self.workflow_type == self.WorkflowType.JORC:
            return profile.can_approve_jorc
        elif self.workflow_type == self.WorkflowType.VALMIN:
            return profile.can_approve_valmin
        else:
            # General approval - check role
            return profile.role in [
                UserProfile.RoleChoices.FIELD_LEAD,
                UserProfile.RoleChoices.DATA_MANAGER,
                UserProfile.RoleChoices.OPERATIONS_MANAGER,
                UserProfile.RoleChoices.ADMIN,
            ]


# DOCUMENT VIEW TRACKING (Phase 2) ---------------------------------

class DocumentView(models.Model):
    """Track when users view documents for audit trail"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    document = models.ForeignKey('Document', on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'document_views'
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['document', 'user'], name='document_vi_documen_dcb332_idx'),
            models.Index(fields=['viewed_at'], name='document_vi_viewed__659188_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} viewed {self.document.title} at {self.viewed_at}"

# DOCUMENT–ENTITY LINKING ---------------------------------

class DocLink(models.Model):
    """Generic document-to-entity attachment for Confluence-style traceability."""
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="links",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "doc_links"
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="doc_links_ct_obj_idx"),
            models.Index(fields=["document"], name="doc_links_document_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "content_type", "object_id"],
                name="unique_doc_link",
            )
        ]

    def __str__(self):
        return f"{self.document.title} → {self.content_object}"


# SAMPLES & SURVEYS ---------------------------------

class Sample(models.Model):
    class SampleType(models.TextChoices):
        ROCK_CHIP  = "ROCK_CHIP",  _("Rock Chip")
        SOIL       = "SOIL",       _("Soil")
        STREAM_SED = "STREAM_SED", _("Stream Sediment")
        TRENCH     = "TRENCH",     _("Trench")
        CORE       = "CORE",       _("Drill Core")
        CHANNEL    = "CHANNEL",    _("Channel")

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name         = models.CharField(max_length=64)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    process      = models.ForeignKey(Process, on_delete=models.CASCADE)
    prospect     = models.ForeignKey(
        Prospect, null=True, blank=True, on_delete=models.SET_NULL, related_name="samples"
    )
    sample_type   = models.CharField(max_length=16, choices=SampleType.choices, blank=True)
    sample_number = models.CharField(max_length=64, blank=True)
    location      = models.PointField(srid=4326, null=True, blank=True)
    depth         = models.FloatField(null=True, blank=True)
    description   = models.TextField(blank=True)
    collected_by  = models.CharField(max_length=128, blank=True)
    collected_at  = models.DateField(null=True, blank=True)
    laboratory    = models.CharField(max_length=128, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_sample_type_display()})" if self.sample_type else self.name


class Survey(models.Model):
    class SurveyType(models.TextChoices):
        GEOPHYSICS     = "GEOPHYSICS", _("Geophysics")
        SOIL_GRID      = "SOIL_GRID",  _("Soil Grid")
        MAPPING        = "MAPPING",    _("Geological Mapping")
        REMOTE_SENSING = "REMOTE",     _("Remote Sensing")

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name         = models.CharField(max_length=128)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    process      = models.ForeignKey(Process, on_delete=models.CASCADE)
    prospect     = models.ForeignKey(
        Prospect, null=True, blank=True, on_delete=models.SET_NULL, related_name="surveys"
    )
    survey_type  = models.CharField(max_length=16, choices=SurveyType.choices, blank=True)
    contractor   = models.CharField(max_length=128, blank=True)
    date_from    = models.DateField(null=True, blank=True)
    date_to      = models.DateField(null=True, blank=True)
    description  = models.TextField(blank=True)
    geom         = models.PolygonField(
        srid=4326, null=True, blank=True,
        help_text="Coverage area of the survey"
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_survey_type_display()})" if self.survey_type else self.name


# HELPER FUNCTIONS ---------------------------------

def log_audit(user, action, obj, description="", ip_address=None, user_agent=""):
    """Create audit trail entry"""
    AuditLog.objects.create(
        user=user,
        action=action,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.id,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
    )


# class ProjectOp(models.Model):
#     MODE = (("EXP","Exploration"), ("MIN","Mining"))
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     mode = models.CharField(max_length=3, choices=MODE)
#     name = models.CharField(max_length=255)
# geom = models.MultiPolygonField(srid=4326, null=True, blank=True)
# commodity = models.CharField(max_length=64, blank=True)
#     def __str__(self): return self.name
#
# class Document(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     file = models.FileField(upload_to="docs/")
#     title = models.CharField(max_length=255)
#     year = models.IntegerField(null=True, blank=True)
#     doc_type = models.CharField(max_length=64, blank=True)
#     confidentiality = models.CharField(max_length=32, default="internal")
#     checksum_sha256 = models.CharField(max_length=64, db_index=True, blank=True)
#     project = models.ForeignKey(ProjectOp, null=True, blank=True, on_delete=models.SET_NULL)
#     created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
#     created_at = models.DateTimeField(auto_now_add=True)
#     def __str__(self): return self.title
