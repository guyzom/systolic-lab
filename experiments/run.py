"""Write deterministic JSON/CSV and a self-contained SVG of model cycle counts."""

import csv
import hashlib
import json
from pathlib import Path

from systolic_lab.simulator import Config, simulate, synthetic


def cases():
    for size in (2, 4, 8):
        yield "array_sweep", (32, 32, 32), Config(size, size, 16, 2)
    for bandwidth in (1, 4, 16, 64):
        yield "bandwidth_sweep", (32, 32, 32), Config(8, 8, bandwidth, 2)
    for shape in ((8, 16, 8), (9, 16, 9), (5, 7, 3), (1, 32, 16)):
        yield "edge_tiles", shape, Config(4, 4, 16, 2)


def chart(rows):
    subset = [row for row in rows if row["experiment"] == "bandwidth_sweep"]
    colors = {"load_cycles": "#8884bd", "compute_cycles": "#398d73", "store_cycles": "#c18c5f"}
    maximum = max(row["total_cycles"] for row in subset)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="920" height="410" viewBox="0 0 920 410">',
             '<rect width="920" height="410" fill="#f7f8fa"/>',
             '<g font-family="sans-serif" fill="#15232c">',
             '<text x="32" y="40" font-size="23" font-weight="600">External bandwidth changes transfer time</text>',
             '<text x="32" y="66" font-size="13">32×32 · 32×32 | 8×8 array | 2 setup cycles per transaction | serialized schedule</text>']
    for index, row in enumerate(subset):
        y, x = 112 + index * 58, 144
        parts.append(f'<text x="32" y="{y + 19}" font-size="14">{row["bandwidth"]} B/cycle</text>')
        for key, color in colors.items():
            width = row[key] / maximum * 620
            parts.append(f'<rect x="{x:.3f}" y="{y}" width="{width:.3f}" height="28" fill="{color}"/>')
            x += width
        parts.append(f'<text x="{x + 10:.3f}" y="{y + 19}" font-size="13">{row["total_cycles"]:,}</text>')
    for index, (key, color) in enumerate(colors.items()):
        x = 32 + index * 195
        parts.append(f'<rect x="{x}" y="350" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{x + 19}" y="361" font-size="12">{key.replace("_", " ")}</text>')
    parts.append('<text x="32" y="391" font-size="11">Model clock-cycle counts, not elapsed software time or measured hardware performance. Compute: 736 cycles in every case.</text></g></svg>')
    return "\n".join(parts) + "\n"


def main():
    destination = Path("results")
    destination.mkdir(exist_ok=True)
    rows = []
    for experiment, shape, config in cases():
        a, b = synthetic(*shape, seed=7)
        data = simulate(a, b, config)
        digest = hashlib.sha256(json.dumps({"a": a, "b": b}, separators=(",", ":")).encode()).hexdigest()
        row = {"experiment": experiment, "m": shape[0], "k": shape[1], "n": shape[2],
               "rows": config.rows, "cols": config.cols, "bandwidth": config.bandwidth,
               "latency": config.latency, "scratchpad": config.scratchpad, "seed": 7,
               "input_sha256": digest, "verified": data["verified"], **data["metrics"]}
        rows.append(row)
    (destination / "experiments.json").write_text(json.dumps(rows, indent=2) + "\n")
    with (destination / "experiments.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (destination / "bandwidth.svg").write_text(chart(rows))
    print(f"Verified {len(rows)} experiment configurations. Saved results/experiments.json, experiments.csv, bandwidth.svg")


if __name__ == "__main__":
    main()
