# core/admin.py
from django.contrib import admin as djadmin
from django.contrib.gis.admin import GISModelAdmin

from .models import (
    Process, Document, Organisation, Prospect, Tenement, Drillhole,
    DrillholeSurvey, LithologyInterval, AssayResult,
    UserProfile, AuditLog, ApprovalWorkflow, DocumentView, SavedReport, DocLink
)

# CORE MODELS ---------------------------------

@djadmin.register(Organisation)
class OrganisationAdmin(djadmin.ModelAdmin):
    list_display = ("name", "mode", "created_at")
    list_filter = ("mode",)
    search_fields = ("name",)

@djadmin.register(Process)
class ProcessAdmin(GISModelAdmin):
    list_display = ("name", "mode", "commodity", "organisation")
    list_filter = ("mode", "organisation")
    search_fields = ("name", "commodity")

@djadmin.register(Document)
class DocumentAdmin(djadmin.ModelAdmin):
    list_display = ("title", "timestamp", "doc_type", "confidentiality", "process", "created_by")
    list_filter = ("doc_type", "confidentiality", "organisation")
    search_fields = ("title", "checksum_sha256")
    readonly_fields = ("checksum_sha256", "created_at", "updated_at")

@djadmin.register(Prospect)
class ProspectAdmin(GISModelAdmin):
    list_display = ("name", "organisation", "process", "created_at")
    list_filter = ("organisation",)
    search_fields = ("name", "hypothesis", "objective")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Identity", {
            "fields": ("name", "organisation", "process"),
        }),
        ("Scientific Rationale", {
            "fields": ("hypothesis", "objective"),
        }),
        ("Geometry", {
            "fields": ("geom",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

@djadmin.register(Tenement)
class TenementAdmin(GISModelAdmin):  
    list_display = ("name", "organisation", "process", "created_at")
    list_filter = ("organisation",)
    search_fields = ("name",)

@djadmin.register(Drillhole)
class DrillholeAdmin(GISModelAdmin):
    list_display  = ("name", "drill_type", "organisation", "process", "elevation", "depth", "date_commenced", "created_at")
    list_filter   = ("drill_type", "organisation", "process")
    search_fields = ("name", "hole_id_original", "company", "current_epm")
    readonly_fields = ("source_crs", "source_easting", "source_northing", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {
            "fields": ("name", "hole_id_original", "organisation", "process"),
        }),
        ("Collar Geometry", {
            "fields": ("collar_location", "elevation", "source_crs", "source_easting", "source_northing"),
        }),
        ("Survey (Collar Reading)", {
            "fields": ("depth", "dip", "azimuth", "drill_type"),
        }),
        ("Administrative", {
            "fields": ("company", "drill_company", "current_epm", "original_epm",
                       "year_report", "company_report", "date_commenced", "date_completed"),
        }),
        ("Notes", {
            "fields": ("comments",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@djadmin.register(DrillholeSurvey)
class DrillholeSurveyAdmin(djadmin.ModelAdmin):
    list_display  = ("drillhole", "depth", "dip", "azimuth_tn", "azimuth_mag", "comment")
    list_filter   = ("drillhole__organisation",)
    search_fields = ("drillhole__name",)
    ordering      = ("drillhole", "depth")


@djadmin.register(LithologyInterval)
class LithologyIntervalAdmin(djadmin.ModelAdmin):
    list_display  = ("drillhole", "from_depth", "to_depth", "lithology", "description")
    list_filter   = ("drillhole__organisation", "lithology")
    search_fields = ("drillhole__name", "lithology", "description")
    ordering      = ("drillhole", "from_depth")


@djadmin.register(AssayResult)
class AssayResultAdmin(djadmin.ModelAdmin):
    list_display  = ("drillhole", "from_depth", "to_depth", "au_ppm", "cu_ppm", "pb_ppm", "zn_ppm", "laboratory")
    list_filter   = ("drillhole__organisation", "laboratory")
    search_fields = ("drillhole__name", "sample_number", "lab_batch_number")
    ordering      = ("drillhole", "from_depth")


# USER PERMISSIONS & AUDIT ---------------------------------

@djadmin.register(UserProfile)
class UserProfileAdmin(djadmin.ModelAdmin):
    list_display = ("user", "role", "organisation", "clearance_level", "can_approve_jorc", "can_approve_valmin")
    list_filter = ("role", "clearance_level", "can_approve_jorc", "can_approve_valmin", "organisation")
    search_fields = ("user__username", "user__email", "employee_id")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("User Information", {
            "fields": ("user", "organisation", "role", "clearance_level")
        }),
        ("Contact Details", {
            "fields": ("department", "phone", "employee_id")
        }),
        ("Approval Permissions", {
            "fields": ("can_approve_jorc", "can_approve_valmin")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

@djadmin.register(AuditLog)
class AuditLogAdmin(djadmin.ModelAdmin):
    list_display = ("user", "action", "content_type", "object_id", "timestamp", "ip_address")
    list_filter = ("action", "content_type", "timestamp")
    search_fields = ("user__username", "description", "object_id")
    readonly_fields = ("user", "action", "content_type", "object_id", "description", "ip_address", "user_agent", "timestamp")
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False  # Audit logs should only be created programmatically

    def has_change_permission(self, request, obj=None):
        return False  # Audit logs should be immutable

@djadmin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(djadmin.ModelAdmin):
    list_display = ("workflow_type", "status", "content_type", "object_id", "submitted_by", "approved_by", "submitted_at")
    list_filter = ("workflow_type", "status", "submitted_at")
    search_fields = ("submission_notes", "approval_notes", "object_id")
    readonly_fields = ("submitted_at", "reviewed_at")

    fieldsets = (
        ("Workflow Details", {
            "fields": ("workflow_type", "status", "content_type", "object_id")
        }),
        ("Participants", {
            "fields": ("submitted_by", "approved_by")
        }),
        ("Notes", {
            "fields": ("submission_notes", "approval_notes")
        }),
        ("Timestamps", {
            "fields": ("submitted_at", "reviewed_at")
        }),
    )

@djadmin.register(SavedReport)
class SavedReportAdmin(djadmin.ModelAdmin):
    list_display  = ("title", "process", "clearance_level", "created_by", "created_at", "updated_at")
    list_filter   = ("clearance_level", "process__organisation")
    search_fields = ("title", "process__name")
    readonly_fields = ("id", "created_at", "updated_at")


@djadmin.register(DocumentView)
class DocumentViewAdmin(djadmin.ModelAdmin):
    list_display = ("user", "document", "viewed_at", "ip_address")
    list_filter = ("viewed_at",)
    search_fields = ("user__username", "document__title")
    readonly_fields = ("user", "document", "viewed_at", "ip_address")
    date_hierarchy = "viewed_at"

    def has_add_permission(self, request):
        return False  # View tracking should only be created programmatically

    def has_change_permission(self, request, obj=None):
        return False  # View records should be immutable


@djadmin.register(DocLink)
class DocLinkAdmin(djadmin.ModelAdmin):
    list_display = ("document", "content_type", "object_id", "created_by", "created_at")
    list_filter = ("content_type", "created_at")
    search_fields = ("document__title",)
    readonly_fields = ("created_at",)
