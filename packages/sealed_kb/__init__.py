"""封印知识库：只读 load / prove / explain。禁止 import engine 业务模块。"""

from sealed_kb.reasoner import ExplainResult, ProveResult, explain, load, prove
from sealed_kb.roles import consult, gate_ticket, harvest_complete, harvest_guard
from sealed_kb.workbench import pending_items, probe_queue, theme_closure

__all__ = [
    "ExplainResult",
    "ProveResult",
    "consult",
    "explain",
    "gate_ticket",
    "harvest_complete",
    "harvest_guard",
    "load",
    "pending_items",
    "probe_queue",
    "prove",
    "theme_closure",
]
