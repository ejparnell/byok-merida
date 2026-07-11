from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class CaptureEvidence(ApiModel):
    url: str = Field(min_length=1)
    title: str = ""
    selected_text: str = Field(default="", alias="selectedText")
    visible_text: str = Field(default="", alias="visibleText")
    semantic_html: str = Field(default="", alias="semanticHtml")


class PrepareCaptureRequest(ApiModel):
    evidence: CaptureEvidence


class ConfirmedDraft(ApiModel):
    job_url: str = Field(alias="jobUrl", min_length=1)
    company_name: str = Field(alias="companyName", min_length=1)
    role: str = Field(min_length=1)
    location: str = ""
    job_content: str = Field(alias="jobContent", min_length=20)


class ConfirmCaptureRequest(ApiModel):
    draft: ConfirmedDraft


class AnalysisRunRequest(ApiModel):
    limit: int = Field(default=5, ge=1, le=10)
