from collections.abc import Mapping


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

    def __init__(
        self,
        message: str = "One or more run checks failed.",
        *,
        errors: tuple[Mapping[str, object], ...] = (),
    ) -> None:
        super().__init__(message)
        self.errors = tuple(dict(error) for error in errors)


class ResourceConflict(DomainError):
    code = "resource_conflict"


class FinalOwnerRequired(DomainError):
    code = "final_owner_required"


class InvalidWorkspaceParent(DomainError):
    code = "invalid_workspace_parent"


class InvalidStorageKey(DomainError):
    code = "invalid_storage_key"


class PathOutsideAllowedRoot(DomainError):
    code = "path_outside_allowed_root"


class ClusterUnavailable(DomainError):
    code = "cluster_unavailable"


class ExternalCommandFailed(DomainError):
    code = "external_command_failed"


class TransferFailed(DomainError):
    code = "transfer_failed"
