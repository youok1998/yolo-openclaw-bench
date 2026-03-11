import os
import subprocess
import requests

OPENCLAW_BASE = os.getenv("OPENCLAW_BASE", "http://localhost:3100")
OPENCLAW_TOKEN = os.getenv("OPENCLAW_TOKEN", "")
AGENT_ID = os.getenv("OPENCLAW_AGENT_ID", "main")


def spawn_job(job_id: str):
    payload = {
        "agentId": AGENT_ID,
        "label": f"bench-{job_id}",
        "task": f"Run benchmark job {job_id} by executing worker/run_benchmark.py and write artifacts/{job_id}/result.json",
        "cleanup": "keep"
    }
    headers = {"Authorization": f"Bearer {OPENCLAW_TOKEN}"} if OPENCLAW_TOKEN else {}
    try:
        r = requests.post(f"{OPENCLAW_BASE}/sessions/spawn", json=payload, headers=headers, timeout=8)
        if r.ok:
            return
    except Exception:
        pass

    # fallback: local process mode
    subprocess.Popen(["python3", "worker/run_benchmark.py", job_id], cwd=".")
