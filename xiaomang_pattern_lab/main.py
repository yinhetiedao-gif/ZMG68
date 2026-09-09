"""Launch only the disposable Xiaomang Pattern Lab UI Harness."""
from __future__ import annotations

import argparse
from pathlib import Path

from .verification import run_fixed_suite
from .ui_harness import run_pattern_lab


def main() -> int:
    parser = argparse.ArgumentParser(description="小芒图案实验室")
    parser.add_argument("--self-test", action="store_true", help="运行六图无界面技术验证")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1] / "work" / "pattern_lab"))
    args = parser.parse_args()
    if args.self_test:
        report = run_fixed_suite(str(Path(args.workspace) / "acceptance"))
        print("Pattern Lab 自检通过：%d / %d 固定测试图。" % (len(report), len(report)))
        return 0
    run_pattern_lab(args.workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
