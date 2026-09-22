from __future__ import annotations

import argparse

from sealed_kb.ask import ask as ask_question
from sealed_kb.reasoner import explain, prove
from sealed_kb.roles import harvest_complete
from sealed_kb.store import format_tree


def _ctx(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="封印知识库 prove / explain / tree / ask / pending / probe")
    parser.add_argument(
        "cmd",
        choices=("prove", "explain", "tree", "ask", "harvest-check", "pending", "probe", "journal"),
    )
    parser.add_argument("claim", nargs="?")
    parser.add_argument("--情境", default="")
    parser.add_argument("--角色", default="默认")
    parser.add_argument("--确认", action="store_true")
    parser.add_argument("--运行结果", action="store_true")
    parser.add_argument("--主题", default="")
    args = parser.parse_args()
    if args.cmd in {"pending", "probe", "journal"}:
        from sealed_kb.workbench import DEFAULT_THEME, format_journal, format_pending, format_probe

        theme = args.主题 or args.claim or DEFAULT_THEME
        if args.cmd == "pending":
            print(format_pending(theme))
            return
        if args.cmd == "probe":
            print(format_probe(theme))
            return
        print(format_journal())
        return
    if args.cmd == "tree":
        from sealed_kb.store import format_runtime_tree

        print(format_tree())
        if args.运行结果:
            extra = format_runtime_tree()
            if extra:
                print()
                print("【运行结果】")
                print(extra)
        return
    if not args.claim:
        parser.error("prove / explain / ask / harvest-check 需要编号或问话")
    if args.cmd == "ask":
        result = ask_question(args.claim, None if args.角色 == "默认" else args.角色)
        print(result.verdict)
        print(result.mode)
        if result.chain:
            print("链: " + " → ".join(result.chain))
        print(result.text)
        return
    if args.cmd == "harvest-check":
        checked = harvest_complete(args.claim, confirmed=args.确认)
        print("完成" if checked.ok else "未完成")
        if checked.path:
            print("链: " + " → ".join(checked.path))
        if checked.reason:
            print(checked.reason)
        return
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
