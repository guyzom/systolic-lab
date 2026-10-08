# Primary sources and material provenance

1. H. T. Kung, **Why Systolic Architectures?**, *Computer* 15(1), 37–46,
   January 1982. DOI: 10.1109/MC.1982.1653825.
   [Author-hosted paper](https://www.eecs.harvard.edu/~htk/publication/1982-kung-why-systolic-architecture.pdf).
   The relevant principles are local regular communication, clocked data flow,
   and reuse of values across multiple computations per memory access. The
   simulator applies these principles to a two-dimensional dot-product schedule.

2. Norman P. Jouppi et al., **In-Datacenter Performance Analysis of a Tensor
   Processing Unit**, ISCA 2017. DOI: 10.1145/3079856.3080246.
   [Authors' arXiv manuscript](https://arxiv.org/abs/1704.04760),
   [PDF](https://arxiv.org/pdf/1704.04760).
   Section 2 and Figure 4 describe systolic execution, a diagonal wavefront,
   MAC units, preloaded weights, and software-managed memory. Section 4 and
   Table 3 motivate distinguishing available arithmetic capacity from memory
   waiting and useful utilization. The original architecture includes an 8-bit
   256×256 matrix unit and separate 32-bit accumulator storage.

The implemented choice is output stationary: both operands travel and the
sum remains in a PE. This differs from the paper's preloaded-weight behavior.
Array geometry, serial memory protocol, transaction latency, scratchpad
capacity, masked edges, and termination rules are explicit pedagogical choices;
they are not claimed to be TPU specifications.

The code, interface, input examples, and SVG diagrams are original project
material. Data is synthetic. No paper text, diagrams, datasets, templates,
third-party source code, images, or fonts are bundled. The papers are cited by
link rather than redistributed. Python's standard library is used at runtime
and is not bundled. Browser fonts come from the local system; no font files or
CDN resources are included. No third-party package lockfile or license notice
is required by a bundled dependency because no such dependency is present.

The PNG screenshots in `docs/images/` are captures of the running local
interface with the synthetic workloads described in the README. Browser
capture tooling is not bundled and is not required to run the project.

CI references GitHub's [checkout](https://github.com/actions/checkout) and
[setup-python](https://github.com/actions/setup-python) actions, pinned to
commit hashes in the workflow. Both actions have MIT licenses in their source
repositories; their code is not copied into this project.

No distribution license has been selected for this project.
