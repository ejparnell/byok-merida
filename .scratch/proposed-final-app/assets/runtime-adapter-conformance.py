"""Exercise the selected external runtime adapters without real credentials.

Install the pinned candidate dependencies in an isolated virtual environment,
then run this module.  Pass --openapi-json PATH when the TypeScript client
generator also needs the representative FastAPI OpenAPI document.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel
from typing_extensions import TypedDict


class RunRequest(BaseModel):
    application_id: str
    mode: str


class RunResult(BaseModel):
    result: str
    application_id: str


class WorkflowState(TypedDict):
    application_id: str
    outcome: str


@dataclass
class WorkflowContext:
    prefix: str


def create_conformance_app() -> FastAPI:
    app = FastAPI()

    @app.post("/conformance/run", response_model=RunResult)
    def run(request: RunRequest) -> RunResult:
        result = "completed" if request.mode == "ready" else "blocked"
        return RunResult(result=result, application_id=request.application_id)

    return app


def evaluate(
    state: WorkflowState, runtime: Runtime[WorkflowContext]
) -> dict[str, str]:
    outcome = "completed" if state["application_id"] else "blocked"
    return {"outcome": f"{runtime.context.prefix}:{outcome}"}


def run_conformance(openapi_json: Path | None = None) -> None:
    app = create_conformance_app()
    client = TestClient(app)

    completed = client.post(
        "/conformance/run",
        json={"application_id": "app-1", "mode": "ready"},
    )
    assert completed.json() == {"result": "completed", "application_id": "app-1"}
    blocked = client.post(
        "/conformance/run",
        json={"application_id": "app-1", "mode": "blocked"},
    )
    assert blocked.json() == {"result": "blocked", "application_id": "app-1"}
    assert client.post("/conformance/run", json={"application_id": "app-1"}).status_code == 422

    schema = client.get("/openapi.json").json()
    assert "/conformance/run" in schema["paths"]
    assert "RunRequest" in schema["components"]["schemas"]
    if openapi_json:
        openapi_json.write_text(json.dumps(schema), encoding="utf-8")

    graph = StateGraph(WorkflowState, context_schema=WorkflowContext)
    graph.add_node("evaluate", evaluate)
    graph.add_edge(START, "evaluate")
    graph.add_edge("evaluate", END)
    result = graph.compile().invoke(
        {"application_id": "app-1"},
        context=WorkflowContext(prefix="workflow"),
    )
    assert result["outcome"] == "workflow:completed"

    model = ChatDeepSeek(
        model="deepseek-v4-flash",
        api_key="not-a-real-key",
        max_retries=0,
    )
    assert model.max_retries == 0
    assert model.with_structured_output(RunResult) is not None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--openapi-json", type=Path)
    arguments = parser.parse_args()
    run_conformance(arguments.openapi_json)
    print("runtime adapter conformance passed")
