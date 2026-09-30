"""Run several recordings through the pipeline in one process, as the worker does, and record GPU memory
and time at every stage.

    docker compose run --rm -v "${PWD}:/app" api python -m scripts.bench_memory FILE [FILE ...]

Stop the worker first so the GPU is not shared. "smi" is the whole card as nvidia-smi sees it (includes
CTranslate2, which PyTorch does not track); "torch reserved" is what PyTorch's caching allocator holds.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

from app.services.pipeline import analyze_meeting


def gpu_used_mb() -> int:
    output = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, check=True).stdout
    return int(output.split()[0])


def torch_reserved_mb() -> int:
    import torch

    return torch.cuda.memory_reserved() // (1024 * 1024) if torch.cuda.is_available() else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()

    print("| Job | File | Stage | Starts at (s) | smi (MB) | torch reserved (MB) |")
    print("|---|---|---|---|---|---|")
    for job, path in enumerate(args.files, start=1):
        started = time.perf_counter()

        def record(stage: str) -> None:
            print(f"| {job} | {path.name} | {stage} | {time.perf_counter() - started:.1f} | {gpu_used_mb()} "
                  f"| {torch_reserved_mb()} |", flush=True)

        try:
            analyze_meeting(path, on_stage=record)
            record("done")
        except Exception as exc:
            print(f"| {job} | {path.name} | FAILED {type(exc).__name__}: {str(exc)[:80]} | "
                  f"{time.perf_counter() - started:.1f} | {gpu_used_mb()} | {torch_reserved_mb()} |", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
