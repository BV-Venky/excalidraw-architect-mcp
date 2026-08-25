# Release Process

Internal guide for publishing a new version of `excalidraw-architect-mcp`.

## Pre-release Checklist

- [ ] All PRs for this release are merged to `main`
- [ ] CI is green on `main` (lint + tests across Python 3.10–3.13)
- [ ] README is updated with any new features, tools, or config changes

## Steps

### 1. Decide the version number

Follow [semver](https://semver.org/):

| Change type | Bump | Example |
|---|---|---|
| New tool / breaking change | **minor** | `0.2.3` → `0.3.0` |
| Bug fix / docs only | **patch** | `0.3.0` → `0.3.1` |

### 2. Bump version in `pyproject.toml`

```bash
# Edit line 7: version = "X.Y.Z"
vim pyproject.toml
```

### 3. Commit and push

```bash
git add pyproject.toml
git commit -m "chore: bump version to vX.Y.Z"
git push origin main
```

### 4. Create and push the git tag

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

### 5. Create a GitHub Release

1. Go to https://github.com/BV-Venky/excalidraw-architect-mcp/releases/new
2. **Choose tag**: select `vX.Y.Z`
3. **Release title**: `vX.Y.Z`
4. Click **Generate release notes** (auto-populates from merged PRs)
5. Review and edit the notes if needed
6. Click **Publish release**

### 6. PyPI publish (automatic)

The `publish.yml` workflow triggers on `release → published` and will:

1. Build the package with `uv build`
2. Upload to PyPI via trusted publishing (OIDC — no tokens needed)

> **Note:** This uses the `pypi` GitHub environment with `id-token: write` permissions.

### 7. Verify

- [ ] [GitHub Actions](https://github.com/BV-Venky/excalidraw-architect-mcp/actions) — "Publish to PyPI" workflow is green
- [ ] [PyPI](https://pypi.org/project/excalidraw-architect-mcp/) — new version is listed
- [ ] Quick smoke test:
  ```bash
  pip install excalidraw-architect-mcp==X.Y.Z
  excalidraw-architect-mcp --help
  ```

## Rollback

If a broken version is published:

1. **Yank on PyPI** (hides from `pip install` but doesn't delete):
   ```bash
   pip install twine
   twine yank excalidraw-architect-mcp X.Y.Z
   ```
2. Fix the issue, bump to `X.Y.(Z+1)`, and release again.

## Past Releases

| Version | Date | Highlights |
|---|---|---|
| v0.3.0 | 2026-05-04 | `export_diagram` tool (SVG/PNG), Claude Code support, README refresh |
| v0.2.3 | — | Python 3.10 pydantic compatibility fix |
| v0.2.2 | — | LobeHub badges, README GIFs |
| v0.2.1 | — | Bug fixes |
| v0.2.0 | — | Initial public release |
