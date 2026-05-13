# HippoDEMO Orchestrator

Mock-first FastAPI service for the macOS menu-bar Jarvis flow.

## Run

```bash
cd /Users/massif/Desktop/HippoDEMO
python -m venv orchestrator/.venv
source orchestrator/.venv/bin/activate
pip install -r orchestrator/requirements.txt
uvicorn orchestrator.main:app --reload --host 127.0.0.1 --port 8787
```

## Verify

```bash
curl http://127.0.0.1:8787/health
curl -X POST http://127.0.0.1:8787/session/jarvis-on
curl -X POST http://127.0.0.1:8787/sop/capture-start
curl -X POST http://127.0.0.1:8787/sop/capture-finish
curl -X POST http://127.0.0.1:8787/session/jarvis-off
curl http://127.0.0.1:8787/state
curl http://127.0.0.1:8787/skills
```

Open an SSE stream in a separate terminal:

```bash
curl -N http://127.0.0.1:8787/events
```

## Project_Cortex Adapter

The adapter keeps the `/api/sop_generator` shape but defaults to mock output.
To call a real Project_Cortex backend later:

```bash
export HIPPO_USE_PROJECT_CORTEX=true
export PROJECT_CORTEX_URL=http://127.0.0.1:8000
```

Generated state, artifacts, sessions, active tasks, and skill Markdown files are written under `orchestrator/data/`.
