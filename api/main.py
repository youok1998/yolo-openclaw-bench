import json
import uuid
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from api.schemas import JobCreate
from api.db import init_db, SessionLocal, Job
from api.openclaw_client import spawn_job

import os
API_KEY = os.getenv("API_KEY", "change-me")
app = FastAPI(title="YOLO OpenClaw Bench API")

@app.on_event("startup")
def _startup():
    init_db()


def _check_key(auth: Optional[str]):
    if not auth or not auth.startswith("Bearer ") or auth.split(" ", 1)[1] != API_KEY:
        raise HTTPException(401, "unauthorized")

@app.get('/health')
def health():
    return {'ok': True}

@app.post("/v1/jobs")
def create_job(req: JobCreate, authorization: Optional[str] = Header(default=None)):
    _check_key(authorization)
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    db = SessionLocal()
    db.add(Job(job_id=job_id, status="queued", progress=0, payload_json=req.model_dump_json()))
    db.commit()
    db.close()
    spawn_job(job_id)
    return {"job_id": job_id, "status": "queued"}

@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, authorization: Optional[str] = Header(default=None)):
    _check_key(authorization)
    db = SessionLocal()
    job = db.query(Job).filter(Job.job_id == job_id).first()
    db.close()
    if not job:
        raise HTTPException(404, "job not found")
    return {"job_id": job.job_id, "status": job.status, "progress": job.progress, "message": job.message}

@app.get("/v1/jobs/{job_id}/result")
def get_result(job_id: str, authorization: Optional[str] = Header(default=None)):
    _check_key(authorization)
    db = SessionLocal()
    job = db.query(Job).filter(Job.job_id == job_id).first()
    db.close()
    if not job:
        raise HTTPException(404, "job not found")
    return {"job_id": job.job_id, "status": job.status, "result": json.loads(job.result_json) if job.result_json else None}

@app.get("/v1/jobs/{job_id}/artifacts/{name}")
def get_artifact(job_id: str, name: str, authorization: Optional[str] = Header(default=None)):
    _check_key(authorization)
    file_path = os.path.join("artifacts", job_id, name)
    if not os.path.exists(file_path):
        raise HTTPException(404, "artifact not found")
    return FileResponse(file_path)
