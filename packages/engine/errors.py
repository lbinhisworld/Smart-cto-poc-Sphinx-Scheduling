"""引擎异常。未实现逻辑用 NotImplementedError，禁止用 mock 掩盖。"""


class SchedulingLoopError(RuntimeError):
    """倒排循环超过 guard（365）—— BR-20 防死循环。"""


class UomConvertError(ValueError):
    """换算链上找不到 from_uom → to_uom 路径（BR-03）。"""


class SphMissingError(ValueError):
    """品项+组缺少 SPH，或 CREW 口径缺 sph_crew（错误码 1002）。"""
