"""Render every stress case and check it for layout defects.

    python scripts/stress_test.py            # SVG + report
    python scripts/stress_test.py --png      # also rasterise (macOS)

Writes to ``tmp/stress-test/<diagram_type>/`` with an index page per type and
one at the top level.

Rendering 90 diagrams is only half the point. At that volume the eye misses
things, so each result is also checked against layout invariants that should
hold for *every* diagram: nothing off-canvas, no partially-overlapping shapes,
labels that fit their containers, no degenerate geometry. Findings are printed
grouped by check, so a systematic problem in one layout shows up as a cluster
rather than as ninety separate surprises.
"""

from __future__ import annotations

import html
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from stress_cases import STRESS_CASES  # noqa: E402

from excalidraw_mcp.core.models import (  # noqa: E402
    DiagramGraph,
    Edge,
    EdgeStyle,
    Node,
    ShapeType,
)
from excalidraw_mcp.diagrams.registry import build_typed_diagram  # noqa: E402
from excalidraw_mcp.engine.layout import compute_layout  # noqa: E402
from excalidraw_mcp.engine.renderer import (  # noqa: E402
    FONT_FAMILY,
    _measure_text,
    build_excalidraw_file,
    save_excalidraw,
)
from excalidraw_mcp.export.svg_exporter import export_to_svg  # noqa: E402

OUT_ROOT = ROOT / "tmp" / "stress-test"


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    case: str
    check: str
    detail: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, case: str, check: str, detail: str) -> None:
        self.findings.append(Finding(case, check, detail))


def _visible(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in doc.get("elements", []) if not e.get("isDeleted")]


def _extent(el: dict[str, Any]) -> tuple[float, float, float, float]:
    if el["type"] in ("arrow", "line"):
        xs = [el["x"] + p[0] for p in el.get("points", [[0, 0]])]
        ys = [el["y"] + p[1] for p in el.get("points", [[0, 0]])]
        return min(xs), min(ys), max(xs), max(ys)
    return el["x"], el["y"], el["x"] + el["width"], el["y"] + el["height"]


def check_on_canvas(case: str, doc: dict[str, Any], rep: Report) -> None:
    for el in _visible(doc):
        x0, y0, _, _ = _extent(el)
        if x0 < -1 or y0 < -1:
            rep.add(case, "off-canvas", f"{el['type']} at ({x0:.0f}, {y0:.0f})")
            return


def check_no_degenerate(case: str, doc: dict[str, Any], rep: Report) -> None:
    for el in _visible(doc):
        if el["type"] in ("arrow", "line"):
            pts = el.get("points", [])
            if len(pts) >= 2 and pts[0] == pts[-1] and len(pts) == 2:
                rep.add(case, "degenerate", f"{el['type']} has zero length")
                return
        elif el["type"] != "text" and (el["width"] < 1 or el["height"] < 1):
            rep.add(
                case,
                "degenerate",
                f"{el['type']} is {el['width']:.1f}x{el['height']:.1f}",
            )
            return


def check_label_fits(case: str, doc: dict[str, Any], rep: Report) -> None:
    """A bound label wider than its container will wrap or clip.

    Types with fixed-width boxes (lane steps, pipeline stages) are where long
    labels actually bite, so this is the check most likely to find real bugs.
    """
    by_id = {e["id"]: e for e in _visible(doc)}
    worst: tuple[float, str] | None = None
    for el in _visible(doc):
        if el["type"] != "text" or not el.get("containerId"):
            continue
        container = by_id.get(el["containerId"])
        if not container or container["type"] in ("arrow", "line"):
            continue
        text = el.get("text", "")
        widest_line = max(text.split("\n"), key=len) if text else ""
        needed, _ = _measure_text(widest_line, el.get("fontSize", 16), FONT_FAMILY)
        overflow = needed - (container["width"] - 10)
        if overflow > 0 and (worst is None or overflow > worst[0]):
            worst = (overflow, f'"{text[:34]}" overflows by {overflow:.0f}px')
    if worst:
        rep.add(case, "label-overflow", worst[1])


# Venn is the one type whose entire meaning is shapes half-overlapping.
OVERLAP_EXEMPT = {"venn"}


def _really_intersect(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Bounding boxes overlap -- but do the actual shapes?

    Only ellipses need the distinction: a rectangle can sit inside an
    ellipse's bounding square while clearing the curve entirely, which is
    exactly what happens where a loop's stations ring its hub.
    """
    ellipse, other = (a, b) if a["type"] == "ellipse" else (b, a)
    if ellipse["type"] != "ellipse":
        return True  # two rectilinear shapes: bbox overlap is real overlap

    rx, ry = ellipse["width"] / 2, ellipse["height"] / 2
    cx, cy = ellipse["x"] + rx, ellipse["y"] + ry
    if rx <= 0 or ry <= 0:
        return True

    if other["type"] == "ellipse":
        orx, ory = other["width"] / 2, other["height"] / 2
        ocx, ocy = other["x"] + orx, other["y"] + ory
        # Normalise into the first ellipse's unit space and compare radii.
        dx, dy = (ocx - cx) / rx, (ocy - cy) / ry
        return (dx * dx + dy * dy) ** 0.5 < 1 + max(orx / rx, ory / ry)

    # Closest point on the rectangle to the ellipse centre.
    ox0, oy0 = other["x"], other["y"]
    ox1, oy1 = ox0 + other["width"], oy0 + other["height"]
    nx = min(max(cx, ox0), ox1)
    ny = min(max(cy, oy0), oy1)
    dx, dy = (nx - cx) / rx, (ny - cy) / ry
    return dx * dx + dy * dy < 1.0


def check_no_partial_overlap(case: str, doc: dict[str, Any], rep: Report) -> None:
    """Shapes may nest (zones contain nodes) but must not half-overlap.

    Full containment is legitimate -- a lane band holds its steps. Two boxes
    that intersect without either containing the other is a layout failure,
    except in the one type built on intersection.
    """
    if case.split("/")[0] in OVERLAP_EXEMPT:
        return

    boxes = [
        e
        for e in _visible(doc)
        if e["type"] in ("rectangle", "ellipse", "diamond")
        and e["width"] > 24
        and e["height"] > 18
    ]
    for i, a in enumerate(boxes):
        ax0, ay0, ax1, ay1 = _extent(a)
        for b in boxes[i + 1 :]:
            bx0, by0, bx1, by1 = _extent(b)
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox <= 2 or oy <= 2:
                continue
            if not _really_intersect(a, b):
                # Bounding boxes touch but the shapes do not -- a rectangle
                # clipping the corner of an ellipse's bbox is not a collision.
                continue
            a_in_b = ax0 >= bx0 - 2 and ay0 >= by0 - 2 and ax1 <= bx1 + 2 and ay1 <= by1 + 2
            b_in_a = bx0 >= ax0 - 2 and by0 >= ay0 - 2 and bx1 <= ax1 + 2 and by1 <= ay1 + 2
            if not (a_in_b or b_in_a):
                rep.add(
                    case,
                    "partial-overlap",
                    f"{a['type']} and {b['type']} intersect by "
                    f"{ox:.0f}x{oy:.0f}px without nesting",
                )
                return


def check_canvas_sane(case: str, doc: dict[str, Any], rep: Report) -> None:
    els = _visible(doc)
    if not els:
        rep.add(case, "empty", "no elements")
        return
    xs = [v for e in els for v in (_extent(e)[0], _extent(e)[2])]
    ys = [v for e in els for v in (_extent(e)[1], _extent(e)[3])]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    if w > 6000 or h > 6000:
        rep.add(case, "oversized", f"canvas is {w:.0f}x{h:.0f}px")
    ratio = max(w, h) / max(min(w, h), 1)
    if ratio > 22:
        rep.add(case, "extreme-aspect", f"{w:.0f}x{h:.0f} (ratio {ratio:.0f}:1)")


CHECKS = (
    check_on_canvas,
    check_no_degenerate,
    check_label_fits,
    check_no_partial_overlap,
    check_canvas_sane,
)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def build_graph_doc(payload: dict[str, Any]) -> dict[str, Any]:
    graph = DiagramGraph(
        nodes=[
            Node(
                id=n["id"],
                label=n.get("label", n["id"]),
                shape=ShapeType(n["shape"]) if "shape" in n else ShapeType.RECTANGLE,
            )
            for n in payload["nodes"]
        ],
        edges=[
            Edge(
                from_id=c["from_id"],
                to_id=c["to_id"],
                label=c.get("label"),
                style=EdgeStyle(c["style"]) if "style" in c else EdgeStyle.SOLID,
            )
            for c in payload.get("connections", [])
        ],
    )
    return build_excalidraw_file(compute_layout(graph), direction=graph.direction)


def write_index(
    path: Path, title: str, entries: list[tuple[str, str, str]], up: str = ""
) -> None:
    """Write a contact sheet. Entries are (caption, link target, image src)."""
    cards = "\n".join(
        f'    <figure><figcaption>{html.escape(name)}</figcaption>'
        f'<a href="{href}"><img src="{img}" alt="{html.escape(name)}"></a></figure>'
        for name, href, img in entries
    )
    back = f'<p><a href="{up}">&larr; all types</a></p>' if up else ""
    path.write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;margin:0;padding:32px;background:#fafafa;color:#1e1e1e}}
 h1{{font-size:22px;margin:0 0 4px}}
 .grid{{display:grid;gap:24px;grid-template-columns:repeat(auto-fill,minmax(460px,1fr))}}
 figure{{margin:0;background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:16px}}
 figcaption{{font-weight:600;margin-bottom:10px}}
 img{{width:100%;height:auto;display:block}}
 a{{color:#555}}
</style></head><body>
<h1>{html.escape(title)}</h1>{back}
<div class="grid">
{cards}
</div></body></html>""",
        encoding="utf-8",
    )


def main() -> int:
    want_png = "--png" in sys.argv
    if OUT_ROOT.exists():
        for item in sorted(OUT_ROOT.rglob("*"), reverse=True):
            item.unlink() if item.is_file() else item.rmdir()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    rasterize = None
    if want_png:
        sys.path.insert(0, str(ROOT / "scripts"))
        from generate_showcase import rasterize as _r

        rasterize = _r

    report = Report()
    errors: list[tuple[str, str]] = []
    type_entries: list[tuple[str, str, str]] = []
    total = 0

    for diagram_type in sorted(STRESS_CASES):
        cases = STRESS_CASES[diagram_type]
        out_dir = OUT_ROOT / diagram_type
        out_dir.mkdir(parents=True, exist_ok=True)
        entries: list[tuple[str, str, str]] = []

        for slug, kind, payload in cases:
            case_id = f"{diagram_type}/{slug}"
            total += 1
            try:
                if kind == "graph":
                    doc = build_graph_doc(payload)
                else:
                    doc, _ = build_typed_diagram(diagram_type, payload)
                excal = save_excalidraw(doc, out_dir / f"{slug}.excalidraw")
                svg = export_to_svg(excal, out_dir / f"{slug}.svg")
                href = f"{slug}.svg"
                if rasterize and rasterize(svg, out_dir / f"{slug}.png"):
                    href = f"{slug}.png"
                entries.append((slug, href, href))
                for check in CHECKS:
                    check(case_id, doc, report)
            except Exception as exc:  # noqa: BLE001 - collect, never stop early
                errors.append((case_id, f"{type(exc).__name__}: {exc}"))
                print(f"  ERROR {case_id}: {exc}")

        if entries:
            write_index(
                out_dir / "index.html", f"{diagram_type} — {len(entries)} cases",
                entries, up="../index.html",
            )
            type_entries.append(
                (
                    f"{diagram_type} ({len(entries)})",
                    f"{diagram_type}/index.html",
                    f"{diagram_type}/{entries[0][2]}",
                )
            )
        print(f"  {diagram_type:16s} {len(entries)}/{len(cases)} rendered")

    write_index(OUT_ROOT / "index.html", f"Stress test — {total} diagrams", type_entries)

    print(f"\n{total - len(errors)}/{total} rendered -> {OUT_ROOT}/index.html")

    if errors:
        print(f"\n{len(errors)} RENDER FAILURES")
        for case, msg in errors:
            print(f"  {case}: {msg}")

    if report.findings:
        by_check: dict[str, list[Finding]] = {}
        for f in report.findings:
            by_check.setdefault(f.check, []).append(f)
        print(f"\n{len(report.findings)} layout findings:")
        for check in sorted(by_check):
            group = by_check[check]
            print(f"\n  [{check}] x{len(group)}")
            for f in group[:8]:
                print(f"    {f.case}: {f.detail}")
            if len(group) > 8:
                print(f"    ... and {len(group) - 8} more")
    else:
        print("\nNo layout findings.")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
