# Executed validation

Validated locally on 2026-10-08 with Python 3.13.11, macOS 27.0.1, arm64.
The model has no external runtime packages. Commands run from the project root.
The plain-text command evidence is [results/validation.txt](../results/validation.txt).

| Check | Executed result |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | 14 tests passed, including 240 seeded randomized cases |
| Fixed 2×3 · 3×2 example | Exact C=[[58,64],[139,154]]; 11 clocks; compute wave 1,3,4,3,1 MACs |
| Rectangular and ragged arrays | Exact products, masks, registered forwarding, byte and MAC accounting passed |
| Bandwidth, capacity, invalid data, trace bounds | Timing isolation, exact transaction bytes, explicit input rejection passed |
| Live HTTP server | Static assets, fixed-result API, summary API, 400 errors and 404 route rejection passed |
| `python3 -m experiments.run` | All 11 configurations passed independent reference comparison |
| `python3 -m experiments.tiny` | Five-cycle SVG rendered from the verified trace |
| Clean copy | Fresh temporary project copy and virtual environment; no third-party project dependencies installed or required; no inherited environment variables |
| Artifact regeneration in clean copy | JSON trace, teaching SVG, experiment JSON/CSV, bandwidth SVG all byte-identical to included results |
| Invalid CLI bandwidth | Exit status 2 and explicit validation error |

## Browser checks

The interface was exercised in Chrome on the local host. The fixed example
displayed the expected product and 11-clock schedule. Stepping from compute
cycle 2 to 3 advanced from 3 to 4 active MACs and updated each accumulator.
The comparison produced 2×2, 4×4, and 8×8 results on the same fixed matrices;
all had 11 clocks and 28 external bytes, while compute utilization fell from
60.0% to 15.0% to 3.8% because the extra physical PEs were masked.

A seeded 5×7 · 7×3 workload on a 4×4 array displayed 39 clocks, 137 external
bytes, and two tiles. Scrubbing to its final clock displayed C[4:5,0:3], three
valid accumulators, thirteen masked PEs, and a completed 12-byte store.
Setting scratchpad capacity to one byte produced the explicit capacity error
and retained the previous successful result with a visible explanation.

Desktop layout and a 400 CSS-pixel responsive viewport were visually inspected.
The smaller viewport stacked controls and kept the cycle controls and array
readable. Browser console inspection distinguished expected capacity rejection
and host extension errors from application behavior. No application JavaScript
exception was observed. The final interface includes a local SVG favicon.

## Repository screenshots

The README images were captured from the running local interface on 2026-10-08
with Playwright CLI 0.1.22 and HeadlessChrome 154.0.0.0, using an isolated browser
profile. `teaching-example.png` is a direct 1440×1200 viewport capture at clock 6.
`ragged-tile.png` is a direct 1052×1715 capture of the workspace element at
clock 39. Both show the synthetic workloads described in the README.

Both saved PNGs were visually inspected. They contain application content only,
without browser chrome, desktop, account details, or personal paths. No UI was
generated or altered for the images. PNG chunk CRCs were checked; neither image
contains text or EXIF metadata. The capture session reported no console messages.

## Continuous integration

The repository workflow runs the unittest suite and regenerates all five
deterministic artifacts on Python 3.10, 3.13, and 3.14 on Ubuntu 24.04. A diff
against the committed `results/` must be empty. The workflow installs no
third-party project dependencies. Its per-commit status is recorded by GitHub
Actions; the historical local execution evidence above is separate.

## Validation boundaries

The recorded macOS run used Python 3.13.11; it did not execute Python 3.10–3.12
or other operating systems. The CI matrix provides separate Linux coverage.
Safari, Firefox, physical
mobile devices, a screen reader audit, long-running autoplay, and the browser's
file download flow were not exercised. JSON output was verified through the
CLI, not by a browser download. Chrome's precise version was not captured during
the initial manual run; the isolated screenshot browser is identified above.

No hardware, power, area, RTL, synthesis, or wall-clock throughput benchmark was
performed. Cycle counts, utilization, and transfer bytes are defined simulation
outputs. The CI workflow validates software behavior and artifact reproduction;
it does not deploy a service, enable GitHub Pages, or measure hardware.
