# Domain 4 Project Instructions

Apply the superpowers workflow by default in this repository.

## Repository Purpose

- This repository exists to establish the prerequisites, resource plan, environment configuration, and governance baseline for Domain 4.
- Treat the design documents under `docs/` as the current requirements source for planning, implementation, and validation.
- Treat `.env.local.L4` at the repository root as the active Domain 4 environment contract.

## Authoritative Inputs

- Read `docs/charters/` first when a task may be affected by project-wide charter rules, cross-app architecture constraints, or AI execution guardrails.
- Read `docs/design-L2-domain-4-prerequisites.md` before changing Domain 4 prerequisites, bootstrap flows, resource provisioning, API exposure, APIM integration, or Application Insights expectations.
- Read `docs/design-L2-domain-4-prerequisites-lowleveldesign.md` before changing Azure resources, SPN setup, environment variables, or deployment assumptions.
- Read `docs/design-L2-domain-4-output-trustworthiness.md` before changing Domain 4 target coverage, metrics, API expectations, or telemetry fields.
- Read `docs/design-L1-overview.md` when a change affects the broader dashboard, KPI semantics, or cross-domain framing.
- Use `.env.local.L4` as the source of truth for current variable names and filled values. Do not reintroduce `.env.local.L4.example` unless explicitly asked.

## Required Workflow

1. Identify the closest concrete anchor: a file, symbol, test, command, or failing behavior.
2. Form one falsifiable local hypothesis about the behavior or needed change.
3. Run the cheapest discriminating check available before widening scope.
4. Make the smallest grounded edit that tests or implements the hypothesis.
5. Validate immediately with the narrowest relevant test, lint, build, or runtime check.
6. Iterate locally until the slice is correct before expanding to adjacent work.
7. Summarize outcome, residual risk, and the next concrete step.

## Repository Constraints

- Preserve the existing Domain 4 naming and resource model unless the user explicitly changes the requirements.
- Keep Domain 4 target types separate in design and implementation. Do not merge AI apps, Foundry models, Foundry agents, Copilot Studio agents, VM-hosted models, Tier 1 apps, and Tier 2 apps into a single undifferentiated metric or workflow.
- Keep APIM and Application Insights roles aligned with the design docs: APIM is the controlled gateway and unified test entrypoint; Application Insights is the evidence and telemetry sink.
- When a task touches target endpoints, telemetry, or coverage logic, preserve the documented `target_type`, `target_id`, `model_name`, `model_version`, `test_tool`, `test_run_id`, `response_id`, and `correlation_id` concepts unless the design docs are intentionally being revised.
- Prefer updates to `docs/` when clarifying or extending requirements, rather than scattering requirement notes into unrelated files.
- Treat `docs/charters/` as the future home for repository-wide charter rules that must apply across all apps in this workspace.
- Treat `.env.local.L4` as sensitive. Do not print, duplicate, or rewrite secrets unless the task explicitly requires it.

## Output Expectations

- Prefer minimal, targeted changes over broad rewrites.
- Preserve existing style and public APIs unless the task requires change.
- Validate with executable checks whenever the environment provides them.
- Call out blockers, assumptions, and missing inputs explicitly.

The repository also includes the explicit superpowers skill and companion agents under `.github/skills/` and `.github/agents/`.