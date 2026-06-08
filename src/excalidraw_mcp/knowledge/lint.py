"""Architecture health check over the knowledge graph.

Surfaces structural problems that are invisible in a static picture: orphaned
services, dependency cycles, single points of failure, dependencies pointing
at services that don't exist, and (optionally) unowned services.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from excalidraw_mcp.knowledge import query
from excalidraw_mcp.knowledge.models import KnowledgeGraph


class LintFinding(BaseModel):
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    services: list[str] = Field(default_factory=list)


class LintReport(BaseModel):
    findings: list[LintFinding] = Field(default_factory=list)

    @property
    def errors(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors and not self.warnings

    def to_text(self) -> str:
        if not self.findings:
            return "Architecture health: ✓ no issues found."
        symbol = {"error": "✗", "warning": "⚠", "info": "ℹ"}
        lines = ["Architecture health check:"]
        for f in self.findings:
            scope = f" [{', '.join(f.services)}]" if f.services else ""
            lines.append(f"  {symbol.get(f.severity, '-')} ({f.code}) {f.message}{scope}")
        n_err = len(self.errors)
        n_warn = len(self.warnings)
        lines.append("")
        lines.append(f"Summary: {n_err} error(s), {n_warn} warning(s).")
        return "\n".join(lines)


def lint(kg: KnowledgeGraph, *, check_owners: bool = False) -> LintReport:
    """Run all health checks and return a structured report."""
    findings: list[LintFinding] = []

    # Dangling dependencies — hard errors (broken references).
    for d in kg.dangling_dependencies():
        findings.append(
            LintFinding(
                severity="error",
                code="dangling-dependency",
                message=f"dependency {d.from_id} -> {d.to_id} references an unknown service",
                services=[d.from_id, d.to_id],
            )
        )

    # Dependency cycles.
    for cyc in query.cycles(kg):
        findings.append(
            LintFinding(
                severity="warning",
                code="cycle",
                message=f"dependency cycle among {len(cyc)} services",
                services=cyc,
            )
        )

    # Single points of failure.
    spofs = query.single_points_of_failure(kg)
    for sid in spofs:
        findings.append(
            LintFinding(
                severity="warning",
                code="single-point-of-failure",
                message=f"'{sid}' is a single point of failure (its removal partitions the graph)",
                services=[sid],
            )
        )

    # Orphans (only meaningful once there's more than one service).
    if len(kg.services) > 1:
        for sid in query.orphans(kg):
            findings.append(
                LintFinding(
                    severity="info",
                    code="orphan",
                    message=f"'{sid}' has no dependencies in either direction",
                    services=[sid],
                )
            )

    if check_owners:
        unowned = query.unowned_services(kg)
        if unowned:
            findings.append(
                LintFinding(
                    severity="info",
                    code="unowned",
                    message=f"{len(unowned)} service(s) have no owner",
                    services=unowned,
                )
            )

    return LintReport(findings=findings)
