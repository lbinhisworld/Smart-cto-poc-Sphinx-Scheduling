"""报价单打印 HTML / PDF（抬头客户名，不含成本）。"""

from __future__ import annotations

from html import escape
from io import BytesIO

from sqlalchemy.orm import Session

from db.quote_service import get_quote
from db.tables import CrmCustomerRow


def quote_print_html(session: Session, code: str, *, hide_cost: bool = True) -> str:
    quote = get_quote(session, code)
    if quote is None:
        raise ValueError("报价不存在")
    cust = session.get(CrmCustomerRow, quote["customer_code"])
    customer_name = cust.name if cust else quote["customer_code"]
    lines_html = ""
    for i, ln in enumerate(quote.get("lines") or [], start=1):
        price = ln.get("unit_price_tax_in") or ln.get("unit_price") or 0
        lines_html += f"""
        <tr>
          <td>{i}</td>
          <td>{escape(str(ln.get('item_name') or ''))}</td>
          <td>{escape(str(ln.get('spec') or ''))}</td>
          <td>{ln.get('qty')}</td>
          <td>{escape(str(ln.get('uom') or ''))}</td>
          <td style="text-align:right">{price}</td>
        </tr>"""
    total = quote.get("total_amount") or 0
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>{escape(code)} · {escape(customer_name)}</title>
<style>
body{{font-family:"PingFang SC",sans-serif;padding:24px;color:#111}}
h1{{font-size:20px;margin:0 0 8px}}
.meta{{color:#555;font-size:13px;margin-bottom:16px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #ccc;padding:6px 8px}}
th{{background:#f3f4f6;text-align:left}}
</style></head>
<body>
<h1>{escape(customer_name)}</h1>
<p class="meta">报价单 {escape(code)} · 有效期至 {escape(str(quote.get('valid_until') or '-'))}</p>
<table>
<thead><tr><th>序号</th><th>产品</th><th>规格</th><th>数量</th><th>单位</th><th>建议售价</th></tr></thead>
<tbody>{lines_html}</tbody>
</table>
<p style="margin-top:16px;text-align:right;font-weight:600">合计：{total}</p>
</body></html>"""


def quote_pdf_bytes(session: Session, code: str) -> tuple[bytes, str]:
    quote = get_quote(session, code)
    cust = session.get(CrmCustomerRow, quote["customer_code"])
    customer_name = cust.name if cust else quote["customer_code"]
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise ValueError("未安装 reportlab，无法导出 PDF") from exc

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("STSong-Light", 14)
    y = 800
    c.drawString(40, y, f"{customer_name} · 报价单 {code}")
    y -= 24
    c.setFont("STSong-Light", 10)
    c.drawString(40, y, f"有效期至 {quote.get('valid_until') or '-'}")
    y -= 28
    for i, ln in enumerate(quote.get("lines") or [], start=1):
        if y < 80:
            c.showPage()
            c.setFont("STSong-Light", 10)
            y = 800
        name = str(ln.get("item_name") or "")
        price = ln.get("unit_price_tax_in") or ln.get("unit_price") or 0
        c.drawString(
            40,
            y,
            f"{i}. {name}  数量 {ln.get('qty')}  单价 {price}",
        )
        y -= 18
    y -= 10
    c.drawString(40, y, f"合计：{quote.get('total_amount') or 0}")
    c.save()
    filename = f"{code}-{customer_name}.pdf"
    return buf.getvalue(), filename
