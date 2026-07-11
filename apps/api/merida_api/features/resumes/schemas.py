from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from ...shared.schemas import CommonResponse, Pagination


class CreateResumeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    application_id: str = Field(alias="applicationId", min_length=1)


class ResumeQueueItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    application_id: str = Field(alias="applicationId")
    title: str
    company_name: str = Field(alias="companyName")
    role: str
    application_status: Literal["To Apply"] = Field(alias="applicationStatus")
    job_url: str = Field(alias="jobUrl")
    match_score: int = Field(alias="matchScore", ge=0, le=100)
    analyzed: Literal[True]
    has_resume: Literal[False] = Field(alias="hasResume")


class ResumeCreationQueueReadyResponse(CommonResponse):
    ok: Literal[True]
    queue_count: int = Field(alias="queueCount", ge=0)
    items: list[ResumeQueueItem]
    pagination: Pagination


class ResumeCreationQueueBlockedResponse(CommonResponse):
    ok: Literal[False]
    status: Literal["blocked"]
    queue_count: Literal[0] = Field(alias="queueCount")
    items: list[ResumeQueueItem]
    pagination: Pagination


class GetResumeCreationQueueResponse(
    RootModel[ResumeCreationQueueReadyResponse | ResumeCreationQueueBlockedResponse]
):
    pass


class ResumeApplicationSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    id: str
    title: str
    company_name: str = Field(alias="companyName")
    role: str


class ResumeArtifactSummary(ResumeApplicationSummary):
    url: str


class PdfArtifactSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    filename: str
    download_url: str = Field(alias="downloadUrl")


class CleanupSummary(BaseModel):
    status: Literal["not_required", "completed", "incomplete"]
    errors: list[str]


class ResumeCreatedResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["created"]
    application: ResumeApplicationSummary
    resume: ResumeArtifactSummary
    note: ResumeArtifactSummary
    pdf: PdfArtifactSummary


class ResumeAlreadyCreatedResponse(CommonResponse):
    ok: Literal[True]
    result: Literal["already_created"]
    application: ResumeApplicationSummary
    resume: ResumeArtifactSummary
    note: ResumeArtifactSummary | None
    pdf: PdfArtifactSummary | None


class ResumeCreationBlockedResponse(CommonResponse):
    ok: Literal[False]
    status: Literal["blocked"]
    result: Literal["blocked"]
    cleanup: CleanupSummary


class ResumeCreationFailedResponse(CommonResponse):
    ok: Literal[False]
    status: Literal["failed"]
    result: Literal["failed"]
    cleanup: CleanupSummary


class CreateResumeResponse(
    RootModel[
        Annotated[
            ResumeCreatedResponse
            | ResumeAlreadyCreatedResponse
            | ResumeCreationBlockedResponse
            | ResumeCreationFailedResponse,
            Field(discriminator="result"),
        ]
    ]
):
    pass
