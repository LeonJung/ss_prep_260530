#!/usr/bin/env bash
# Quick look at a recorded LeRobotDataset.
# Prints file layout, meta/info.json (fps, episode/frame counts,
# feature schema), and stats summary so we can verify state vector
# shape, image dtype/shape, and per-channel ranges look sane.
#
# Usage:
#   docker compose run --rm pai_teach bash scripts/inspect_dataset.sh datasets/<task>
set -e
DATASET="${1:?usage: bash scripts/inspect_dataset.sh <dataset_root>}"

echo "=== files (top 20) ==="
find "$DATASET" -type f -not -path "*/cache/*" 2>/dev/null | head -20

echo
echo "=== meta/info.json ==="
cat "$DATASET/meta/info.json" 2>/dev/null || echo "(missing)"

echo
echo "=== meta/stats.json (first 60 lines) ==="
head -60 "$DATASET/meta/stats.json" 2>/dev/null || echo "(missing)"

echo
echo "=== meta/tasks.parquet ==="
python3 -c "
import sys
try:
    import pyarrow.parquet as pq
    t = pq.read_table('$DATASET/meta/tasks.parquet').to_pandas()
    print(t.to_string(max_rows=10))
except Exception as e:
    print(f'(skip: {e})')
"

echo
echo "=== first frame sample ==="
python3 -c "
import sys
try:
    import pyarrow.parquet as pq
    import glob
    f = sorted(glob.glob('$DATASET/data/chunk-*/file-*.parquet'))[0]
    t = pq.read_table(f).to_pandas()
    print(f'parquet shape: {t.shape}, columns: {list(t.columns)}')
    row = t.iloc[0]
    for col in t.columns:
        val = row[col]
        kind = type(val).__name__
        try:
            import numpy as np
            if isinstance(val, np.ndarray):
                print(f'  {col}: ndarray shape={val.shape} dtype={val.dtype}')
                continue
        except Exception:
            pass
        try:
            n = len(val)
            print(f'  {col}: {kind} len={n} first={val[0] if n else None!r}')
        except Exception:
            print(f'  {col}: {kind} value={val!r}')
except Exception as e:
    print(f'(failed: {e})')
"
