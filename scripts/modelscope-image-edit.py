#!/usr/bin/env python3
"""Compatibility wrapper for Source2Launch image editing.

Prefer the main CLI:

  source2launch image . \
    --provider modelscope \
    --model FireRedTeam/FireRed-Image-Edit-1.1 \
    --image-file launch-assets/images/source.png \
    --prompt "Turn this into a source-grounded launch cover" \
    --output launch-assets/images/cover-edit.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from source2launch.image import generate_image  # noqa: E402

DEFAULT_MODEL = "FireRedTeam/FireRed-Image-Edit-1.1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a ModelScope image edit through Source2Launch.")
    parser.add_argument("--image", "--image-file", dest="image_file", help="Local reference image path.")
    parser.add_argument("--image-url", help="Remote reference image URL.")
    parser.add_argument("--output", default="launch-assets/images/xhs-cover-edit.png")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--base-url", help="ModelScope base URL. Defaults to SOURCE2LAUNCH_MODELSCOPE_BASE_URL.")
    parser.add_argument("--poll-interval-ms", type=int)
    parser.add_argument("--timeout-ms", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.image_file and not args.image_url:
        parser.error("Provide --image-file/--image or --image-url.")

    result = generate_image(
        None,
        prompt=args.prompt,
        platform="xhs",
        output_path=args.output,
        options={
            "provider": "modelscope",
            "model": args.model,
            "base_url": args.base_url,
            "image_file": args.image_file,
            "image_url": args.image_url,
            "poll_interval_ms": args.poll_interval_ms,
            "timeout_ms": args.timeout_ms,
        },
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"已保存 {result['outputPath']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
