"""Registered east/south operand transport and output-stationary accumulation."""

from dataclasses import asdict, dataclass
from math import ceil
import random

from .reference import matmul

MAX_DIM = 128
MAX_TRACE_CYCLES = 20_000
MAX_TRACE_CELL_STATES = 500_000


@dataclass(frozen=True)
class Config:
    rows: int = 4
    cols: int = 4
    bandwidth: int = 16  # shared off-chip bytes per clock cycle
    latency: int = 2  # setup cycles for each load and store transaction
    scratchpad: int = 32_768  # operand bytes; excludes PE accumulators

    def validate(self):
        for name, low, high in (("rows", 1, 16), ("cols", 1, 16),
                                ("bandwidth", 1, 4096), ("latency", 0, 1024),
                                ("scratchpad", 1, 1_048_576)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in [{low}, {high}]")


def validate_matrices(a, b):
    for name, matrix in (("A", a), ("B", b)):
        if not isinstance(matrix, list) or not 1 <= len(matrix) <= MAX_DIM:
            raise ValueError(f"{name} must have 1..{MAX_DIM} rows")
        width = len(matrix[0]) if isinstance(matrix[0], list) else 0
        if not 1 <= width <= MAX_DIM:
            raise ValueError(f"{name} must have 1..{MAX_DIM} columns")
        for row in matrix:
            if not isinstance(row, list) or len(row) != width:
                raise ValueError(f"{name} must be rectangular")
            if any(type(x) is not int or not -128 <= x <= 127 for x in row):
                raise ValueError(f"{name} operands must be signed int8 integers")
    if len(a[0]) != len(b):
        raise ValueError("A columns must equal B rows")


def synthetic(m: int, k: int, n: int, seed: int = 7):
    """Seeded synthetic data, uniformly selected from integers -4..4."""
    if any(type(x) is not int or not 1 <= x <= MAX_DIM for x in (m, k, n)):
        raise ValueError(f"matrix dimensions must be integers in [1, {MAX_DIM}]")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    return ([[rng.randint(-4, 4) for _ in range(k)] for _ in range(m)],
            [[rng.randint(-4, 4) for _ in range(n)] for _ in range(k)])


def _tiles(m, n, config):
    for row in range(0, m, config.rows):
        for col in range(0, n, config.cols):
            yield row, col, min(config.rows, m - row), min(config.cols, n - col)


def simulate(a, b, config: Config = Config(), *, trace: bool = False):
    """Run one GEMM; trace entries describe the state AFTER a counted clock edge.

    Tokens are (reduction_index, value). Boundary tokens are read from SRAM;
    internal inputs read the previous cycle's neighbor outputs, never outputs
    just created in the current cycle. Masked PEs neither compute nor transport.
    """
    config.validate()
    validate_matrices(a, b)
    m, k, n = len(a), len(b), len(b[0])
    tile_specs = list(_tiles(m, n, config))
    predicted_cycles = 0
    for _, _, h, w in tile_specs:
        load_bytes, store_bytes = k * (h + w), 4 * h * w
        if load_bytes > config.scratchpad:
            raise ValueError(f"tile needs {load_bytes} operand bytes; scratchpad has "
                             f"{config.scratchpad}. Reduce array size or K.")
        predicted_cycles += 2 * config.latency + ceil(load_bytes / config.bandwidth)
        predicted_cycles += ceil(store_bytes / config.bandwidth) + k + h + w - 2
    if trace and predicted_cycles > MAX_TRACE_CYCLES:
        raise ValueError(f"trace would exceed {MAX_TRACE_CYCLES} cycles; use summary mode")
    if trace and predicted_cycles * config.rows * config.cols > MAX_TRACE_CELL_STATES:
        raise ValueError(f"trace would exceed {MAX_TRACE_CELL_STATES} PE states; use summary mode")

    result = [[0] * n for _ in range(m)]
    frames, tiles = [], []
    totals = {"load_cycles": 0, "compute_cycles": 0, "store_cycles": 0,
              "load_bytes": 0, "store_bytes": 0, "link_bytes": 0, "useful_macs": 0,
              "scratchpad_reads": 0, "masked_pe_cycles": 0}
    cycle = 0

    for tile_id, (row, col, h, w) in enumerate(tile_specs):
        acc = [[0] * config.cols for _ in range(config.rows)]
        left = [[None] * config.cols for _ in range(config.rows)]
        top = [[None] * config.cols for _ in range(config.rows)]
        info = {"id": tile_id, "row": row, "col": col, "height": h, "width": w,
                "start_cycle": cycle + 1, "load_bytes": k * (h + w),
                "store_bytes": 4 * h * w, "compute_cycles": k + h + w - 2}

        def frame(phase, local_cycle, cells, moved=0, transferred=0,
                  transaction_bytes=0, setup=False, active=0, links=0):
            if trace:
                frames.append({"cycle": cycle, "tile": tile_id, "phase": phase,
                               "phase_cycle": local_cycle, "cells": cells,
                               "active_macs": active, "link_bytes": links,
                               "transfer_bytes": moved, "transferred_bytes": transferred,
                               "transaction_bytes": transaction_bytes, "setup": setup})

        def cells_idle():
            return [[{"a": None, "b": None, "k": None, "acc": acc[i][j],
                      "active": False, "masked": i >= h or j >= w}
                     for j in range(config.cols)] for i in range(config.rows)]

        def transfer(phase, byte_count):
            nonlocal cycle
            cycles = config.latency + ceil(byte_count / config.bandwidth)
            moved_total = 0
            for tick in range(cycles):
                cycle += 1
                moved = 0 if tick < config.latency else min(
                    config.bandwidth, byte_count - moved_total)
                moved_total += moved
                frame(phase, tick + 1, cells_idle() if trace else [], moved,
                      moved_total, byte_count, tick < config.latency)
            totals[f"{phase}_cycles"] += cycles
            totals[f"{phase}_bytes"] += byte_count
            info[f"{phase}_cycles"] = cycles

        transfer("load", info["load_bytes"])
        info["compute_start_cycle"] = cycle + 1
        for tick in range(info["compute_cycles"]):
            cycle += 1
            next_left = [[None] * config.cols for _ in range(config.rows)]
            next_top = [[None] * config.cols for _ in range(config.rows)]
            cells, active, links = [], 0, 0
            for i in range(config.rows):
                cell_row = []
                for j in range(config.cols):
                    masked = i >= h or j >= w
                    a_token = b_token = None
                    if not masked:
                        ka, kb = tick - i, tick - j
                        a_token = ((ka, a[row + i][ka]) if 0 <= ka < k else None) \
                            if j == 0 else left[i][j - 1]
                        b_token = ((kb, b[kb][col + j]) if 0 <= kb < k else None) \
                            if i == 0 else top[i - 1][j]
                        next_left[i][j], next_top[i][j] = a_token, b_token
                        links += int(j > 0 and a_token is not None)
                        links += int(i > 0 and b_token is not None)
                        totals["scratchpad_reads"] += int(j == 0 and a_token is not None)
                        totals["scratchpad_reads"] += int(i == 0 and b_token is not None)
                    do_mac = a_token is not None and b_token is not None
                    if do_mac:
                        if a_token[0] != b_token[0]:
                            raise RuntimeError("operand reduction indices are not aligned")
                        acc[i][j] += a_token[1] * b_token[1]
                        active += 1
                    if trace:
                        cell_row.append({"a": a_token[1] if a_token else None,
                                         "b": b_token[1] if b_token else None,
                                         "k": a_token[0] if do_mac else None,
                                         "acc": acc[i][j], "active": do_mac,
                                         "masked": masked})
                if trace:
                    cells.append(cell_row)
            left, top = next_left, next_top
            totals["compute_cycles"] += 1
            totals["useful_macs"] += active
            totals["link_bytes"] += links
            totals["masked_pe_cycles"] += config.rows * config.cols - h * w
            frame("compute", tick + 1, cells, active=active, links=links)
        # Results commit after the serialized store transaction completes.
        transfer("store", info["store_bytes"])
        for i in range(h):
            for j in range(w):
                result[row + i][col + j] = acc[i][j]
        info["end_cycle"] = cycle
        tiles.append(info)

    expected = matmul(a, b)
    pes = config.rows * config.cols
    total_bytes = totals["load_bytes"] + totals["store_bytes"]
    totals.update({"total_cycles": cycle, "tile_count": len(tiles),
                   "external_bytes": total_bytes, "peak_operand_bytes": max(
                       tile["load_bytes"] for tile in tiles),
                   "compute_utilization": totals["useful_macs"] / (pes * totals["compute_cycles"]),
                   "overall_utilization": totals["useful_macs"] / (pes * cycle),
                   "macs_per_external_byte": totals["useful_macs"] / total_bytes,
                   "naive_external_bytes": 2 * m * n * k + 4 * m * n})
    if result != expected or totals["useful_macs"] != m * n * k:
        raise RuntimeError("systolic result or MAC count disagrees with the independent oracle")
    return {"schema_version": 1, "shape": {"m": m, "k": k, "n": n},
            "config": asdict(config), "a": a, "b": b, "result": result,
            "reference": expected, "verified": True, "metrics": totals,
            "tiles": tiles, "frames": frames}
