from __future__ import annotations

import argparse

from sealed_kb.reasoner import explain, prove


def _ctx(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="封印知识库 prove / explain")
    parser.add_argument("cmd", choices=("prove", "explain"))
    parser.add_argument("claim")
    parser.add_argument("--情境", default="")
    parser.add_argument("--角色", default="默认")
    args = parser.parse_args()
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
