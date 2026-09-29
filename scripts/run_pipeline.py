"""Run the full analysis pipeline on one recording and print the result with stage timings.

    docker compose run --rm -v "${PWD}:/app" api python -m scripts.run_pipeline sample_data/sample_meeting.wav
"""
import argparse
import logging
import sys
import time

from app.services.pipeline import analyze_meeting


class _StageTimer(logging.Handler):
    """Prints elapsed time whenever the pipeline logs a new stage."""

    def __init__(self):
        super().__init__()
        self.started = time.perf_counter()

    def emit(self, record):
        elapsed = time.perf_counter() - self.started
        print(f"[{elapsed:7.1f}s] {record.getMessage()}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", help="Path to a WAV/MP3/M4A file")
    args = parser.parse_args()

    pipeline_logger = logging.getLogger("app.services.pipeline")
    pipeline_logger.setLevel(logging.INFO)
    pipeline_logger.addHandler(_StageTimer())

    result = analyze_meeting(args.audio)
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
