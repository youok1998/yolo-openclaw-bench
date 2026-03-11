from pydantic import BaseModel, Field
from typing import Literal, List, Optional

class JobCreate(BaseModel):
    task: Literal["benchmark_yolov8"] = "benchmark_yolov8"
    model: str = Field(..., description="Model path or URL")
    dataset: str = Field(..., description="COCO yaml path")
    metrics: List[Literal["map", "qps"]] = ["map", "qps"]
    imgsz: int = 640
    batch: int = 16
    conf: float = 0.25
    iou: float = 0.7
    device: str = "cuda:0"

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    message: Optional[str] = None
