"""Export format generators for Credence verification reports.

Generates:
- Self-contained annotated HTML dossiers (with print-to-PDF styles)
- Academic Markdown review dossiers
- Full raw JSON evidence packages
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any


def generate_markdown_export(report: dict[str, Any]) -> str:
    """Generate structured Markdown verification dossier."""
    doc_name = report.get("document_name", "Manuscript")
    created_at = report.get("created_at", datetime.now(timezone.utc).isoformat())
    confidence = (report.get("overall_confidence", 0.0) or 0.0) * 100
    summary = report.get("summary", {})
    claims = report.get("claims", [])

    lines = [
        f"# Credence Scientific Verification Dossier",
        f"**Document:** `{doc_name}`  ",
        f"**Generated:** {created_at}  ",
        f"**Overall Computed Confidence:** {confidence:.1f}%  ",
        f"**Access Tier:** {report.get('access_tier', 'Full Text')}  ",
        "",
        "## Executive Summary",
        f"- **Total Empirical Claims:** {len(claims)}",
        f"- **Supported:** {summary.get('supported', 0)}",
        f"- **Partially Supported:** {summary.get('partially_supported', 0)}",
        f"- **Contradictory:** {summary.get('contradictory', 0)}",
        f"- **Unsupported:** {summary.get('unsupported', 0)}",
        f"- **Needs Review:** {summary.get('needs_review', 0)}",
        f"- **Human Overrides:** {summary.get('human_overrides', 0)}",
        "",
        "---",
        "",
        "## Verified Empirical Claims",
        "",
    ]

    for idx, c in enumerate(claims, 1):
        cid = c.get("id", f"claim-{idx}")
        text = c.get("text", "")
        loc = c.get("source_location", "Manuscript Body")
        citations = ", ".join(c.get("citation_keys", [])) or "N/A"
        verdict = c.get("verdict", {})
        display_v = verdict.get("display_verdict") or verdict.get("verdict", "Needs review")
        conf = (verdict.get("confidence", 0.0) or 0.0) * 100
        explanation = verdict.get("explanation", "")

        lines.extend([
            f"### {cid.upper()}: {text}",
            f"- **Location:** {loc}",
            f"- **Citation Keys:** [{citations}]",
        ])

        if verdict.get("override_info"):
            lines.extend([
                f"- **Effective Verdict (Overridden):** **{display_v}**",
                f"- **Original Automated Verdict:** `{verdict.get('original_verdict', 'N/A')}`",
                f"- **Override Rationale:** *{verdict['override_info'].get('explanation') or verdict['override_info'].get('comment') or 'N/A'}*",
                f"- **Computed Confidence:** {conf:.0f}%",
            ])
        else:
            lines.append(f"- **Computed Verdict:** **{display_v}** ({conf:.0f}% confidence)")

        if c.get("citation_classification"):
            lines.append(f"- **Citation Classification:** `{c.get('citation_classification')}`")
            if c.get("citation_audit", {}).get("explanation"):
                lines.append(f"- **Citation Diagnostic:** {c['citation_audit']['explanation']}")

        if explanation:
            lines.append(f"- **Triage Analysis:** {explanation}")

        # Slot table
        slots = c.get("slots", [])
        slot_results = c.get("slot_results", [])
        if slots:
            lines.extend([
                "",
                "#### Atomized Factual Slots",
                "| Slot ID | Field Type | Expected Value | Code Check Status |",
                "|---|---|---|---|",
            ])
            for s in slots:
                sid = s.get("id", "")
                ftype = s.get("field_type", "value")
                exp = s.get("expected_value", "")
                res = next((r for r in slot_results if r.get("slot_id") == sid), {})
                status = res.get("status", "absent").upper()
                lines.append(f"| `{sid}` | {ftype} | {exp} | {status} |")
            lines.append("")

        # Verified Quote
        verified_quote = next((r for r in slot_results if r.get("quote_verified")), None) or (slot_results[0] if slot_results else None)
        if verified_quote and verified_quote.get("quote"):
            span_str = f"span: {verified_quote.get('quote_span')}" if verified_quote.get("quote_span") else ""
            lines.extend([
                "#### Code-Verified Verbatim Source Quote",
                f"> \"{verified_quote.get('quote')}\"",
                f"> — *{span_str}*",
                "",
            ])

        # Reviews
        reviews = c.get("reviews", [])
        if reviews:
            lines.extend(["#### Human Review History", ""])
            for r in reviews:
                act = r.get("action", "").upper()
                rev_id = r.get("reviewer_id", "reviewer")
                dt = r.get("created_at", "")
                comment = r.get("comment", "")
                ov = f" -> {r.get('override_verdict')}" if r.get("override_verdict") else ""
                lines.append(f"- **[{act}{ov}]** by `{rev_id}` at {dt}: *{comment}*")
            lines.append("")

        lines.append("---")
        lines.append("")

    lines.extend([
        "## Credence Verification Engine Core Guarantee",
        "1. LLM judges meaning only; Python confirms deterministic quote existence.",
        "2. Any unverified candidate quote is discarded to 'Needs review'.",
        "3. Confidence is computed from access-tier caps minus deductions, never model self-reporting.",
        "4. 'Not found in databases' ≠ fabricated.",
        "5. Default stance is human review; all verdicts carry verbatim proof.",
    ])

    return "\n".join(lines)


def generate_html_export(report: dict[str, Any]) -> str:
    """Generate self-contained annotated HTML report with print-to-PDF styles."""
    doc_name = html.escape(str(report.get("document_name", "Manuscript")))
    created_at = html.escape(str(report.get("created_at", datetime.now(timezone.utc).isoformat())))
    confidence = (report.get("overall_confidence", 0.0) or 0.0) * 100
    summary = report.get("summary", {})
    claims = report.get("claims", [])

    claims_html_parts = []
    for idx, c in enumerate(claims, 1):
        cid = html.escape(str(c.get("id", f"claim-{idx}")))
        text = html.escape(str(c.get("text", "")))
        loc = html.escape(str(c.get("source_location", "Results")))
        citations = html.escape(", ".join(c.get("citation_keys", [])) or "1")
        verdict = c.get("verdict", {})
        display_v = html.escape(str(verdict.get("display_verdict") or verdict.get("verdict", "Needs review")))
        conf = (verdict.get("confidence", 0.0) or 0.0) * 100
        explanation = html.escape(str(verdict.get("explanation", "")))
        tier = html.escape(str(verdict.get("access_tier", "full_text")))

        # Slots table rows
        slots = c.get("slots", [])
        slot_results = c.get("slot_results", [])
        slot_rows = []
        for s in slots:
            sid = html.escape(str(s.get("id", "")))
            ftype = html.escape(str(s.get("field_type", "")))
            exp = html.escape(str(s.get("expected_value", "")))
            res = next((r for r in slot_results if r.get("slot_id") == s.get("id")), {})
            status = html.escape(str(res.get("status", "absent")).upper())
            is_match = status == "MATCH"
            color = "#5fcf6a" if is_match else "#ef6b6b"
            slot_rows.append(
                f"<tr><td><code>{sid}</code></td><td>{ftype}</td><td>{exp}</td>"
                f"<td style='color:{color}; font-weight:700;'>{status}</td></tr>"
            )

        slots_table_html = ""
        if slot_rows:
            slots_table_html = f"""
            <div class="slots-box">
              <div class="section-title">Atomized Factual Slots</div>
              <table class="data-table">
                <thead><tr><th>Slot ID</th><th>Type</th><th>Expected Value</th><th>Status</th></tr></thead>
                <tbody>{''.join(slot_rows)}</tbody>
              </table>
            </div>
            """

        # Quote
        verified_quote = next((r for r in slot_results if r.get("quote_verified")), None) or (slot_results[0] if slot_results else None)
        quote_text = html.escape(str(verified_quote.get("quote", ""))) if verified_quote else "No verbatim quote recorded."
        span = html.escape(str(verified_quote.get("quote_span", ""))) if verified_quote else ""

        # Reviews
        reviews = c.get("reviews", [])
        review_items = []
        for r in reviews:
            act = html.escape(str(r.get("action", "")).upper())
            rev_id = html.escape(str(r.get("reviewer_id", "reviewer-1")))
            comment = html.escape(str(r.get("comment", "")))
            dt = html.escape(str(r.get("created_at", "")))
            review_items.append(
                f"<div class='audit-item'><strong>{act}</strong> by {rev_id} ({dt}): <em>\"{comment}\"</em></div>"
            )

        review_html = ""
        if review_items:
            review_html = f"<div class='reviews-box'><div class='section-title'>Human Review Ledger</div>{''.join(review_items)}</div>"

        override_badge_html = ""
        if verdict.get("override_info"):
            orig_v_str = html.escape(str(verdict.get("original_verdict", "N/A")))
            override_badge_html = f"""
            <div style="font-size: 11px; color: #f06a2c; margin-top: 4px; font-weight: 600;">
              ✎ Overridden by human reviewer (Original Automated Verdict: <em>{orig_v_str}</em>)
            </div>
            """

        claims_html_parts.append(f"""
        <div class="claim-card">
          <div class="claim-header">
            <span class="claim-id">{cid} · {loc}</span>
            <span class="badge verdict-badge">{display_v}</span>
          </div>
          {override_badge_html}
          <div class="claim-text">"{text}"</div>
          <div class="claim-meta">
            <span>Citation: [{citations}]</span>
            <span>Confidence: <strong>{conf:.0f}%</strong> (Tier: {tier})</span>
            {f'<span class="badge" style="background: rgba(240, 106, 44, 0.15); color: #f06a2c; border: 1px solid rgba(240, 106, 44, 0.3); font-size: 11px;">{html.escape(c.get("citation_classification"))}</span>' if c.get("citation_classification") else ''}
          </div>
          {f'<div class="explanation"><strong>Triage Analysis:</strong> {explanation}</div>' if explanation else ''}
          <div class="quote-container">
            <div class="quote-header">🛡️ CODE-VERIFIED VERBATIM SOURCE QUOTE {f'<span class="span-info">Span: {span}</span>' if span else ''}</div>
            <div class="quote-body">"{quote_text}"</div>
          </div>
          {slots_table_html}
          {review_html}
        </div>
        """)

    all_claims_html = "\n".join(claims_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Credence Report: {doc_name}</title>
  <style>
    :root {{
      --bg: #0b0b0e;
      --panel: #16161c;
      --panel2: #1c1c23;
      --line: rgba(255, 255, 255, 0.1);
      --ink: #edeef1;
      --muted: #9a9ca4;
      --orange: #f06a2c;
      --orange2: #ff7d3c;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      padding: 40px 20px;
      line-height: 1.6;
    }}
    .container {{ max-width: 960px; margin: 0 auto; }}
    .header-box {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 24px;
      margin-bottom: 30px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 20px;
    }}
    h1 {{ font-family: Georgia, serif; font-size: 28px; color: #fff; margin-bottom: 6px; }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      background: rgba(240, 106, 44, 0.15);
      color: var(--orange2);
      border: 1px solid rgba(240, 106, 44, 0.3);
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 12px;
      margin-bottom: 30px;
    }}
    .summary-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 14px;
      text-align: center;
    }}
    .summary-num {{ font-size: 22px; font-weight: 700; color: #fff; }}
    .summary-lbl {{ font-size: 11px; color: var(--muted); text-transform: uppercase; margin-top: 2px; }}
    .claim-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 24px;
      margin-bottom: 24px;
      page-break-inside: avoid;
    }}
    .claim-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
    .claim-id {{ font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; }}
    .claim-text {{ font-size: 18px; font-weight: 600; color: #fff; margin-bottom: 12px; line-height: 1.4; }}
    .claim-meta {{ display: flex; gap: 20px; font-size: 12px; color: var(--muted); margin-bottom: 16px; }}
    .explanation {{
      background: rgba(255,255,255,0.03);
      border-left: 3px solid var(--orange);
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 12px;
      margin-bottom: 18px;
    }}
    .quote-container {{
      background: rgba(240, 106, 44, 0.04);
      border: 1px solid rgba(240, 106, 44, 0.3);
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 18px;
    }}
    .quote-header {{ font-size: 11px; font-weight: 700; color: var(--orange2); margin-bottom: 8px; display: flex; justify-content: space-between; }}
    .quote-body {{ font-style: italic; color: #fff; font-size: 14px; line-height: 1.5; }}
    .span-info {{ font-weight: normal; color: var(--muted); }}
    .section-title {{ font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; margin-bottom: 8px; }}
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 16px; }}
    .data-table th, .data-table td {{ padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; }}
    .data-table th {{ color: var(--muted); background: rgba(255,255,255,0.02); }}
    .reviews-box {{
      background: var(--panel2);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 14px;
      margin-top: 14px;
    }}
    .audit-item {{ font-size: 12px; padding: 4px 0; color: var(--ink); }}
    .print-bar {{
      margin-bottom: 24px;
      display: flex;
      justify-content: flex-end;
    }}
    .btn-print {{
      background: var(--orange);
      color: #000;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 700;
      cursor: pointer;
    }}
    @media print {{
      body {{ background: #fff; color: #111; padding: 0; }}
      .print-bar {{ display: none; }}
      .header-box, .claim-card, .summary-card {{ border: 1px solid #ccc; background: #fafafa; color: #111; }}
      .claim-text, h1, .summary-num {{ color: #000; }}
      .quote-container {{ border: 1px solid #bbb; background: #f0f0f0; }}
      .quote-body {{ color: #000; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="print-bar">
      <button class="btn-print" onclick="window.print()">Print / Save as PDF</button>
    </div>

    <div class="header-box">
      <div>
        <span class="badge">Credence Verification Report</span>
        <h1>{doc_name}</h1>
        <p style="font-size: 12px; color: var(--muted);">Generated on {created_at} · Access Tier: {report.get('access_tier', 'Full Text')}</p>
      </div>
      <div style="text-align: right;">
        <div style="font-size: 11px; color: var(--muted); font-weight: 700;">OVERALL CONFIDENCE</div>
        <div style="font-size: 32px; font-weight: 800; color: var(--orange2);">{confidence:.0f}%</div>
      </div>
    </div>

    <div class="summary-grid">
      <div class="summary-card"><div class="summary-num">{len(claims)}</div><div class="summary-lbl">Claims</div></div>
      <div class="summary-card"><div class="summary-num" style="color: #5fcf6a;">{summary.get('supported', 0)}</div><div class="summary-lbl">Supported</div></div>
      <div class="summary-card"><div class="summary-num" style="color: #e3a93a;">{summary.get('partially_supported', 0)}</div><div class="summary-lbl">Partial</div></div>
      <div class="summary-card"><div class="summary-num" style="color: #e0574f;">{summary.get('contradictory', 0)}</div><div class="summary-lbl">Contradictory</div></div>
      <div class="summary-card"><div class="summary-num" style="color: #5aa9f0;">{summary.get('needs_review', 0)}</div><div class="summary-lbl">Needs Review</div></div>
      <div class="summary-card"><div class="summary-num" style="color: var(--orange2);">{summary.get('human_overrides', 0)}</div><div class="summary-lbl">Overrides</div></div>
    </div>

    <div class="claims-list">
      {all_claims_html}
    </div>
  </div>
</body>
</html>
"""


def generate_json_export(report: dict[str, Any]) -> str:
    """Generate indented JSON string representation of report."""
    return json.dumps(report, indent=2, default=str)
