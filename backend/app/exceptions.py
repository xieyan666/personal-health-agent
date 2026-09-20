"""Dependency-free application exceptions."""


class ServiceError(Exception):
    """Base class for clear business-layer failures."""


class NotFoundError(ServiceError):
    """A requested business resource does not exist."""


class ForbiddenError(ServiceError):
    """The current principal may not access the requested business resource."""


class ConflictError(ServiceError):
    """A unique business identity already exists."""


class ValidationError(ServiceError):
    """Input violates a Service-level business rule."""
