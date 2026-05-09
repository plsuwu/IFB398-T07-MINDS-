from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("home/", views.home, name="home"),

    # Projects
    path("projects/", views.projects, name="projects"),
    path("projects/<uuid:pk>/", views.project_detail, name="project_detail"),

    path("prospects/new/",            views.create_prospect, name="create_prospect"),
    path("prospects/", views.prospects, name="prospects"),
    path("prospects/<uuid:pk>/",      views.prospect_detail, name="prospect_detail"),
    path("prospects/<uuid:pk>/edit/", views.edit_prospect,   name="edit_prospect"),

    # DocLink routes
    path("doclinks/picker/", views.doc_link_picker, name="doc_link_picker"),
    path("doclinks/create/", views.create_doc_link, name="create_doc_link"),
    path("doclinks/<int:pk>/delete/", views.delete_doc_link, name="delete_doc_link"),

    path("drillholes/link-picker/",      views.drillhole_link_picker, name="drillhole_link_picker"),
    path("drillholes/link/",             views.link_drillhole,        name="link_drillhole"),
    path("drillholes/<uuid:pk>/unlink/", views.unlink_drillhole,      name="unlink_drillhole"),
    path("drillholes/", views.drillholes, name="drillholes"),
    path("drillholes/import/", views.drillhole_import, name="drillhole_import"),
    path("drillholes/<uuid:pk>/", views.drillhole_detail, name="drillhole_detail"),
    path("tenements/", views.tenements, name="tenements"),
    path("documents/", views.documents, name="documents"),
    path("documents/<uuid:pk>/", views.document_detail, name="document_detail"),
    path("documents/<uuid:pk>/delete/", views.delete_document, name="delete_document"),
    path("map/", views.map_view, name="map_view"),
    path("ai-insights/", views.ai_insights, name="ai_insights"),
    path("upload/", views.upload_doc, name="upload"),

    # PDF / DOCX direct download by process
    path("ai/report/<uuid:process_id>/pdf/", views.project_report_pdf,  name="project_report_pdf"),
    path("ai/report/<uuid:process_id>/docx/", views.project_report_docx, name="project_report_docx"),

    # Report History
    path("process/<uuid:process_id>/reports/history/", views.report_history, name="report_history"),
    path("reports/<uuid:report_id>/version/", views.report_version_detail, name="report_version_detail"),

    # AI Routes
    path("ai/reports/", views.report_list_page, name="report_list"),
    path("ai/reports/generate/", views.generate_report, name="generate_report"),
    path("ai/reports/<uuid:report_id>/", views.report_detail, name="report_detail"),
    path("ai/reports/history/", views.all_reports_history, name="all_reports_history"),

    # Report Editor 
    path("ai/reports/editor/<uuid:process_id>/", views.report_editor, name="report_editor"),
    path("ai/reports/<uuid:report_id>/view/", views.saved_report_editor, name="saved_report_editor"),

    # Save / Update 
    path("ai/reports/save/", views.save_report, name="save_report"),
    path("ai/reports/<uuid:report_id>/update/", views.update_saved_report, name="update_saved_report"),

    # Export from editor content via POST 
    path("ai/reports/export/", views.export_report, name="export_report"),
    path("ai/documents/analysis/", views.document_analysis_page, name="document_analysis_page"),
    path("ai/documents/<uuid:pk>/analyze/", views.analyze_document, name="analyze_document"),
    path("ai/documents/<uuid:pk>/analysis/", views.document_analysis_detail, name="document_analysis_detail"),
    path("ai/documents/<uuid:pk>/analysis/save/", views.save_document_analysis, name="save_document_analysis"),
    path("ai/documents/<uuid:pk>/analysis/export/", views.export_document_analysis, name="export_document_analysis"),


    # GeoJSON API endpoints for the map viewer
    path("api/geojson/projects/", views.geojson_projects, name="geojson_projects"),
    path("api/geojson/tenements/", views.geojson_tenements, name="geojson_tenements"),
    path("api/geojson/prospects/", views.geojson_prospects, name="geojson_prospects"),
    path("api/geojson/drillholes/", views.geojson_drillholes, name="geojson_drillholes"),
    path("api/spatial-search/", views.spatial_search, name="spatial_search"),
]
