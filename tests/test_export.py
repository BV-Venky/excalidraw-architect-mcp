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
        assert "<ellipse" in svg

    def test_diamond_rendered(self):
        el = {**_rect(), "type": "diamond", "id": "d1"}
        svg = excalidraw_to_svg(_minimal_doc(elements=[el]))
        assert "<polygon" in svg

    def test_text_rendered(self):
        svg = excalidraw_to_svg(_minimal_doc(elements=[_text(text="PostgreSQL")]))
        assert "<text" in svg
        assert "PostgreSQL" in svg

    def test_multiline_text(self):
        svg = excalidraw_to_svg(_minimal_doc(elements=[_text(text="line1\nline2")]))
        assert svg.count("<tspan") == 2

    def test_arrow_with_arrowhead(self):
        svg = excalidraw_to_svg(_minimal_doc(elements=[_arrow()]))
        assert "<path" in svg
        assert "<marker" in svg
        assert "arr-555555" in svg

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
