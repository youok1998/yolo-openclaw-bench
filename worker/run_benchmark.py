import json, os

def main(job_id: str):
    os.makedirs(f"artifacts/{job_id}", exist_ok=True)
    result = {
        "map50": 0.0,
        "map50_95": 0.0,
        "qps": 0.0,
        "latency_p50_ms": 0.0,
        "latency_p95_ms": 0.0,
        "note": "Replace with real benchmark logic"
    }
    with open(f"artifacts/{job_id}/result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python worker/run_benchmark.py <job_id>")
    main(sys.argv[1])
