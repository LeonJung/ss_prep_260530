#!/usr/bin/env bash
# Compact one-shot dataset summary. Prints only the fields we actually
# need to verify a recorded LeRobotDataset:
#   fps, total_episodes, total_frames, feature names + dtype + shape,
#   and per-column shape/dtype of the first parquet row.
#
# Usage:
#   docker compose run --rm pai_teach bash scripts/inspect_dataset.sh datasets/<task>
set -e
DATASET="${1:?usage: bash scripts/inspect_dataset.sh <dataset_root>}"

python3 - <<EOF
import glob, json
from pathlib import Path
import pyarrow.parquet as pq

root = Path("$DATASET")
info = json.loads((root / "meta" / "info.json").read_text())
print(f"fps             : {info.get('fps')}")
print(f"total_episodes  : {info.get('total_episodes')}")
print(f"total_frames    : {info.get('total_frames')}")
print(f"data_path       : {info.get('data_path')}")
print(f"video_path      : {info.get('video_path')}")
print("features:")
for k, f in info.get("features", {}).items():
    print(f"  {k:35s} dtype={f.get('dtype'):<8s} shape={tuple(f.get('shape', ()))}")

files = sorted(glob.glob(str(root / "data" / "chunk-*" / "file-*.parquet")))
if not files:
    print("\n(no parquet data files found)")
else:
    print(f"\nfirst parquet: {Path(files[0]).relative_to(root)}")
    t = pq.read_table(files[0])
    row = t.to_pandas().iloc[0]
    print(f"  rows={t.num_rows}  cols={t.num_columns}")
    for col in t.column_names:
        v = row[col]
        try:
            import numpy as np
            if isinstance(v, np.ndarray):
                print(f"    {col:35s} ndarray shape={v.shape} dtype={v.dtype}")
            elif hasattr(v, "__len__") and not isinstance(v, str):
                print(f"    {col:35s} list len={len(v)} elem0_type={type(v[0]).__name__ if len(v) else '-'}")
            else:
                s = repr(v)
                if len(s) > 40: s = s[:37] + "..."
                print(f"    {col:35s} {type(v).__name__}={s}")
        except Exception as e:
            print(f"    {col:35s} ({e})")
EOF
