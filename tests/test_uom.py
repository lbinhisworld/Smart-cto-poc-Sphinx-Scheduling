"""§11 T1 单位换算（BR-01 / BR-03 / BR-04 / BR-05）。"""

from decimal import Decimal

import pytest

from engine.errors import UomConvertError
from engine.models import Uom
from engine.uom import to_board


def test_br01_br03_uom_chain_box_to_board(p1_converts):
    assert to_board(Decimal("1"), Uom.BOX, p1_converts) == Decimal("4")


def test_br01_br03_uom_chain_pcs_to_board(p1_converts):
    assert to_board(Decimal("300"), Uom.PCS, p1_converts) == Decimal("12.5")


def test_br05_p4_computable_pcs_board_box_only(p4):
    assert p4.computable is True


def test_br03_no_magic_box_to_board_without_chain(p1_converts):
    """去掉 BOX→BOARD 边后必须失败，证明没有硬编码 4。"""
    stripped = [
        row
        for row in p1_converts
        if not (row.from_uom == Uom.BOX and row.to_uom == Uom.BOARD)
    ]
    with pytest.raises(UomConvertError):
        to_board(Decimal("1"), Uom.BOX, stripped)
