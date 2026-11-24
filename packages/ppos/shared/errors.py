"""Explicit error taxonomy. Presentation maps these to HTTP status codes."""


class PposError(Exception):
    """Base class for all expected application errors."""


class ValidationError(PposError):
    """Input violates a domain rule."""


class NotFoundError(PposError):
    """Requested entity does not exist."""

    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(f"{entity} {entity_id!r} not found")
        self.entity = entity
        self.entity_id = entity_id


class ConflictError(PposError):
    """Operation conflicts with current state (e.g. dependency cycle)."""


class DataBoundaryError(PposError):
    """Private data location is unsafe (e.g. inside the source repository)."""


class MigrationRequiredError(PposError):
    """Database has pending migrations that must be applied explicitly."""
