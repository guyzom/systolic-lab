PYTHON ?= python3

.PHONY: test demo experiments serve
test:
	$(PYTHON) -m unittest discover -s tests -v
demo:
	$(PYTHON) -m systolic_lab simulate --input examples/tiny.json --rows 2 --cols 2 --bandwidth 8 --latency 1 --trace --output results/tiny-trace.json
	$(PYTHON) -m experiments.tiny
experiments:
	$(PYTHON) -m experiments.run
serve:
	$(PYTHON) -m systolic_lab serve
