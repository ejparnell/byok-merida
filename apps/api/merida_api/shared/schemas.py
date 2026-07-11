from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, serialize_by_alias=True
    )


class RequestValidationFailure(ApiModel):
    kind: Literal["request"]
    field: str
    message: str


class ConfigurationValidationFailure(ApiModel):
    kind: Literal["configuration"]
    setting: str
    message: str


class WorkspaceSchemaValidationFailure(ApiModel):
    kind: Literal["workspace_schema"]
    database: str
    property: str | None
    message: str


ValidationFailure = Annotated[
    RequestValidationFailure
    | ConfigurationValidationFailure
    | WorkspaceSchemaValidationFailure,
    Field(discriminator="kind"),
]


class CommonResponse(ApiModel):
    ok: bool
    validation_failures: list[ValidationFailure] = Field(alias="validationFailures")
    errors: list[str]


ApiErrorCode = Literal[
    "invalid_request",
    "invalid_cursor",
    "invalid_capture_token",
    "not_found",
    "pdf_not_found",
    "demo_not_active",
    "method_not_allowed",
    "conflict",
    "payload_too_large",
    "unsupported_media_type",
    "internal_error",
]


class ApiErrorDetail(ApiModel):
    code: ApiErrorCode
    message: str
    request_id: str | None = Field(alias="requestId")


class ApiErrorResponse(CommonResponse):
    ok: Literal[False]
    error: ApiErrorDetail


class HealthChecks(ApiModel):
    settings: Literal["ready", "blocked", "not_checked"]
    notion: Literal["ready", "blocked", "not_checked"]
    analysis: Literal["ready", "blocked", "not_checked"]
    resumes: Literal["ready", "blocked", "not_checked"]


class HealthResponse(CommonResponse):
    status: Literal["ready", "blocked"]
    service: Literal["merida-api"]
    mode: Literal["demo", "real"]
    checks: HealthChecks


class NotionDatabaseChecks(ApiModel):
    applications: Literal["ready", "blocked", "not_checked"]
    resumes: Literal["ready", "blocked", "not_checked"]
    notes: Literal["ready", "blocked", "not_checked"]


class NotionHealthResponse(CommonResponse):
    status: Literal["ready", "blocked"]
    workspace: Literal["demo", "notion"]
    databases: NotionDatabaseChecks


class ApplicationAnalysisChecks(ApiModel):
    deepseek: Literal["ready", "blocked", "not_checked"]
    applications_database: Literal["ready", "blocked", "not_checked"] = Field(alias="applicationsDatabase")
    job_content_access: Literal["ready", "blocked", "not_checked"] = Field(alias="jobContentAccess")
    master_resume_evidence: Literal["ready", "blocked", "not_checked"] = Field(alias="masterResumeEvidence")
    evidence_matcher: Literal["ready", "blocked", "not_checked"] = Field(alias="evidenceMatcher")


class ApplicationAnalysisHealthResponse(CommonResponse):
    status: Literal["ready", "blocked"]
    workflow: Literal["application_analysis"]
    checks: ApplicationAnalysisChecks


class ResumeCreationChecks(ApiModel):
    deepseek: Literal["ready", "blocked", "not_checked"]
    notion: Literal["ready", "blocked", "not_checked"]
    fit_analysis: Literal["ready", "blocked", "not_checked"] = Field(alias="fitAnalysis")
    master_resume: Literal["ready", "blocked", "not_checked"] = Field(alias="masterResume")
    pdf_export: Literal["ready", "blocked", "not_checked"] = Field(alias="pdfExport")


class ResumeCreationHealthResponse(CommonResponse):
    status: Literal["ready", "blocked"]
    workflow: Literal["resume_creation"]
    checks: ResumeCreationChecks


class OperatorModels(ApiModel):
    analysis: str
    resumes: str


class OperatorConfigured(ApiModel):
    notion: bool
    deepseek: bool


class OperatorSettingsResponse(CommonResponse):
    mode: Literal["demo", "real"]
    workspace: Literal["demo", "notion"]
    models: OperatorModels
    configured: OperatorConfigured


class Pagination(ApiModel):
    limit: int = Field(ge=1, le=10)
    next_cursor: str | None = Field(alias="nextCursor")
    has_more: bool = Field(alias="hasMore")


class ResetDemoResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["reset"]
