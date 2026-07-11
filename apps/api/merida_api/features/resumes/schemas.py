from pydantic import BaseModel, ConfigDict, Field


class CreateResumeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    application_id: str = Field(alias="applicationId", min_length=1)
