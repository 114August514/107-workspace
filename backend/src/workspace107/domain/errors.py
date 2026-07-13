class DomainError(Exception):
    code = "domain_error"


class WorkspaceAccessDenied(DomainError):
    code = "workspace_access_denied"


class InvalidRunTransition(DomainError):
    code = "invalid_run_transition"


class InvalidRelativePath(DomainError):
    code = "invalid_relative_path"


class ResourceNotFound(DomainError):
    code = "resource_not_found"


class ResourceArchived(DomainError):
    code = "resource_archived"


class PreflightFailed(DomainError):
    code = "preflight_failed"
