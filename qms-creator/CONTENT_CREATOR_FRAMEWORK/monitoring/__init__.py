"""Monitoring and observability module for Cannabis EU GMP QMS Creator."""

from .metrics import (
    DatabaseQueryContext,
    DocumentGenerationContext,
    ExternalServiceContext,
    init_prometheus,
    record_api_error,
    record_document_generated,
    record_document_upload,
    record_questionnaire_submission,
    update_active_documents,
)
from .sentry_integration import (
    add_breadcrumb,
    capture_exception,
    capture_message,
    clear_user_context,
    init_sentry,
    set_context,
    set_tag,
    set_user_context,
)

__all__ = [
    "init_sentry",
    "capture_exception",
    "capture_message",
    "set_user_context",
    "clear_user_context",
    "set_tag",
    "set_context",
    "add_breadcrumb",
    "init_prometheus",
    "record_document_generated",
    "record_questionnaire_submission",
    "record_document_upload",
    "record_api_error",
    "update_active_documents",
    "DatabaseQueryContext",
    "ExternalServiceContext",
    "DocumentGenerationContext",
]
