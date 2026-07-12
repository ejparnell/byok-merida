from ..features.resumes.resume_builder import DeepSeekResumeDocumentBuilder
from ..shared.prompt_payload import JsonPromptPayloadEncoder
from .deepseek import create_deepseek_json_client


def create_deepseek_resume_builder(
    *, api_key: str, model: str, input_format: str = "json"
) -> DeepSeekResumeDocumentBuilder:
    if input_format != "json":
        raise ValueError("Only JSON prompt input is supported in v1.")
    return DeepSeekResumeDocumentBuilder(
        create_deepseek_json_client(
            api_key=api_key, model=model, max_tokens=8000
        ),
        JsonPromptPayloadEncoder(),
    )
