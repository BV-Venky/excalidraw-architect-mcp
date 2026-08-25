"""Render every diagram type, for the README showcase or for local review.

    python scripts/generate_showcase.py                     # SVG -> showcase/gallery
    python scripts/generate_showcase.py --png                # also rasterise (macOS)
    python scripts/generate_showcase.py --out tmp/gallery --index
                                                            # local review page

**Why rasterise at all?** The SVG names a handwriting font stack but cannot
ship one -- Excalidraw's Excalifont is theirs to distribute, and the system
faces we fall back to (Bradley Hand, Segoe Print) are not redistributable
either. So an SVG in the README renders with whatever the *reader* happens to
have installed, which for a showcase means every visitor sees something
different. Rasterising once bakes the font in.

PNG rasterisation uses ``qlmanage``, the WebKit-backed thumbnailer built into
macOS -- no extra dependency. It only emits square thumbnails, so the SVG is
padded to a square first and the result cropped back with ``sips``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from typed_samples import SAMPLES  # noqa: E402

from excalidraw_mcp.core.models import (  # noqa: E402
    DiagramGraph,
    Direction,
    Edge,
    EdgeStyle,
    Node,
    ShapeType,
)
from excalidraw_mcp.diagrams.registry import build_typed_diagram  # noqa: E402
from excalidraw_mcp.engine.layout import compute_layout  # noqa: E402
from excalidraw_mcp.engine.renderer import build_excalidraw_file, save_excalidraw  # noqa: E402
from excalidraw_mcp.export.svg_exporter import export_to_svg  # noqa: E402

OUT_DIR = ROOT / "showcase" / "gallery"
RASTER_SIZE = 1400  # long edge, before cropping

# The two graph types take nodes/connections rather than a spec, so they are
# not in typed_samples. The showcase should still cover them.
GRAPH_SAMPLES: dict[str, DiagramGraph] = {
    "architecture": DiagramGraph(
        nodes=[
            Node(id="web", label="Web App", component_type="browser"),
            Node(id="cdn", label="Cloudflare", component_type="cloudflare"),
            Node(id="gw", label="API Gateway", component_type="nginx"),
            Node(id="auth", label="Auth Service"),
            Node(id="orders", label="Order Service"),
            Node(id="pg", label="PostgreSQL", component_type="postgresql"),
            Node(id="redis", label="Redis", component_type="redis"),
            Node(id="kafka", label="Kafka", component_type="kafka"),
            Node(id="workers", label="Fulfilment Worker"),
        ],
        edges=[
            Edge(from_id="web", to_id="cdn"),
            Edge(from_id="cdn", to_id="gw"),
            Edge(from_id="gw", to_id="auth", label="verify JWT"),
            Edge(from_id="gw", to_id="orders", label="REST"),
            Edge(from_id="auth", to_id="redis", label="sessions"),
            Edge(from_id="orders", to_id="pg"),
            Edge(from_id="orders", to_id="kafka", label="order.placed", style=EdgeStyle.DASHED),
            Edge(from_id="kafka", to_id="workers", style=EdgeStyle.DASHED),
            Edge(from_id="workers", to_id="pg"),
        ],
        direction=Direction.LEFT_RIGHT,
    ),
    "flowchart": DiagramGraph(
        nodes=[
            Node(id="push", label="Push to main", shape=ShapeType.STADIUM),
            Node(id="tests", label="Tests pass?", shape=ShapeType.DIAMOND),
            Node(id="build", label="Build image"),
            Node(id="canary", label="Deploy canary"),
            Node(id="healthy", label="Error rate OK?", shape=ShapeType.DIAMOND),
            Node(id="rollout", label="Full rollout"),
            Node(id="rollback", label="Auto-rollback"),
            Node(id="notify", label="Page on-call", shape=ShapeType.STADIUM),
        ],
        edges=[
            Edge(from_id="push", to_id="tests"),
            Edge(from_id="tests", to_id="build", label="yes"),
            Edge(from_id="tests", to_id="notify", label="no"),
            Edge(from_id="build", to_id="canary"),
            Edge(from_id="canary", to_id="healthy"),
            Edge(from_id="healthy", to_id="rollout", label="yes"),
            Edge(from_id="healthy", to_id="rollback", label="no"),
            Edge(from_id="rollback", to_id="notify"),
        ],
        direction=Direction.TOP_DOWN,
    ),
}


def _svg_size(svg: str) -> tuple[float, float]:
    match = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    if not match:
        raise ValueError("SVG has no viewBox")
    return float(match.group(1)), float(match.group(2))


def rasterize(svg_path: Path, png_path: Path) -> bool:
    """SVG -> PNG via macOS WebKit. Returns False if the tooling is absent."""
    if not (shutil.which("qlmanage") and shutil.which("sips")):
        return False

    svg = svg_path.read_text(encoding="utf-8")
    width, height = _svg_size(svg)
    side = max(width, height)
    dx, dy = (side - width) / 2, (side - height) / 2

    body = svg.split(">", 1)[1].rsplit("</svg>", 1)[0]
    padded = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{side}" height="{side}" '
        f'viewBox="0 0 {side} {side}">'
        f'<rect width="{side}" height="{side}" fill="#ffffff"/>'
        f'<g transform="translate({dx},{dy})">{body}</g></svg>'
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        square = tmp_dir / f"{svg_path.stem}.svg"
        square.write_text(padded, encoding="utf-8")

        subprocess.run(
            ["qlmanage", "-t", "-s", str(RASTER_SIZE), "-o", str(tmp_dir), str(square)],
            capture_output=True,
            check=False,
        )
        produced = tmp_dir / f"{square.name}.png"
        if not produced.is_file():
            return False

        # Crop the square thumbnail back to the diagram's real aspect ratio.
        scale = RASTER_SIZE / side
        crop_w = max(1, round(width * scale))
        crop_h = max(1, round(height * scale))
        png_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["sips", "-c", str(crop_h), str(crop_w), str(produced), "--out", str(png_path)],
            capture_output=True,
            check=False,
        )
        return png_path.is_file()


def write_index(out_dir: Path, names: list[str], ext: str) -> None:
    """A scrollable contact sheet, for eyeballing every type after a change."""
    cards = "\n".join(
        f"""    <figure>
      <figcaption>{name}</figcaption>
      <img src="{name}.{ext}" alt="{name} diagram">
      <a href="{name}.excalidraw" download>{name}.excalidraw</a>
    </figure>"""
        for name in names
    )
    out_dir.joinpath("index.html").write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Diagram gallery</title>
<style>
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 0; padding: 32px;
         background: #fafafa; color: #1e1e1e; }}
  h1 {{ font-size: 22px; margin: 0 0 24px; }}
  .grid {{ display: grid; gap: 24px;
           grid-template-columns: repeat(auto-fill, minmax(440px, 1fr)); }}
  figure {{ margin: 0; background: #fff; border: 1px solid #e5e5e5;
            border-radius: 10px; padding: 16px; }}
  figcaption {{ font-weight: 600; margin-bottom: 12px; }}
  img {{ width: 100%; height: auto; display: block; }}
  a {{ display: inline-block; margin-top: 10px; font-size: 12px; color: #666; }}
</style></head>
<body>
  <h1>Diagram gallery — {len(names)} types</h1>
  <div class="grid">
{cards}
  </div>
</body></html>""",
        encoding="utf-8",
    )


def main() -> int:
    argv = sys.argv[1:]
    want_png = "--png" in argv
    want_index = "--index" in argv
    out_dir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else OUT_DIR
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered: list[str] = []
    failed: list[str] = []
    rasterized = 0

    for name in sorted(GRAPH_SAMPLES) + sorted(SAMPLES):
        try:
            if name in GRAPH_SAMPLES:
                graph = GRAPH_SAMPLES[name]
                doc = build_excalidraw_file(compute_layout(graph), direction=graph.direction)
            else:
                doc, _ = build_typed_diagram(name, SAMPLES[name])
            excal = save_excalidraw(doc, out_dir / f"{name}.excalidraw")
            svg = export_to_svg(excal, out_dir / f"{name}.svg")
            rendered.append(name)
            note = ""
            if want_png and rasterize(svg, out_dir / f"{name}.png"):
                rasterized += 1
                note = " + png"
            print(f"  ok   {name}{note}")
        except Exception as exc:  # noqa: BLE001 - report all, never stop early
            failed.append(name)
            print(f"  FAIL {name}: {exc}")

    if want_index and rendered:
        # Prefer PNG in the contact sheet only if every diagram rasterised,
        # otherwise the page would silently mix stale and fresh images.
        write_index(out_dir, rendered, "png" if rasterized == len(rendered) else "svg")
        print(f"  index -> {out_dir / 'index.html'}")

    print(f"\n{len(rendered)} rendered, {rasterized} rasterised, {len(failed)} failed -> {out_dir}")
    if want_png and rasterized < len(rendered):
        print("  (PNG needs macOS qlmanage + sips; SVGs were still written)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
