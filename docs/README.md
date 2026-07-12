# Merida Documentation

This directory is the detailed reference for the supported FastAPI, React, and Chrome extension application. Start with the [root README](../README.md) for the product tour and local quick start, then use the guides below when you need operational or implementation detail.

## Get started

- [Operations](operations.md) — prerequisites, environment configuration, readiness, verification, recovery, and provider checks.
- [Notion schema](notion-schema.md) — required Applications, Resumes, and Notes databases, relations, properties, and Master Resume requirements.
- [Extension](extension.md) — Chrome MV3 installation, side-panel behavior, settings, capture states, and privacy boundaries.

## Understand the workflows

- [Workflows](workflows.md) — Application Capture, Application Analysis, and Resume Creation from the operator’s perspective.
- [Frontend](frontend.md) — dashboard behavior, queue states, readiness, errors, and operator-facing interaction rules.
- [AI and ML workflows](ai-workflows.md) — model boundaries, evidence validation, deterministic Matching, structured output, and recovery.

## Explore the codebase

- [Architecture](architecture.md) — runtime topology, ownership, module seams, trust boundaries, and storage.
- [Codebase structure](codebase-structure.md) — implemented paths, feature ownership, and test seams.
- [Routes](routes.md) — the `/api/v1` public contract, response rules, authentication, and route details.

The [CONTEXT-MAP](../CONTEXT-MAP.md) records feature ownership and canonical domain language for contributors working across the repository.
