from typing import Annotated, Literal

from pydantic import Field, RootModel

from ...shared.schemas import ApiModel, CommonResponse, Pagination


class CreateResumeRequest(ApiModel):
    application_id: str = Field(alias="applicationId", min_length=1)


class ResumeQueueItem(ApiModel):
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


class ResumeApplicationSummary(ApiModel):
    id: str
    title: str
    company_name: str = Field(alias="companyName")
    role: str


class ResumeArtifactSummary(ResumeApplicationSummary):
    url: str


class PdfArtifactSummary(ApiModel):
    filename: str
    download_url: str = Field(alias="downloadUrl")


class CleanupSummary(ApiModel):
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


ResumeRunLifecycle = Literal["queued", "running", "cancelling", "finished"]
ResumeRunOutcome = Literal[
    "target_met",
    "spend_limited",
    "attempt_budget_exhausted",
    "queue_exhausted",
    "cancelled",
    "authorization_blocked",
    "failed",
]
ResumeCandidateState = Literal[
    "pending",
    "evaluating",
    "recovering",
    "compensating",
    "completed",
    "skipped",
    "failed",
    "cancelled",
]
ResumeCandidateStage = Literal[
    "admission",
    "requirements",
    "draft",
    "artifact_recovery",
    "completion_gate",
    "compensation",
]


class StartResumeRunRequest(ApiModel):
    target: int = Field(ge=1, le=10)


class ResumeSpendSnapshot(ApiModel):
    ceiling_micros: int = Field(alias="ceilingMicros", ge=0)
    committed_micros: int = Field(alias="committedMicros", ge=0)
    verified_cost_micros: int = Field(alias="verifiedCostMicros", ge=0)
    active_reservation_micros: int = Field(alias="activeReservationMicros", ge=0)
    indeterminate_reservation_micros: int = Field(
        alias="indeterminateReservationMicros", ge=0
    )
    remaining_authorized_micros: int = Field(
        alias="remainingAuthorizedMicros", ge=0
    )


class ResumeRunProgress(ApiModel):
    completions: int = Field(ge=0)
    candidates_considered: int = Field(alias="candidatesConsidered", ge=0)
    evaluations_consumed: int = Field(alias="evaluationsConsumed", ge=0)


class ResumeCompletionLink(ApiModel):
    id: str
    url: str


class ResumeCompletionPdf(ApiModel):
    filename: str
    download_url: str = Field(alias="downloadUrl")


class ResumeCompletionSummary(ApiModel):
    sealed_at: str = Field(alias="sealedAt")
    resume: ResumeCompletionLink
    note: ResumeCompletionLink
    pdf: ResumeCompletionPdf


class ResumeRunCandidate(ApiModel):
    application_id: str = Field(alias="applicationId")
    application_label: str = Field(alias="applicationLabel")
    ordinal: int = Field(ge=0, le=19)
    state: ResumeCandidateState
    stage: ResumeCandidateStage | None
    reason_code: str | None = Field(alias="reasonCode")
    evaluation_consumed: bool = Field(alias="evaluationConsumed")
    artifact_set_id: str | None = Field(alias="artifactSetId")
    completion: ResumeCompletionSummary | None
    considered_at: str | None = Field(alias="consideredAt")
    updated_at: str = Field(alias="updatedAt")
    terminal_at: str | None = Field(alias="terminalAt")


class ResumeRunSnapshot(ApiModel):
    run_id: str = Field(alias="runId")
    revision: int = Field(ge=1)
    lifecycle: ResumeRunLifecycle
    outcome: ResumeRunOutcome | None
    reason_code: str | None = Field(alias="reasonCode")
    target: int = Field(ge=1, le=10)
    attempt_budget: int = Field(alias="attemptBudget", ge=0, le=20)
    created_at: str = Field(alias="createdAt")
    started_at: str | None = Field(alias="startedAt")
    stopping_decided_at: str | None = Field(alias="stoppingDecidedAt")
    finished_at: str | None = Field(alias="finishedAt")
    updated_at: str = Field(alias="updatedAt")
    progress: ResumeRunProgress
    spend: ResumeSpendSnapshot
    candidates: list[ResumeRunCandidate]


class ResumeRunResponse(CommonResponse):
    ok: Literal[True]
    run: ResumeRunSnapshot


class ResumeRunLookupResponse(CommonResponse):
    ok: Literal[True]
    run: ResumeRunSnapshot | None


class ResumeArtifactActionRequest(ApiModel):
    expected_revision: int = Field(alias="expectedRevision", ge=1)


class ResumeArtifactQuarantine(ApiModel):
    reason_code: str = Field(alias="reasonCode")
    entered_at: str = Field(alias="enteredAt")
    last_assessed_at: str = Field(alias="lastAssessedAt")


class ResumeArtifactActiveAction(ApiModel):
    kind: Literal["reconcile", "compensate"]
    accepted_at: str = Field(alias="acceptedAt")


class ResumeArtifactSetSnapshot(ApiModel):
    artifact_set_id: str = Field(alias="artifactSetId")
    run_id: str = Field(alias="runId")
    application_id: str = Field(alias="applicationId")
    candidate_ordinal: int = Field(alias="candidateOrdinal", ge=0, le=19)
    application_label: str = Field(alias="applicationLabel")
    revision: int = Field(ge=1)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    disposition: Literal[
        "recoverable", "compensation_required", "sealed", "compensated"
    ]
    pending_boundary: str | None = Field(alias="pendingBoundary")
    quarantine: ResumeArtifactQuarantine | None
    available_actions: list[Literal["reconcile", "compensate"]] = Field(
        alias="availableActions"
    )
    active_action: ResumeArtifactActiveAction | None = Field(alias="activeAction")
    completion: ResumeCompletionSummary | None


class ResumeArtifactSetResponse(CommonResponse):
    ok: Literal[True]
    artifact_set: ResumeArtifactSetSnapshot = Field(alias="artifactSet")


class ResumeArtifactQuarantinePagination(ApiModel):
    limit: int = Field(ge=1, le=50)
    next_cursor: str | None = Field(alias="nextCursor")
    has_more: bool = Field(alias="hasMore")


class ResumeArtifactQuarantineListResponse(CommonResponse):
    ok: Literal[True]
    items: list[ResumeArtifactSetSnapshot]
    pagination: ResumeArtifactQuarantinePagination
