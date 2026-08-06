---
name: to-tasks
description: Breaks down an existing Product Requirements Document (PRD) into atomic, locally saved task files. Use when preparing to implement a completed PRD.
---

# Task Breakdown Generator

## Description

This skill reads a completed PRD and breaks it down into a series of atomic, independently executable tasks. Instead of pushing to an external issue tracker, it saves each task as a markdown file within a dedicated `.ai-context/issues/` subdirectory.

## Process

When asked to break down a PRD into tasks:

1. Ask the user which PRD from `.ai-context/prds/` they want to process, if not specified.
2. Read the selected PRD and the task template from `issue-template.md` located in the same directory as this skill.
3. Determine the sequential list of atomic tasks required to complete the PRD.
4. Create a new directory named after the PRD: `.ai-context/issues/<prd-filename-without-extension>/`.
5. Generate a markdown file for each task inside that new directory. Prefix the filenames with sequential numbers to indicate implementation order (e.g., `01-setup-pydantic-models.md`, `02-duckdb-migrations.md`).

## Constraints & Guidelines

- **Atomic Scope:** Each task must be small enough to be completed in a single development session by one person.
- **Sequential Ordering:** Ensure the numbering of the files reflects a logical build order (e.g., define data models before creating API routes).
- **Stack Consistency:** Implementation details in the tasks must align with the stack defined in the PRD (`uv`, `Pydantic v2`).
- **File Paths:** Carry over the exact file paths defined in the PRD into the relevant tasks to guide the implementation agent.
