"""封印知识库：只读 load / prove / explain。禁止 import engine 业务模块。"""

from sealed_kb.reasoner import ExplainResult, ProveResult, explain, load, prove
from sealed_kb.roles import consult, gate_ticket, harvest_guard

__all__ = [
    "ExplainResult",
    "ProveResult",
    "consult",
    "explain",
    "gate_ticket",
    "harvest_guard",
    "load",
    "prove",
]
