"""演示线拟真词库与校验。"""

import pytest

from db.guided_demo_realism import RealismError, scan_lexicon, validate_display_name


def test_lexicon_scan_passes():
    scan_lexicon()


@pytest.mark.parametrize(
    "bad",
    [
        "测试001",
        "客户3",
        "销售李",
        "仓库王",
        "Customer A",
        "x",
    ],
)
def test_banned_display_names(bad: str):
    with pytest.raises(RealismError):
        validate_display_name(bad, entity_id="GD-ABC-C01")
