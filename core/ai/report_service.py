from __future__ import annotations
import logging
from datetime import datetime
from typing import Iterable

from django.db.models import QuerySet
from django.utils.timezone import localtime

from ..models import Process, Document, SavedReport, AuditLog, log_audit
from .granite_client import GraniteClient
from .retrieval import retrieve_context

log = logging.getLogger(__name__)

# clearance hierarchy — mirrors UserProfile.ClearanceLevel and retrieval.py
CLEARANCE_LEVELS = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "JORC_APPROVED": 3,
}

# doc confidentiality field values used in the Document model
CONFIDENTIALITY_MAP = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "jorc_restricted": 3,
}

def _fmt_dt(dt):
    if not dt:
        return ""
    try:
        return localtime(dt).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)

def _fmt_user(user):
    if not user:
        return ""
    return getattr(user, "username", str(user))

def fetch_process_bundle(process_id: str, clearance_level: str = "INTERNAL") -> dict:
    """
    Fetch the project (Process) and a clearance-filtered slice of related documents.

    Only documents whose confidentiality level is accessible to the caller's
    clearance_level are included.  This prevents higher-clearance content from
    appearing in reports cached for lower-clearance users.
    """
    proc = Process.objects.select_related("organisation").get(pk=process_id)

    user_level = CLEARANCE_LEVELS.get(clearance_level, 1)
    accessible_confidentiality = [
        conf for conf, level in CONFIDENTIALITY_MAP.items()
        if level <= user_level
    ]

    docs: QuerySet[Document] = (
        Document.objects
        .filter(process=proc, confidentiality__in=accessible_confidentiality)
        .select_related("created_by", "organisation", "process")
        .order_by("-timestamp", "-created_at")[:50]
        .only(
            "id",
            "title",
            "timestamp",
            "doc_type",
            "confidentiality",
            "file",
            "created_at",
            "checksum_sha256",
            "extracted_text",
            "created_by__username",
            "organisation__name",
            "process__name",
        )
    )

    return {
        "process": proc,
        "docs": list(docs),
    }

def build_structured_context(bundle: dict) -> str:
    """
    Convert DB records into a compact, LLM-friendly context block.
    """
    p: Process = bundle["process"]
    lines = []
    lines.append("PROCESS")
    lines.append(f"  id: {p.id}")
    lines.append(f"  name: {p.name or ''}")
    lines.append(f"  mode: {p.mode}")
    lines.append(f"  commodity: {p.commodity or ''}")
    lines.append(f"  organisation: {p.organisation.name if p.organisation else ''}")
    lines.append("")

    lines.append("DOCUMENTS (latest up to 50)")
    for d in bundle["docs"]:
        snippet = (d.extracted_text or "")[:1000].replace("\n", " ").strip()

        lines.append(
            "  - {"
            f"id: {d.id}, "
            f"title: {d.title!r}, "
            f"date: {d.timestamp or ''}, "
            f"type: {d.doc_type or ''}, "
            f"uploaded_by: {_fmt_user(d.created_by)}, "
            f"conf: {d.confidentiality or ''}, "
            f"created_at: {_fmt_dt(d.created_at)}, "
            f"file: {getattr(d.file, 'name', '')}, "
            f"checksum: {d.checksum_sha256 or ''}, "
            f"text_snippet: {snippet!r}"
            "}"
        )

    return "\n".join(lines)

REPORT_SYSTEM_INSTRUCTIONS = """You are a technical writer generating concise mining/exploration project reports.
Write clearly and factually, using only the provided context. If data is missing, say so briefly.
Output Markdown. Keep it structured with headings.
Audience: internal stakeholders (technical + managerial)."""

def build_prompt(context: str, as_of: str | None = None, sections: Iterable[str] | None = None) -> str:
    sections = sections or [
        "1. Project Summary",
        "2. Key Documents & Evidence",
        "3. Activities Timeline",
        "4. Commodities & Targets",
        "5. Data Gaps & Next Steps",
    ]
    as_of = as_of or datetime.utcnow().strftime("%Y-%m-%d")
    return f"""{REPORT_SYSTEM_INSTRUCTIONS}

DATE: {as_of}

CONTEXT:
{context}

TASK:
Generate a succinct, well-structured Markdown report for the project above.
Use the following section outline (omit any section with no information):

{chr(10).join(f"- {s}" for s in sections)}

Style:
- Bullet points where helpful.
- Include internal file names/links if present.
- Keep to ~400–700 words.
"""

def generate_project_report(process_id: str, clearance_level: str = "INTERNAL") -> str:
    """
    Orchestrates: fetch → structure → call Granite → return Markdown.

    Only documents and chunks accessible at clearance_level are included,
    ensuring cached reports are correctly scoped per clearance tier.
    """
    bundle = fetch_process_bundle(process_id, clearance_level=clearance_level)
    p = bundle["process"]

    # Structured metadata context
    metadata_ctx = build_structured_context(bundle)

    # Retrieved document content chunks (scoped to same clearance level)
    content_ctx = retrieve_context(
        query=f"{p.name or ''} {p.commodity or ''}".strip(),
        process=p,
        clearance_level=clearance_level,
        max_chunks=8
    )

    full_context = f"{metadata_ctx}\n\nDOCUMENT CONTENT EXCERPTS:\n{content_ctx}"
    prompt = build_prompt(full_context)

    client = GraniteClient()
    text = client.complete(prompt)
    return text

def save_report(process, organisation, title, content_md, user, reason="GENERATED", summary=""):
    import hashlib
    content_hash = hashlib.sha256(content_md.encode()).hexdigest()

    # Check if a report already exists for this process+title
    existing = SavedReport.objects.filter(
        process=process, title=title
    ).order_by("-version_number").first()

    if existing:
        # Create a new version
        report = SavedReport.create_version(
            parent=existing,
            content_md=content_md,
            user=user,
            reason=reason,
            summary=summary,
        )
    else:
        # First version ever
        report = SavedReport.objects.create(
            process=process,
            organisation=organisation,
            title=title,
            content_md=content_md,
            content_hash=content_hash,
            clearance_level="INTERNAL",
            created_by=user,
            version_number=1,
            change_reason=reason,
            change_summary=summary,
        )

    log_audit(user=user, action=AuditLog.ActionType.CREATE, obj=report,
              description=f"Saved '{title}' v{report.version_number}")
    return report