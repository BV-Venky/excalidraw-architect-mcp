"""Regenerate the skill's generated sections from the diagram registry.

Guidance is authored once, in ``diagrams/registry.py``. The MCP tools serve it
directly; this script projects the same data into the companion skill so the
two can never disagree. ``test_skill_docs_are_in_sync`` fails the build if
someone edits the registry without re-running this.

    python scripts/sync_skill_docs.py           # write
    python scripts/sync_skill_docs.py --check   # exit 1 if stale
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from typed_samples import SAMPLES  # noqa: E402

from excalidraw_mcp.diagrams.registry import DIAGRAM_TYPES  # noqa: E402

SKILL_DIR = ROOT / "skills" / "excalidraw-architect"
SKILL_MD = SKILL_DIR / "SKILL.md"
TYPES_MD = SKILL_DIR / "references" / "types.md"

BEGIN = "<!-- BEGIN:selection-table -->"
END = "<!-- END:selection-table -->"

FAMILY_ORDER = ["structural", "flow", "geometric", "chart"]
FAMILY_TITLES = {
    "structural": "Structural — hierarchy, containment, entities",
    "flow": "Flow — work moving across actors and time",
    "geometric": "Geometric — position carries the meaning",
    "chart": "Charts — quantitative, drawn hand-sketched",
}


def selection_table() -> str:
    rows = [
        "| If you're showing… | Use | Not when |",
        "|---|---|---|",
        "| Components and the connections between them | `architecture` | "
        "(graph type — pass `nodes` + `connections`) |",
        "| Decision logic with branches | `flowchart` | "
        "(graph type — pass `nodes` + `connections`) |",
    ]
    for family in FAMILY_ORDER:
        for dt in DIAGRAM_TYPES.values():
            if dt.family == family:
                rows.append(f"| {dt.use_when} | `{dt.name}` | {dt.avoid_when} |")
    return "\n".join(rows)


def types_reference() -> str:
    out = [
        "# Diagram type reference",
        "",
        "Generated from the registry by `scripts/sync_skill_docs.py`. Do not",
        "edit by hand — edit `src/excalidraw_mcp/diagrams/registry.py` and the",
        "type's spec model, then re-run the script.",
        "",
        "Every spec also accepts `title` and `subtitle`. Mark one or two",
        "elements `\"focal\": true` — no more.",
        "",
    ]

    for family in FAMILY_ORDER:
        types = [dt for dt in DIAGRAM_TYPES.values() if dt.family == family]
        if not types:
            continue
        out += [f"## {FAMILY_TITLES[family]}", ""]

        for dt in types:
            schema = dt.spec.model_json_schema()
            required = set(schema.get("required", []))
            props = schema.get("properties", {})
            fields = [
                f"- `{name}`{'' if name in required else ' (optional)'}"
                for name in props
                if name not in ("title", "subtitle")
            ]
            example = json.dumps(SAMPLES[dt.name], indent=2)

            out += [
                f"### `{dt.name}`",
                "",
                f"**Use when:** {dt.use_when}",
                "",
                f"**Avoid when:** {dt.avoid_when}",
                "",
                "**Spec fields**",
                "",
                *fields,
                "",
                "**Example**",
                "",
                "```json",
                example,
                "```",
                "",
            ]
    return "\n".join(out)


def render() -> dict[Path, str]:
    skill = SKILL_MD.read_text(encoding="utf-8")
    head, _, rest = skill.partition(BEGIN)
    _, _, tail = rest.partition(END)
    return {
        SKILL_MD: f"{head}{BEGIN}\n{selection_table()}\n{END}{tail}",
        TYPES_MD: types_reference(),
    }


def main() -> int:
    check = "--check" in sys.argv
    stale: list[str] = []

    for path, content in render().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        if check:
            stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"  wrote {path.relative_to(ROOT)}")

    if stale:
        print("Stale skill docs: " + ", ".join(stale))
        print("Run: python scripts/sync_skill_docs.py")
        return 1
    print("Skill docs up to date." if check else "Skill docs synced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
