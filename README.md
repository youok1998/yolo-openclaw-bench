# yolo-openclaw-bench

OpenClaw orchestration framework for YOLOv8 benchmark on COCO (mAP, QPS, F1, Precision, Recall + FP/FN image artifacts).

## 1. 准备本地数据集
你说的数据直接放在宿主机 `/dataset`，按下面结构：

```bash
/dataset/
├── images/
│   └── val/
│       ├── 000001.jpg
│       └── ...
├── labels/
│   └── val/
│       ├── 000001.txt
│       └── ...
└── coco_local.yaml
```

`/dataset/coco_local.yaml` 示例：

```yaml
path: /dataset
val: images/val
names:
  0: person
  1: car
  2: bicycle
```

> 注意：`images/val/*.jpg` 必须和 `labels/val/*.txt` 一一对应且同名。

---

## 2. 启动服务

```bash
cd yolo-openclaw-bench
docker compose up -d --build
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

---

## 3. 提交评测任务

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H 'Authorization: Bearer change-me' \
  -H 'Content-Type: application/json' \
  -d '{
    "task":"benchmark_yolov8",
    "model":"models/best.pt",
    "dataset":"/dataset/coco_local.yaml",
    "metrics":["map","qps"],
    "imgsz":640,
    "batch":16,
    "conf":0.25,
    "iou":0.7,
    "device":"cuda:0"
  }'
```

返回示例：

```json
{"job_id":"job_abc123def456","status":"queued"}
```

---

## 4. 查询状态和结果

查状态：

```bash
curl -H 'Authorization: Bearer change-me' \
  http://127.0.0.1:8000/v1/jobs/job_abc123def456
```

查结果：

```bash
curl -H 'Authorization: Bearer change-me' \
  http://127.0.0.1:8000/v1/jobs/job_abc123def456/result
```

结果字段包含：
- `map50`
- `map50_95`
- `precision`
- `recall`
- `f1_score`
- `qps`
- `latency_p50_ms`
- `latency_p95_ms`
- `artifacts.false_negative_image`
- `artifacts.false_positive_image`

---

## 5. 下载漏报/误报图片

```bash
curl -H 'Authorization: Bearer change-me' -o false_negative.jpg \
  http://127.0.0.1:8000/v1/jobs/job_abc123def456/artifacts/false_negative.jpg

curl -H 'Authorization: Bearer change-me' -o false_positive.jpg \
  http://127.0.0.1:8000/v1/jobs/job_abc123def456/artifacts/false_positive.jpg
```

---

## 6. 关键配置说明
- `docker-compose.yml` 已经把宿主机 `/dataset` 挂载到容器 `/dataset`
- API 默认密钥是 `change-me`，建议改成复杂字符串
- Worker 读取 `/app/bench.db`，API/Worker 共享同一个 job 状态库

---

## 7. 常见问题
1) **找不到数据集**
- 检查宿主机 `/dataset/coco_local.yaml` 是否存在
- 检查 compose 挂载是否生效

2) **GPU 没被识别**
- 先在宿主机执行 `nvidia-smi`
- 确保已安装 NVIDIA Container Toolkit

3) **一直 queued 不跑**
- 看 API/Worker 日志：
```bash
docker compose logs -f api worker
```
