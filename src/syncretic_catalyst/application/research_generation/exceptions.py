"""Custom exceptions for the research generation workflow."""


class ProjectDocumentsNotFound(RuntimeError):
    """Raised when no project documents are available for generation."""
