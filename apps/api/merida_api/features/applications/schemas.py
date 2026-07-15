from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, RootModel, field_validator, model_validator
from pydantic_core import PydanticCustomError

from ...shared.schemas import ApiModel, CommonResponse, Pagination
from .workspace import ApplicationStatus


class CaptureEvidence(ApiModel):
    url: str = Field(min_length=1, max_length=4096)
    title: str = Field(default="", max_length=1000)
    selected_text: str = Field(default="", alias="selectedText", max_length=120_000)
    visible_text: str = Field(default="", alias="visibleText", max_length=120_000)
    semantic_html: str = Field(default="", alias="semanticHtml", max_length=120_000)
    metadata_text: str = Field(default="", alias="metadataText", max_length=120_000)
    structured_job_title: str = Field(default="", alias="structuredJobTitle", max_length=200)
    structured_company_name: str = Field(default="", alias="structuredCompanyName", max_length=200)
    structured_location: str = Field(default="", alias="structuredLocation", max_length=300)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("URL must be an absolute HTTP(S) URL.")
        return value

    @model_validator(mode="after")
    def validate_evidence_size(self):
        total = (
            len(self.selected_text)
            + len(self.visible_text)
            + len(self.semantic_html)
            + len(self.metadata_text)
        )
        if total > 240_000:
            raise PydanticCustomError(
                "payload_too_large", "Combined Capture Evidence is too large."
            )
        if not any(
            value.strip()
            for value in (
                self.selected_text,
                self.visible_text,
                self.semantic_html,
                self.metadata_text,
            )
        ):
            raise ValueError("Readable Capture Evidence is required.")
        return self


class PrepareApplicationRequest(ApiModel):
    evidence: CaptureEvidence


class ConfirmedApplicationDraft(ApiModel):
    job_url: str = Field(alias="jobUrl", min_length=1, max_length=4096)
    company_name: str = Field(alias="companyName", min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    job_content: str = Field(alias="jobContent", min_length=20, max_length=120_000)

    @field_validator("company_name", "role", "job_content", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("location", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if not isinstance(value, str):
            return value
        return value.strip() or None

    @field_validator("job_url")
    @classmethod
    def validate_job_url(cls, value: str) -> str:
        return CaptureEvidence.validate_url(value)


class ConfirmApplicationRequest(ApiModel):
    draft: ConfirmedApplicationDraft


class CaptureMatchApplication(ApiModel):
    id: str
    title: str
    company_name: str = Field(alias="companyName")
    role: str
    application_status: ApplicationStatus = Field(alias="applicationStatus")
    url: str


class CaptureMatchesFoundResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["matched"]
    matches: list[CaptureMatchApplication]


class CaptureMatchesEmptyResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["unmatched"]
    matches: list[CaptureMatchApplication]


class CaptureMatchesBlockedResponse(CommonResponse):
    ok: Literal[False]
    status: Literal["blocked"]
    result: Literal["blocked"]
    matches: list[CaptureMatchApplication]


class CaptureMatchesResponse(
    RootModel[
        Annotated[
            CaptureMatchesFoundResponse
            | CaptureMatchesEmptyResponse
            | CaptureMatchesBlockedResponse,
            Field(discriminator="result"),
        ]
    ]
):
    pass


class RunApplicationAnalysisRequest(ApiModel):
    limit: int = Field(default=5, ge=1, le=10)


class PreparedApplicationDraft(ApiModel):
    job_url: str = Field(alias="jobUrl")
    company_name: str | None = Field(alias="companyName")
    role: str | None
    location: str | None
    job_content_preview: str = Field(alias="jobContentPreview")


class PreparedApplicationResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["prepared"]
    draft: PreparedApplicationDraft
    needs_review: Literal[False] = Field(alias="needsReview")
    review_reasons: list[str] = Field(alias="reviewReasons")
    missing_fields: list[str] = Field(alias="missingFields")


class ApplicationNeedsReviewResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["needs_review"]
    draft: PreparedApplicationDraft
    needs_review: Literal[True] = Field(alias="needsReview")
    review_reasons: list[str] = Field(alias="reviewReasons")
    missing_fields: list[str] = Field(alias="missingFields")


class PrepareApplicationResponse(
    RootModel[
        Annotated[
            PreparedApplicationResponse | ApplicationNeedsReviewResponse,
            Field(discriminator="result"),
        ]
    ]
):
    pass


class CapturedApplication(ApiModel):
    id: str
    title: str
    company_name: str = Field(alias="companyName")
    role: str
    location: str | None
    job_url: str = Field(alias="jobUrl")
    application_status: Literal["To Apply"] = Field(alias="applicationStatus")
    url: str


class ApplicationCreatedResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["created"]
    application: CapturedApplication


class ApplicationAlreadyCapturedResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["already_captured"]
    application: CapturedApplication


class ApplicationCaptureBlockedResponse(CommonResponse):
    ok: Literal[False]
    status: Literal["blocked"]
    result: Literal["blocked"]


class ConfirmApplicationResponse(
    RootModel[
        Annotated[
            ApplicationCreatedResponse
            | ApplicationAlreadyCapturedResponse
            | ApplicationCaptureBlockedResponse,
            Field(discriminator="result"),
        ]
    ]
):
    pass


class AnalysisQueueItem(ApiModel):
    application_id: str = Field(alias="applicationId")
    title: str
    company_name: str = Field(alias="companyName")
    role: str
    application_status: Literal["To Apply"] = Field(alias="applicationStatus")
    job_url: str = Field(alias="jobUrl")


class ApplicationAnalysisQueueReadyResponse(CommonResponse):
    ok: Literal[True]
    queue_count: int = Field(alias="queueCount", ge=0)
    items: list[AnalysisQueueItem]
    pagination: Pagination


class ApplicationAnalysisQueueBlockedResponse(CommonResponse):
    ok: Literal[False]
    status: Literal["blocked"]
    queue_count: Literal[0] = Field(alias="queueCount")
    items: list[AnalysisQueueItem]
    pagination: Pagination


class GetApplicationAnalysisQueueResponse(
    RootModel[ApplicationAnalysisQueueReadyResponse | ApplicationAnalysisQueueBlockedResponse]
):
    pass


class AnalysisResultItem(AnalysisQueueItem):
    result: Literal["analyzed", "repaired", "skipped", "failed"]
    match_score: int | None = Field(alias="matchScore", ge=0, le=100)
    errors: list[str]


class ApplicationAnalysisCompletedResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["completed"]
    processed: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    repaired: int = Field(ge=0)
    items: list[AnalysisResultItem]


class ApplicationAnalysisBlockedResponse(CommonResponse):
    ok: Literal[False]
    status: Literal["blocked"]
    result: Literal["blocked"]
    processed: Literal[0]
    succeeded: Literal[0]
    failed: Literal[0]
    repaired: Literal[0]
    items: list[AnalysisResultItem]


class RunApplicationAnalysisResponse(
    RootModel[
        Annotated[
            ApplicationAnalysisCompletedResponse | ApplicationAnalysisBlockedResponse,
            Field(discriminator="result"),
        ]
    ]
):
    pass
