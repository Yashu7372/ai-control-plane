# AI Control Plane

Generalized prototype for durable AI-assisted delivery workflows with DAG dependencies, approvals, retries, cancellation, evidence, REST APIs, and a worker.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
python run.py
```

In another terminal:

```bash
python -m control_plane.worker
```

Create a run with `POST /runs`, inspect it with `GET /runs/{run_id}`, and approve the `approval` gate through the decision endpoint.

All ongoing changes are maintained on `ai-control-plane-dev`.
