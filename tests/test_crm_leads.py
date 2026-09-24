"""线索回收与列表。"""

from datetime import date

from sqlalchemy import select

from db.crm_leads import apply_lead_recycle, ensure_demo_leads, list_leads
from db.session import make_engine, session_factory
from db.tables import CrmFollowRecordRow, CrmLeadRow


def _reset_demo_leads(session):
    for code in ("LD20260001", "LD20260002", "LD20260003"):
        row = session.get(CrmLeadRow, code)
        if row:
            session.delete(row)
    for rec in session.scalars(
        select(CrmFollowRecordRow).where(CrmFollowRecordRow.lead_code.like("LD2026000%"))
    ).all():
        session.delete(rec)
    session.commit()


def test_recycle_only_handwritten_lead():
    engine = make_engine(__import__("pathlib").Path("data/scheduling.db"))
    factory = session_factory(engine)
    session = factory()
    try:
        _reset_demo_leads(session)
        ensure_demo_leads(session)
        session.commit()
        n = apply_lead_recycle(session, today=date(2026, 9, 15))
        session.commit()
        assert n >= 1
        recycled = session.get(CrmLeadRow, "LD20260002")
        assert recycled is not None
        assert recycled.status == "待分配"
        assert recycled.owner_sales == ""
        kept = session.get(CrmLeadRow, "LD20260003")
        assert kept is not None
        assert kept.owner_sales == "李业务"
    finally:
        session.close()


def test_sales_sees_only_own_leads():
    engine = make_engine(__import__("pathlib").Path("data/scheduling.db"))
    factory = session_factory(engine)
    session = factory()
    try:
        _reset_demo_leads(session)
        ensure_demo_leads(session)
        apply_lead_recycle(session, today=date(2026, 9, 15))
        session.commit()
        rows = list_leads(session, role="SALES", pool=False, today=date(2026, 9, 15))
        assert all(r["owner_sales"] == "李业务" for r in rows)
        pool = list_leads(session, role="SALES_MGR", pool=True, today=date(2026, 9, 15))
        assert any(r["code"] == "LD20260001" for r in pool)
    finally:
        session.close()
