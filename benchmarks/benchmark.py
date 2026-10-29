"""Reproducible micro-benchmark for the Luma compiler pipeline and VM.

Run from the repository root:

    python benchmarks/benchmark.py

Results are written to benchmarks/results.json together with the environment
they were measured in. They describe only this machine, this Python version and
this one small workload; they say nothing about how Luma compares to any other
language.
"""

import json
import platform
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from luma import __version__  # noqa: E402
from luma.compiler import Compiler  # noqa: E402
from luma.vm import VirtualMachine  # noqa: E402

SOURCE_FILE = ROOT / "benchmarks" / "programs" / "arithmetic.luma"
RESULTS_FILE = ROOT / "benchmarks" / "results.json"
REPEATS = 7


def measure(function: Callable[[], object], repeats: int = REPEATS) -> dict:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        function()
        samples.append(time.perf_counter() - start)
    return {
        "median_seconds": statistics.median(samples),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "repeats": repeats,
    }


def main() -> None:
    source = SOURCE_FILE.read_text(encoding="utf-8")
    compiler = Compiler()

    result = compiler.compile(source)
    if not result.success or result.bytecode is None:
        raise SystemExit("Benchmark program failed to compile.")
    bytecode = result.bytecode

    output = VirtualMachine(bytecode).execute()
    expected = ["49995000"]
    if list(output.output) != expected:
        raise SystemExit(f"Unexpected benchmark output: {output.output!r}")

    report = {
        "luma_version": __version__,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "program": str(SOURCE_FILE.relative_to(ROOT)).replace("\\", "/"),
        "vm_instructions_per_run": output.instructions_executed,
        "compile_pipeline": measure(lambda: compiler.compile(source)),
        "vm_execution": measure(lambda: VirtualMachine(bytecode).execute()),
    }
    RESULTS_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    vm = report["vm_execution"]
    rate = report["vm_instructions_per_run"] / vm["median_seconds"]
    print(f"Python {report['python']} on {report['platform']}")
    print(f"Program: {report['program']}")
    compile_median = report["compile_pipeline"]["median_seconds"]
    print(f"Compile pipeline median: {compile_median:.6f}s")
    print(f"VM execution median:     {vm['median_seconds']:.6f}s")
    print(f"VM instructions per run: {report['vm_instructions_per_run']}")
    print(f"VM throughput (median):  {rate:,.0f} instructions/second")
    print(f"Wrote {RESULTS_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
