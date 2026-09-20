from __future__ import annotations

import argparse

from sealed_kb.reasoner import explain, prove
from sealed_kb.store import format_tree


def _ctx(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="封印知识库 prove / explain / tree")
    parser.add_argument("cmd", choices=("prove", "explain", "tree"))
    parser.add_argument("claim", nargs="?")
    parser.add_argument("--情境", default="")
    parser.add_argument("--角色", default="默认")
    args = parser.parse_args()
    if args.cmd == "tree":
        print(format_tree())
        return
    if not args.claim:
        parser.error("prove / explain 需要结论或主张编号")
    ctx = _ctx(args.情境)
    if args.cmd == "prove":
        result = prove(args.claim, ctx)
        print(result.verdict)
        if result.chain:
            print("链: " + " → ".join(result.chain))
        if result.missing:
            print("缺: " + ", ".join(result.missing))
        return
    print(explain(args.claim, ctx, args.角色))


if __name__ == "__main__":
    main()
