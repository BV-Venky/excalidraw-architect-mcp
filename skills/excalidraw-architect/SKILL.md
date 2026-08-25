---
name: excalidraw-architect
description: Choose and compose the right Excalidraw diagram - architecture, flowchart, sequence, state, ER, swimlane, process, timeline, quadrant, pyramid, venn, loop, gantt, bar, line, scatter, and more - using the excalidraw-architect-mcp server. Use whenever a reader would learn more from a picture than from prose, or when asked to draw, diagram, chart, or visualize a system, process, or dataset.
license: MIT
---

# Excalidraw Architect

The MCP server renders. This skill decides **what** to render and **how much**.

Picking the wrong diagram type is the most common way a diagram fails. A
cross-functional process drawn as a flowchart loses the handoffs that were the
entire point. A ranking drawn as a bar chart loses the ranking.

---

## 1. Before you draw

Ask: *would the reader learn more from this than from a well-written
paragraph or a three-column table?* If no, write the paragraph.

Don't draw for:

- A list of things → bullets or a table.
- A simple before/after → a two-column table.
- One shape → just write the sentence.

---

## 2. The two rules that carry most of the quality

**Density target: ~4/10.** Enough to be complete, not so dense it needs its
own legend. Above nine nodes it is usually two diagrams — draw an overview
and a detail. Two nodes that always travel together are one node.

**Accent is reserved.** Every spec accepts `"focal": true` on its elements.
Mark **one or two** — the thing you want looked at first. Marking five spends
the signal and leaves the reader with no entry point. Most elements should be
unmarked; that is what makes the marked one work.

A third, quieter rule: every connection should carry information. If the
relationship is already obvious from the layout, delete the line.

---

## 3. Picking a type

<!-- BEGIN:selection-table -->
| If you're showing… | Use | Not when |
|---|---|---|
| Components and the connections between them | `architecture` | (graph type — pass `nodes` + `connections`) |
| Decision logic with branches | `flowchart` | (graph type — pass `nodes` + `connections`) |
| Parent -> children: taxonomies, file hierarchies, decision breakdowns. | `tree` | Use org_chart for people or teams; use nested when containment is the point. |
| Human, team, or agent ownership: reporting lines, escalation, routing. | `org_chart` | Not for system components -- that is architecture. |
| States, transitions, and guards. Order lifecycles, retry machines, approval flows. | `state` | Not for time-ordered messages between actors -- that is sequence. |
| Hierarchy by containment or scope: bounded contexts, module trees, org scopes. | `nested` | Beyond three levels of nesting, split into an overview plus a detail diagram. |
| Stacked abstraction levels where each layer sits on the one below. | `layers` | If the layers exchange traffic in both directions, use architecture instead. |
| Multi-tier data storage with quality levels: bronze/silver/gold, raw/curated/serving. | `medallion` | Use data_flow when the emphasis is who does what rather than where data rests. |
| Entities, their fields, and relationships. Data models and schema documentation. | `er` | Above ~8 entities, split by bounded context. |
| End-to-end stack drawn inside one named boundary (a cluster, an account, a VPC). | `high_level` | Use architecture when the boundary is not the point. |
| Legacy landscape grouped by phase or department; the 'before' state. | `it_state` | Use architecture for a target-state design. |
| Cross-functional process where step ownership matters. Handoffs are the story. | `swimlane` | If every step has the same owner, use flowchart. |
| Multi-actor sequential workflow drawn as vertical actor columns with data handoffs. | `process` | Use swimlane for horizontal lanes and a wider flow. |
| A pipeline where each stage is tagged with the role that owns it. | `data_flow` | Use medallion when storage tiers, not roles, are the subject. |
| Integration topology of a platform: sources -> core -> consumers. | `dp_integration` | Use architecture when the core needs to be decomposed in detail. |
| Time-ordered messages between actors: API traces, protocols, incident replays. | `sequence` | Never draw a message arrow that points backwards in time; use state for lifecycles. |
| Events positioned in time along a single axis. Roadmaps, incident chronologies. | `timeline` | Use gantt when items have duration rather than a single instant. |
| Two-axis positioning and prioritization. Add quadrant_labels for a consultant 2x2. | `quadrant` | Use scatter when the axes carry real units rather than relative position. |
| Ranked hierarchy (mode='pyramid') or conversion drop-off (mode='funnel'). | `pyramid` | Use bar when the values matter more than the ranking. |
| Overlap between two or three sets, where the intersection is the insight. | `venn` | Four or more sets is unreadable -- use a table. |
| A reinforcing cycle; add a hub for shared state the stations write back to. | `loop` | Use process when the flow has a real beginning and end. |
| Tasks and phases with duration on a timeline. Shows overlap and parallel tracks. | `gantt` | Above ~12 tasks, collapse to a phase-level view. |
| Quantitative comparison across categories. Multiple series render as grouped bars. | `bar` | Use line when the x axis is continuous time. |
| Continuous trends over an ordered axis. Capped at 15 points per series. | `line` | Use bar for a handful of discrete categories. |
| Distribution and correlation between two continuous variables. | `scatter` | Use quadrant when position is relative judgement rather than measurement. |
<!-- END:selection-table -->

Rules of thumb:

- If a three-column table says the same thing, use the table.
- Combining two types? Pick the dominant axis. Don't hybridize grammars.
- Past the density budget? Split into overview + detail.

---

## 4. Calling the tools

```
list_diagram_types()            # the table above, from the server
get_diagram_schema("sequence")  # exact spec shape for one type
create_diagram(output_path="./x.excalidraw", diagram_type="sequence", spec={...})
```

`architecture` and `flowchart` are graph types and take `nodes` +
`connections` instead of a `spec`. Everything else takes `diagram_type` +
`spec`.

Every spec accepts optional `title` and `subtitle`.

**Editing.** Call `get_diagram_info(path)` to read the stored spec, then:

```
modify_diagram(path, [{"op": "update_spec", "patch": {"title": "New title"}}])
```

The patch is deep-merged. **Lists are replaced wholesale** — to change one
tier, send the whole `tiers` list.

**Exporting.** `export_diagram(path, "./x.svg")` for SVG; PNG needs the
optional `cairosvg` extra.

See [`references/types.md`](references/types.md) for the full spec shape and a
worked example of every type.

---

## 5. Anti-patterns

| Anti-pattern | Why it fails |
|---|---|
| Accent on five nodes | Destroys the signal it exists to carry. |
| A step drawn across two lanes | Pick one owner; ambiguity is the opposite of the point. |
| A sequence message pointing upward | Reverses time. Never correct. |
| Fifteen nodes in one diagram | Past the budget — split it. |
| A chart with 50 points | Sketchy strokes turn it into a seismograph. Downsample. |
| A table drawn as boxes | Excalidraw has no table primitive. Write the markdown table. |
| Generic labels ("Service A") | Name the real thing or delete the node. |

---

## 6. What the renderer already handles

Don't work around these — they are done for you:

- **Layout.** Never pass coordinates. The engine places and routes everything.
- **Chrome vs content.** Axes, gridlines, and lane dividers render crisp;
  shapes and data marks render hand-drawn. That contrast is deliberate.
- **Themes.** `default`, `dark`, `colorful`. Accent and series ramps adapt.
- **Bindings.** Arrows stay attached when a node is dragged in Excalidraw.
