#!/usr/bin/env python3
"""Fix LeRobot checkpoint configs for ROBOTIS inference containers.

Some training versions save `pretrained_revision` into policy config.json.
ROBOTIS lerobot-zenoh 1.3.2 uses a stricter ACTConfig/SmolVLAConfig parser and
rejects that extra field during inference. This script removes the field from
all pretrained_model/config.json files under the model root.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def fix_config(path: Path) -> bool:
    data = json.loads(path.read_text())
    if "pretrained_revision" not in data:
        return False

    backup = path.with_suffix(path.suffix + ".bak-pretrained_revision")
    if not backup.exists():
        try:
            backup.write_text(path.read_text())
        except PermissionError:
            print(f"warning: could not write backup: {backup}")

    data.pop("pretrained_revision", None)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove inference-incompatible fields from LeRobot checkpoints."
    )
    parser.add_argument(
        "model_root",
        nargs="?",
        default="data/cyclo/workspace/model/lerobot",
        help="Root containing LeRobot model run folders.",
    )
    args = parser.parse_args()

    root = Path(args.model_root).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"model root does not exist: {root}")

    changed = []
    scanned = 0
    for config in sorted(root.glob("**/pretrained_model/config.json")):
        scanned += 1
        if fix_config(config):
            changed.append(config)

    print(f"scanned={scanned}")
    print(f"changed={len(changed)}")
    for path in changed:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
