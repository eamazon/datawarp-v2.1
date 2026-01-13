# Implementation Plan: Autonomous Supervisor for DataWarp

## Context for the Agent
> **You are a supervisor for a deterministic data pipeline.** You never run code directly. You only read structured JSON artefacts produced by each step: `StepResult`, `ValidationReport`, and `PipelineState`. Based on these, you output a single JSON object called `SupervisorDecision` with one of four allowed actions: "proceed", "retry", "halt", or "escalate". You must stay within the pipeline’s state machine and retry limits. You never invent data, paths, counts, or logs. You only reason about what is explicitly provided. Your job is to mimic a cautious human operator: detect partial failures, interpret validation results, and choose the safest next action.

## Goal Description
To replace the manual supervision of the **DataWarp Backfill Workflow** with an **Autonomous Supervisor**. The system will wrap the existing Python CLI tools (`url_to_manifest`, `load-batch`, etc.) into a deterministic state machine managed by an LLM-based agent.

## User Review Required
> [!IMPORTANT]
> **Workflow Mapping:** This plan strictly maps the "Existing Backfill" (from `docs/BACKFILL_WORKFLOW.md`) to the "Autonomous Architecture".
> The resulting State Machine is: `INIT` → `EXTRACT` → `ENRICH` → `INGEST` → `PUBLISH` → `COMPLETE`.

## Architecture: The 5 Components

### 1. PSE (Pipeline Step Executor)
*   **Role:** The "Hands". Wraps CLI tools.
*   **Input:** `StepSpec` (Command, Args).
*   **Output:** `StepResult` (Exit Code, Artifact Paths).
*   **Implementation:** `src/datawarp/autonomous/executor.py`

### 2. DV (Deterministic Validator)
*   **Role:** The "Eyes". Python logic for factual checks.
*   **Checks:** `file_exists`, `min_size`, `log_regex_absent`.
*   **Output:** `ValidationReport` (Pass/Fail).
*   **Implementation:** `src/datawarp/autonomous/validator.py`

### 3. OSM (Orchestrator State Machine)
*   **Role:** The "Physics". Enforces transitions and retries.
*   **States:** `INIT`, `EXTRACT`, `ENRICH`, `INGEST`, `PUBLISH`, `COMPLETE`, `HALTED`.
*   **Implementation:** `src/datawarp/autonomous/state_machine.py`

### 4. SA (Supervisor Agent)
*   **Role:** The "Brain".
*   **Input:** Result + Report + State.
*   **Output:** `SupervisorDecision` (JSON).
*   **Model:** Gemini Flash (Low cost, high speed).
*   **Implementation:** `src/datawarp/autonomous/agent.py`

### 5. AL (Audit Logger)
*   **Role:** The "Memory". Append-only JSONL.
*   **Implementation:** `src/datawarp/autonomous/logger.py`

## The DataWarp Workflow Mapping

We will configure the `OSM` to run this specific sequence (defined in `pipeline_config.json`):

### Step 1: EXTRACT
*   **Tool:** `scripts/url_to_manifest.py`
*   **Action:** Downloads file, extracts structure to Draft YAML.
*   **Validation:**
    *   `file_exists`: Draft YAML created?
    *   `file_size_min`: Is it > 1KB?

### Step 2: ENRICH
*   **Tool:** `scripts/enrich_manifest.py`
*   **Action:** Adds semantic metadata (via LLM or Reference).
*   **Validation:**
    *   `file_exists`: Enriched YAML created?
    *   `file_exists`: Reference file exists (if using reference)?

### Step 3: INGEST
*   **Tool:** `datawarp load-batch`
*   **Action:** Loads data to PostgreSQL.
*   **Validation:**
    *   `log_regex_absent`: No "ConnectionError", "CRITICAL".
    *   `log_regex_present`: "MIGRATION SUCCESS" or "Loaded".

### Step 4: PUBLISH (Parquet)
*   **Tool:** `scripts/export_to_parquet.py`
*   **Action:** Exports Staging DB to Parquet + Metadata.
*   **Validation:**
    *   `file_exists`: Parquet file created?
    *   `file_size_min`: Is it non-empty?

## Data Contracts (JSON Schemas)

*   **`StepResult`**: `{"step_id": str, "exit_code": int, "artefacts": dict}`
*   **`ValidationReport`**: `{"status": "pass|fail", "checks": list}`
*   **`SupervisorDecision`**: `{"action": "proceed|retry|halt|escalate", "reason": str}`

## Implementation Steps

1.  **Scaffolding:** Create `src/datawarp/autonomous/` and the 5 component files.
2.  **Contracts:** Define Pydantic models in `contracts.py`.
3.  **Components:** Implement PSE, DV, OSM, SA, AL.
4.  **Configuration:** Create `config/autonomous_pipeline.json` mapping the Step 1-4 commands.
5.  **Entrypoint:** Create `scripts/run_autonomous.py`.

## Verification Plan

### Automated Tests
*   **Contract Tests:** Ensure Pydantic models match the JSON specs above.
*   **Validator Tests:** Unit tests for `log_regex_absent` and `file_count`.
*   **State Machine Tests:** Verify `retry` increments attempts and `proceed` advances state.
*   **Mock Agent Tests:** Verify pipeline flow using a "decider" that always returns `{"action": "proceed"}`.

### Manual Verification
*   **Integration Run:** Execute `run_autonomous_pipeline.py` with a **mock** agent (no LLM cost) to verify the plumbing.
*   **Fault Injection:** Manually corrupt a download file and verify the Validator catches it and the State Machine halts/retries.
