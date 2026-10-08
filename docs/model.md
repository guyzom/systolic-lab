# Architecture and memory model

## Computation

For A[M×K] and B[K×N], compute `C[i,j] = Σ A[i,k] B[k,j]`. All operands are
signed 8-bit integers. Products and accumulators use exact Python integers;
within the supported K≤128, the worst absolute dot-product bound is
`128 × 128 × 128 = 2,097,152`, so every result also fits signed int32. There is
no overflow, saturation, rounding, or quantization policy to simulate.

The physical array has R rows and S columns. The scheduler visits output tiles
in row-major order: row offset 0,R,2R,…, then column offset 0,S,2S,…. For each
tile, h=min(R, remaining rows), w=min(S, remaining columns). K is streamed in
full. Accumulators reset before each output tile; there are no partial sums
between different tiles. Unused PEs are masked and do not compute or forward.

## Clock edge semantics

Compute-local time t starts at zero. Inject A[row+i,k] at the west boundary of
row i at `t=k+i`; inject B[k,col+j] at the north boundary of column j at `t=k+j`.
Each token contains its value and reduction index k. Internal inputs read the
previous edge's neighbor outputs. After one eastward hop per column and one
southward hop per row, PE[i,j] sees the matching pair at `t=k+i+j`.

On an edge, each valid pair performs `acc ← acc + a×b` and both tokens advance
to the PE's output registers. Index disagreement raises a simulation error.
The last useful MAC occurs at `t=(K−1)+(h−1)+(w−1)`, so the phase lasts
`K+h+w−2` edges. Termination follows the last active PE, including partial
tiles; the model does not drain inactive physical rows and columns.

A trace frame records inputs used and accumulators **after** one counted edge.
Global clock numbers and phase clock numbers are one-based; operand index k
and tile IDs are zero-based. The first global clock is the first load edge.
Memory frames keep all PE accumulators visible, with no MAC marked active.
The output matrix in the response is the final result, independently of the
cycle selected in the UI. PE states are the cycle-local result.

## Memory contract

| Component | Capacity / transfer rule | Timing effect |
| --- | --- | --- |
| External memory | A and B initially resident; C initially absent; effectively unbounded | Shared bus bandwidth β integer bytes/clock; load and store serialized |
| Operand scratchpad | Configurable Q bytes; requires K(h+w) actual operand bytes | Full tile loaded before compute; insufficient capacity is an error |
| Boundary SRAM ports | One int8 per active row lane and per active column lane per clock | Enough independent ports for skewed injection; no bank conflicts or stalls |
| PE registers | One A token and one B token per active PE | One registered east/south hop per compute clock |
| PE accumulator | One int32-equivalent value per physical PE; separate from Q | Local MAC each compute clock; no external partial-sum spills |
| Result gather | Ideal direct gather from accumulators; no scratchpad reservation | Bus store includes four bytes per valid C output; no extra gather cycles |

Each tile uses exactly one load transaction and one store transaction. The
single load includes both A and B tile data. Bytes are packed into the bus
budget; elements may straddle bus cycles, including a four-byte output on a
one-byte-wide bus. The first L edges transfer zero bytes (transaction setup).
Then transfer up to β bytes per edge until complete. There are no bursts,
addresses, DRAM rows, alignment, cache lines, or memory bank models.

```
tile operand bytes = K(h+w)                 # 1 byte per A/B value
tile output bytes  = 4hw                    # 4 bytes per C value
load clocks        = L + ceil(K(h+w)/β)
compute clocks     = K + h + w - 2
store clocks       = L + ceil(4hw/β)
tile clocks        = load + compute + store
total clocks       = sum of all tile clocks
```

There is no double buffering or compute/transfer overlap. Increasing β shortens
the load/store phases until setup and ceiling effects dominate; it never
changes compute clocks or the product. Increasing Q beyond the required
capacity changes neither traffic nor cycles in this model. Operands are
reloaded for each output tile; no cross-tile reuse is retained. The load and
store bytes are logical payload; setup cycles contribute time but no bytes.

## Metrics and baselines

One MAC counts as one multiplication plus one addition; report MACs, rather
than converting implicitly to two operations. Zero operands still count as
useful scheduled MACs. `useful_macs = MNK`, checked after each simulation.

```
compute utilization = MNK / (R*S*compute_clocks)
overall utilization = MNK / (R*S*total_clocks)
masked PE clocks    = Σ (R*S-h*w)*(K+h+w-2)
external bytes      = total operand loads + total output stores
intensity           = MNK / external bytes                   # MAC/B
mesh operand bytes  = Σ [h*K*(w-1) + w*K*(h-1)]              # int8 hops
```

The unused slots during compute include both masked PEs and fill/drain bubbles
in valid PEs. Mesh traffic counts an operand consumed from an internal neighbor,
not boundary injection, ejection, accumulator access, control bits, or memory
stores. Each such hop costs one payload byte. Scratchpad read count equals
operand load bytes because each int8 operand is injected once per output tile.

The `naive_external_bytes = 2MNK+4MN` baseline is a specified no-reuse algorithm:
read both operands externally for every scalar MAC and write C once. It is a
traffic comparison only, not a CPU/cache model or timing baseline. A bandwidth
setting is shared across every compared configuration. No energy or wall-clock
speedup follows directly from these counters.

## Correctness oracle and scope

`reference.matmul` forms columns of B and computes exact row–column dot
products. It shares neither the simulator's scheduler nor register forwarding.
The simulator compares every output element and its MAC count to this oracle.
Tests additionally check timing, traffic, masks, token alignment, and capacity;
a correct final product alone is not sufficient to verify cycle behavior.

The intentionally narrow model isolates regular operand reuse, wavefronts,
physical utilization, tile edges, and memory serialization. It does not predict
TPU performance: TPU v1 uses preloaded weights, separate accumulator memory,
and overlap facilities absent here. See [sources.md](sources.md).
