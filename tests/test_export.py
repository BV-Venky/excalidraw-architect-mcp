"""Tests for the SVG/PNG export functionality."""

from __future__ import annotations

import json

import pytest

from excalidraw_mcp.export.svg_exporter import excalidraw_to_svg, export_to_svg


def _minimal_doc(**overrides):
    doc = {
        "type": "excalidraw",
        "version": 2,
        "elements": [],
        "appState": {"viewBackgroundColor": "#ffffff"},
        "files": {},
    }
    doc.update(overrides)
    return doc


def _rect(x=100, y=100, w=160, h=60, **kw):
    el = {
        "id": "r1",
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "#eaf0ff",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "opacity": 100,
        "isDeleted": False,
        "roughness": 1,
        "fillStyle": "solid",
        "roundness": {"type": 3},
    }
    el.update(kw)
    return el


def _text(x=110, y=118, text="Hello"):
    return {
        "id": "t1",
        "type": "text",
        "x": x,
        "y": y,
        "width": 80,
        "height": 20,
        "text": text,
        "fontSize": 16,
        "fontFamily": 1,
        "textAlign": "center",
        "strokeColor": "#1e1e1e",
        "opacity": 100,
        "isDeleted": False,
    }


def _arrow(x1=260, y1=130, dx=80):
    return {
        "id": "a1",
        "type": "arrow",
        "x": x1,
        "y": y1,
        "width": dx,
        "height": 1,
        "points": [[0, 0], [dx, 0]],
        "strokeColor": "#555555",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "opacity": 100,
        "isDeleted": False,
        "endArrowhead": "arrow",
    }


class TestExcalidrawToSvg:
    def test_empty_document_returns_placeholder(self):
        svg = excalidraw_to_svg(_minimal_doc())
        assert "<svg" in svg
        assert "400" in svg  # placeholder width

    def test_rectangle_rendered(self):
        doc = _minimal_doc(elements=[_rect()])
        svg = excalidraw_to_svg(doc)
        assert "<rect" in svg
        assert "#eaf0ff" in svg

    def test_ellipse_rendered(self):
        el = {**_rect(), "type": "ellipse", "id": "e1"}
        svg = excalidraw_to_svg(_minimal_doc(elements=[el]))
        # Sketchy shapes are <path> curves, never a geometrically exact
        # <ellipse> -- that primitive cannot be hand-drawn.
        assert "<ellipse" not in svg
        assert "<path" in svg
        assert " C " in svg

    def test_diamond_rendered(self):
        el = {**_rect(), "type": "diamond", "id": "d1"}
        svg = excalidraw_to_svg(_minimal_doc(elements=[el]))
        assert "<polygon" not in svg
        assert "<path" in svg

    def test_text_rendered(self):
        svg = excalidraw_to_svg(_minimal_doc(elements=[_text(text="PostgreSQL")]))
        assert "<text" in svg
        assert "PostgreSQL" in svg

    def test_multiline_text(self):
        svg = excalidraw_to_svg(_minimal_doc(elements=[_text(text="line1\nline2")]))
        assert svg.count("<tspan") == 2

    def test_edge_label_gets_masking_background(self):
        """A text bound to an arrow gets a canvas-colored backing rect so the
        line doesn't run through the label."""
        arrow = _arrow()
        label = {**_text(text="REST"), "id": "lbl", "containerId": arrow["id"]}
        doc = _minimal_doc(
            elements=[arrow, label],
            appState={"viewBackgroundColor": "#fafafa"},
        )
        svg = excalidraw_to_svg(doc)
        # backing rect in the canvas color appears for the edge label
        assert 'rx="3" fill="#fafafa"' in svg

    def test_plain_text_has_no_masking_background(self):
        """A standalone text (or a label bound to a shape) is not masked."""
        # bound to a rectangle, not an arrow -> no mask
        label = {**_text(text="Node"), "id": "lbl", "containerId": "r1"}
        doc = _minimal_doc(elements=[_rect(), label])
        svg = excalidraw_to_svg(doc)
        assert 'rx="3" fill="#ffffff"' not in svg

    def test_arrow_with_arrowhead(self):
        svg = excalidraw_to_svg(_minimal_doc(elements=[_arrow()]))
        assert "<path" in svg
        # Excalidraw draws a two-stroke V, not a filled marker triangle. A
        # marker is the most obvious tell that something else rendered it.
        assert "<marker" not in svg
        assert "#555555" in svg
        # Shaft plus two head legs, all as paths.
        assert svg.count("<path") >= 2

    def test_dashed_stroke(self):
        el = _rect(strokeStyle="dashed")
        svg = excalidraw_to_svg(_minimal_doc(elements=[el]))
        assert "stroke-dasharray" in svg

    def test_dotted_stroke(self):
        el = _rect(strokeStyle="dotted")
        svg = excalidraw_to_svg(_minimal_doc(elements=[el]))
        assert "stroke-dasharray" in svg

    def test_deleted_elements_skipped(self):
        el = {**_rect(), "isDeleted": True}
        svg = excalidraw_to_svg(_minimal_doc(elements=[el]))
        assert "<rect" not in svg or "400" in svg  # only placeholder rect

    def test_background_color_applied(self):
        doc = _minimal_doc(
            elements=[_rect()],
            appState={"viewBackgroundColor": "#1e1e1e"},
        )
        svg = excalidraw_to_svg(doc)
        assert "#1e1e1e" in svg

    def test_padding_adds_space(self):
        doc = _minimal_doc(elements=[_rect(x=0, y=0, w=100, h=50)])
        svg = excalidraw_to_svg(doc)
        # viewBox width should be 100 + 2*40 = 180
        assert "180.00" in svg

    def test_valid_svg_structure(self):
        doc = _minimal_doc(elements=[_rect(), _text(), _arrow()])
        svg = excalidraw_to_svg(doc)
        assert svg.startswith("<svg")
        assert svg.strip().endswith("</svg>")


class TestExportToSvgFile:
    def test_writes_svg_file(self, tmp_path):
        doc = _minimal_doc(elements=[_rect(), _text(text="DB")])
        src = tmp_path / "test.excalidraw"
        src.write_text(json.dumps(doc), encoding="utf-8")

        out = export_to_svg(src, tmp_path / "test.svg")
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "DB" in content

    def test_creates_parent_directories(self, tmp_path):
        doc = _minimal_doc(elements=[_rect()])
        src = tmp_path / "diag.excalidraw"
        src.write_text(json.dumps(doc), encoding="utf-8")

        out = export_to_svg(src, tmp_path / "subdir" / "nested" / "out.svg")
        assert out.exists()

    def test_png_raises_without_cairosvg(self, tmp_path):
        pytest.importorskip("cairosvg", reason="cairosvg not installed — skipping PNG test")
        from excalidraw_mcp.export.svg_exporter import export_to_png

        doc = _minimal_doc(elements=[_rect()])
        src = tmp_path / "test.excalidraw"
        src.write_text(json.dumps(doc), encoding="utf-8")

        out = export_to_png(src, tmp_path / "test.png")
        assert out.exists()
        assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


class TestSketchRenderer:
    """The roughjs port: seeded jitter, doubled strokes, crisp chrome."""

    def test_same_seed_gives_identical_output(self):
        a = excalidraw_to_svg(_minimal_doc(elements=[_rect(seed=12345)]))
        b = excalidraw_to_svg(_minimal_doc(elements=[_rect(seed=12345)]))
        assert a == b, "export must be reproducible for a given seed"

    def test_different_seed_gives_different_strokes(self):
        a = excalidraw_to_svg(_minimal_doc(elements=[_rect(seed=1)]))
        b = excalidraw_to_svg(_minimal_doc(elements=[_rect(seed=999)]))
        assert a != b, "seed must drive the jitter"

    def test_roughness_zero_is_crisp(self):
        """Chrome must not wobble: a 1px jittered hairline reads as noise."""
        from excalidraw_mcp.export import sketch

        o = sketch.Rough(roughness=0)
        rng = sketch.Rng(42)
        d = sketch.linear_path([(0, 0), (100, 0)], False, o, rng)
        # With zero roughness every offset collapses to 0, so both passes land
        # exactly on the requested geometry.
        assert "0.00 0.00" in d
        assert "100.00 0.00" in d

    def test_roughness_one_perturbs_geometry(self):
        from excalidraw_mcp.export import sketch

        o = sketch.Rough(roughness=1)
        rng = sketch.Rng(42)
        d = sketch.linear_path([(0, 0), (100, 0)], False, o, rng)
        assert d.count("M ") == 2, "a solid stroke is drawn twice"
        assert "0.00 0.00 C" not in d, "the start point should be nudged"

    def test_non_solid_stroke_is_single_pass(self):
        """Two jittered dashed passes read as a smudge, so Excalidraw uses one."""
        from excalidraw_mcp.export import sketch

        rng = sketch.Rng(7)
        solid = sketch.linear_path(
            [(0, 0), (100, 0)], False, sketch.Rough(disable_multi_stroke=False), rng
        )
        rng = sketch.Rng(7)
        dashed = sketch.linear_path(
            [(0, 0), (100, 0)], False, sketch.Rough(disable_multi_stroke=True), rng
        )
        assert solid.count("M ") == 2
        assert dashed.count("M ") == 1

    def test_dashed_element_thickens_and_keeps_dasharray(self):
        svg = excalidraw_to_svg(_minimal_doc(elements=[_rect(strokeStyle="dashed")]))
        assert "stroke-dasharray" in svg
        assert 'stroke-width="2.5"' in svg, "non-solid strokes gain 0.5"

    def test_fill_and_stroke_are_separate_paths(self):
        """The fill sits slightly inside the outline -- crayon, not vector."""
        svg = excalidraw_to_svg(_minimal_doc(elements=[_rect(backgroundColor="#eaf0ff")]))
        assert 'fill="#eaf0ff"' in svg
        assert 'stroke="none"' in svg
        assert svg.count("<path") >= 2

    def test_transparent_background_emits_no_fill_path(self):
        svg = excalidraw_to_svg(
            _minimal_doc(elements=[_rect(backgroundColor="transparent")])
        )
        assert 'stroke="none"' not in svg

    def test_prng_matches_javascript_semantics(self):
        """Park-Miller via Math.imul; drift here changes every export."""
        from excalidraw_mcp.export import sketch

        rng = sketch.Rng(1)
        values = [rng.next() for _ in range(3)]
        assert all(0.0 <= v < 1.0 for v in values)
        assert len(set(values)) == 3
        # Reproducible from the same seed.
        assert [sketch.Rng(1).next()] == [values[0]]

    def test_handwriting_font_stack_not_generic_cursive(self):
        """Generic `cursive` resolves to Apple Chancery on macOS -- calligraphy,
        not handwriting. Real faces must be named first."""
        svg = excalidraw_to_svg(_minimal_doc(elements=[_text(text="Orders")]))
        assert "Excalifont" in svg
        assert "Bradley Hand" in svg
        assert 'font-family="cursive"' not in svg

    def test_embedded_font_is_inlined(self, tmp_path):
        font = tmp_path / "fake.woff2"
        font.write_bytes(b"not-a-real-font")
        svg = excalidraw_to_svg(
            _minimal_doc(elements=[_text(text="Orders")]), embed_font=font
        )
        assert "@font-face" in svg
        assert "data:font/woff2;base64," in svg

    def test_missing_embed_font_is_ignored(self, tmp_path):
        svg = excalidraw_to_svg(
            _minimal_doc(elements=[_text(text="x")]), embed_font=tmp_path / "nope.ttf"
        )
        assert "@font-face" not in svg

    def test_closed_poly_fills_and_closes(self):
        el = {
            "id": "p1",
            "type": "line",
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 80,
            "points": [[0, 0], [100, 0], [50, 80]],
            "polygon": True,
            "strokeColor": "#1e1e1e",
            "backgroundColor": "#ffd8a8",
            "strokeWidth": 2,
            "strokeStyle": "solid",
            "opacity": 100,
            "roughness": 1,
            "seed": 5,
            "isDeleted": False,
        }
        svg = excalidraw_to_svg(_minimal_doc(elements=[el]))
        assert 'fill="#ffd8a8"' in svg
        assert " Z" in svg
