import json
import os
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Dict, List, Tuple

import yaml
from PIL import Image, ImageDraw
from ultralytics import YOLO

DB_PATH = os.getenv("BENCH_DB_PATH", "bench.db")


def _update_job(job_id: str, status: str = None, progress: int = None, message: str = None, result: Dict = None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    fields, vals = [], []
    if status is not None:
        fields.append("status=?")
        vals.append(status)
    if progress is not None:
        fields.append("progress=?")
        vals.append(progress)
    if message is not None:
        fields.append("message=?")
        vals.append(message)
    if result is not None:
        fields.append("result_json=?")
        vals.append(json.dumps(result, ensure_ascii=False))
    vals.append(job_id)
    cur.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_id=?", vals)
    conn.commit()
    conn.close()


def _load_payload(job_id: str) -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT payload_json FROM jobs WHERE job_id=?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise RuntimeError(f"job_id not found: {job_id}")
    return json.loads(row[0])


def _resolve_images(data_yaml: str) -> List[Path]:
    yaml_path = Path(data_yaml)
    if not yaml_path.exists():
        raise FileNotFoundError(f"dataset yaml not found: {data_yaml}")
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    base = Path(cfg.get("path", yaml_path.parent)).resolve()
    val_entry = cfg.get("val")
    if not val_entry:
        raise RuntimeError("data yaml missing 'val' entry")
    val_dir = Path(val_entry)
    if not val_dir.is_absolute():
        val_dir = (base / val_dir).resolve()

    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = [p for p in val_dir.rglob("*") if p.suffix.lower() in exts]
    if not images:
        raise RuntimeError(f"no images found in val dir: {val_dir}")
    return sorted(images)


def _label_path_from_image(img_path: Path) -> Path:
    parts = list(img_path.parts)
    if "images" in parts:
        i = parts.index("images")
        parts[i] = "labels"
        return Path(*parts).with_suffix(".txt")
    return img_path.with_suffix(".txt")


def _load_gt_boxes(label_path: Path, w: int, h: int):
    gts = []
    if not label_path.exists():
        return gts
    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        cls, xc, yc, bw, bh = map(float, line.split())
        x1 = max(0, (xc - bw / 2) * w)
        y1 = max(0, (yc - bh / 2) * h)
        x2 = min(w, (xc + bw / 2) * w)
        y2 = min(h, (yc + bh / 2) * h)
        gts.append((int(cls), [x1, y1, x2, y2]))
    return gts


def _iou(a, b):
    x1 = max(a[0], b[0]); y1 = max(a[1], b[1])
    x2 = min(a[2], b[2]); y2 = min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter <= 0:
        return 0.0
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def _match(gt_boxes, pred_boxes, iou_thr=0.5):
    matched_gt, matched_pred = set(), set()
    for pi, (pcls, pbox) in enumerate(pred_boxes):
        best = (-1, 0.0)
        for gi, (gcls, gbox) in enumerate(gt_boxes):
            if gi in matched_gt or pcls != gcls:
                continue
            i = _iou(pbox, gbox)
            if i > best[1]:
                best = (gi, i)
        if best[0] >= 0 and best[1] >= iou_thr:
            matched_pred.add(pi)
            matched_gt.add(best[0])
    fp = [pred_boxes[i] for i in range(len(pred_boxes)) if i not in matched_pred]
    fn = [gt_boxes[i] for i in range(len(gt_boxes)) if i not in matched_gt]
    return fp, fn


def _draw_boxes(img_path: Path, boxes, out_path: Path, color=(255, 0, 0), text_prefix=""):
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    for idx, (cls, box) in enumerate(boxes):
        draw.rectangle(box, outline=color, width=3)
        draw.text((box[0] + 2, box[1] + 2), f"{text_prefix}{cls}", fill=color)
    img.save(out_path)


def _benchmark_qps(model: YOLO, images: List[Path], imgsz: int, conf: float, iou: float, device: str):
    sample = images[: min(len(images), 100)]
    for p in sample[:5]:
        model.predict(source=str(p), imgsz=imgsz, conf=conf, iou=iou, device=device, verbose=False)

    lats = []
    t0 = time.perf_counter()
    for p in sample:
        s = time.perf_counter()
        model.predict(source=str(p), imgsz=imgsz, conf=conf, iou=iou, device=device, verbose=False)
        lats.append((time.perf_counter() - s) * 1000)
    total = time.perf_counter() - t0
    qps = len(sample) / total if total > 0 else 0.0
    p50 = statistics.median(lats) if lats else 0.0
    p95 = sorted(lats)[max(0, int(0.95 * len(lats)) - 1)] if lats else 0.0
    return qps, p50, p95


def main(job_id: str):
    out_dir = Path("artifacts") / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    _update_job(job_id, status="running", progress=5, message="loading payload")

    payload = _load_payload(job_id)
    model_path = payload["model"]
    data_yaml = payload["dataset"]
    imgsz = int(payload.get("imgsz", 640))
    conf = float(payload.get("conf", 0.25))
    iou = float(payload.get("iou", 0.7))
    device = payload.get("device", "cuda:0").replace("cuda:", "")

    model = YOLO(model_path)

    _update_job(job_id, progress=20, message="running val for mAP/precision/recall")
    val_res = model.val(data=data_yaml, split="val", imgsz=imgsz, conf=conf, iou=iou, device=device, verbose=False)
    map50 = float(val_res.box.map50)
    map50_95 = float(val_res.box.map)
    precision = float(val_res.box.mp)
    recall = float(val_res.box.mr)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    _update_job(job_id, progress=55, message="running qps benchmark")
    images = _resolve_images(data_yaml)
    qps, p50, p95 = _benchmark_qps(model, images, imgsz, conf, iou, device)

    _update_job(job_id, progress=75, message="finding false negative/false positive examples")
    fp_img = out_dir / "false_positive.jpg"
    fn_img = out_dir / "false_negative.jpg"
    found_fp = found_fn = False

    for img_path in images[:200]:
        pred = model.predict(source=str(img_path), imgsz=imgsz, conf=conf, iou=iou, device=device, verbose=False)[0]
        pred_boxes = []
        if pred.boxes is not None:
            xyxy = pred.boxes.xyxy.cpu().tolist()
            cls = pred.boxes.cls.cpu().tolist()
            for c, b in zip(cls, xyxy):
                pred_boxes.append((int(c), b))

        with Image.open(img_path) as im:
            w, h = im.size
        gt_boxes = _load_gt_boxes(_label_path_from_image(img_path), w, h)
        fp, fn = _match(gt_boxes, pred_boxes, iou_thr=0.5)

        if fn and not found_fn:
            _draw_boxes(img_path, fn, fn_img, color=(255, 165, 0), text_prefix="FN-")
            found_fn = True
        if fp and not found_fp:
            _draw_boxes(img_path, fp, fp_img, color=(255, 0, 0), text_prefix="FP-")
            found_fp = True
        if found_fp and found_fn:
            break

    if not found_fn:
        Image.new("RGB", (640, 120), (30, 30, 30)).save(fn_img)
    if not found_fp:
        Image.new("RGB", (640, 120), (30, 30, 30)).save(fp_img)

    result = {
        "map50": map50,
        "map50_95": map50_95,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "qps": qps,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "artifacts": {
            "false_negative_image": f"/v1/jobs/{job_id}/artifacts/false_negative.jpg",
            "false_positive_image": f"/v1/jobs/{job_id}/artifacts/false_positive.jpg"
        }
    }

    (out_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _update_job(job_id, status="done", progress=100, message="finished", result=result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python worker/run_benchmark.py <job_id>")
    try:
        main(sys.argv[1])
    except Exception as e:
        _update_job(sys.argv[1], status="failed", message=str(e))
        raise
