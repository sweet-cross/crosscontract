---
name: to-prd
description: Transforms a feature request into a structured Product Requirements Document (PRD) saved locally. Use when planning a new feature before implementation begins.
---

# Product Requirements Document (PRD) Generator

## Description

This skill transforms a feature request into a structured, locally version-controlled Product Requirements Document (PRD) to map out edge cases, architecture, and dependencies before coding.

## Process

When asked to create a PRD for a feature:

1. Read the PRD template from the `PRD-FORMAT.md` file located in the same directory as this skill.
2. Write the PRD strictly following that template.
3. Save the output as a new markdown file inside the `.ai-context/prds/` directory (e.g., `.ai-context/prds/YYYY-MM-DD-feature-name.md`).

## Constraints & Guidelines

- **Be Exhaustive on Edge Cases:** Think through what could go wrong to prevent bugs.
- **Include File Paths:** Because this PRD is version-controlled alongside the code, explicitly define file paths for new and modified modules to guide implementation.
- **Maintain Stack Consistency:** Respect the existing tech stack. Favor modular designs aligned with `uv`. `fastapi`, `fastapi-users`, and `Pydantic v2`.
- **Team Scale:** Keep the architecture pragmatic and manageable for a three-person development team. Avoid over-engineering.
- **ADR Compliance:** Always scan `.ai-context/` for Architecture Decision Records and explicitly link relevant ones in the PRD.
