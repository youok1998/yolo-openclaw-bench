# yolo-openclaw-bench

OpenClaw orchestration framework for YOLOv8 benchmark on COCO (mAP, QPS, F1, Precision, Recall + FP/FN image artifacts).

## Architecture
- API gateway (FastAPI): receive jobs, auth, status/result query
- OpenClaw dispatcher: spawn isolated sessions to run benchmark worker
- Worker: run YOLOv8 val and infer benchmark
- Storage: SQLite (demo) + artifacts/result.json

## Quick Start
```bash
docker compose up -d --build
curl -X POST http://localhost:8000/v1/jobs \
  -H 'Authorization: Bearer change-me' \
  -H 'Content-Type: application/json' \
  -d '{"task":"benchmark_yolov8","model":"models/best.pt","dataset":"data/coco.yaml","metrics":["map","qps"],"imgsz":640,"batch":16,"device":"cuda:0"}'
```
