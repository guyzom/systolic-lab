"""Draw the five compute cycles directly from the checked teaching trace."""

import json
from pathlib import Path


def main():
    data = json.loads(Path("results/tiny-trace.json").read_text())
    frames = [frame for frame in data["frames"] if frame["phase"] == "compute"]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="345" viewBox="0 0 1100 345">',
             '<rect width="1100" height="345" fill="#0d141b"/>',
             '<g font-family="sans-serif" fill="#e9eef1">',
             '<text x="24" y="35" font-size="22" font-weight="600">A clocked diagonal wave · 12 MACs in 5 compute cycles</text>',
             '<text x="24" y="60" font-size="12" fill="#97a9b7">A=[[1,2,3],[4,5,6]]  B=[[7,8],[9,10],[11,12]] · A moves east → · B moves south ↓ · green = MAC this cycle</text>']
    for index, frame in enumerate(frames):
        base = 24 + index * 215
        parts.append(f'<text x="{base}" y="93" font-size="13">Compute {index + 1} · clock {frame["cycle"]}</text>')
        for i, row in enumerate(frame["cells"]):
            for j, cell in enumerate(row):
                x, y = base + j * 93, 107 + i * 88
                fill, stroke = ("#18372e", "#7bddc1") if cell["active"] else ("#151f28", "#40515f")
                parts.append(f'<rect x="{x}" y="{y}" width="86" height="80" rx="4" fill="{fill}" stroke="{stroke}"/>')
                parts.append(f'<text x="{x + 8}" y="{y + 17}" font-size="10" fill="#97a9b7">PE {i},{j}</text>')
                aval, bval = cell["a"] if cell["a"] is not None else "·", cell["b"] if cell["b"] is not None else "·"
                parts.append(f'<text x="{x + 8}" y="{y + 35}" font-size="11" fill="#7bddc1">A {aval} →</text>')
                parts.append(f'<text x="{x + 49}" y="{y + 35}" font-size="11" fill="#f8b982">B {bval} ↓</text>')
                parts.append(f'<text x="{x + 8}" y="{y + 62}" font-size="21">{cell["acc"]}</text>')
        parts.append(f'<text x="{base}" y="300" font-size="12" fill="#97a9b7">{frame["active_macs"]} / 4 PEs active</text>')
    parts.append('<text x="24" y="330" font-size="11" fill="#97a9b7">Displayed numbers are local accumulators after each clock edge. External transfer phases add 3 load + 3 store cycles; total = 11.</text></g></svg>')
    destination = Path("results/tiny-wavefront.svg")
    destination.write_text("\n".join(parts) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
