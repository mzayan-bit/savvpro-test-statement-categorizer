# Verification record

Executed on **26 October 2026**, with final release verification beginning at approximately **17:51 PKT**. These are local observations, not claims about hosted CI or other machines.

## Executed results

| Check | Observed result |
|---|---|
| `python -m pytest backend/tests -q` | **100 passed**, one upstream Starlette HTTPX-adapter deprecation warning |
| `ruff check backend` | Passed |
| `ruff format --check backend` | 14 files already formatted |
| `npm run check` | TypeScript strict compilation passed |
| `npm run test` | **4 passed** |
| `npm run build` | Production build passed |
| `npm run test:e2e` | **6 passed**, including desktop/mobile and axe accessibility |
| `pip check` | No broken requirements |
| Clean `npm ci` dependency audit | 0 vulnerabilities reported |
| `git diff --check` | Passed |

The browser suite uses Chromium against a real FastAPI server and temporary SQLite database. It verifies import and review, saved corrections after refresh, reset, duplicate keep/exclude, actual file download, atomic invalid-import rejection, mobile layout, complete final review/export, and the last-unresolved-item regression. The accessibility scenario runs axe WCAG A/AA rules across five UI stages; no automated violations were reported. This is not a claim of complete assistive-technology certification.

## Clean-install rehearsal

A separate temporary source copy was created without `.git`, `.venv`, `node_modules`, compiled assets, application databases, or test caches. A **new virtual environment** installed the pinned Python requirements, and **`npm ci`** installed the lockfile. The production build, all 100 backend tests, Ruff checks, and formatting check succeeded in that copy. No private environment variables or external accounts were required. Strict TypeScript checks, all 4 frontend unit tests, and all 6 browser/accessibility tests also passed in that fresh copy. The browser suite launches and initializes its own fresh database.

Environment: macOS/ARM64, Python 3.14.4, Node 26.0.0, npm 11.12.1. The declared dependency metadata supports Python 3.12+. CI is configured for Python 3.12 and Node 22, but hosted CI has **not** run before publication; Windows/Linux were not manually verified here.

## Real browser inspection

Actual desktop (1440×1000) and mobile (390×844) captures are included:

- [Desktop workspace](desktop-overview.png)
- [Decision/review panel](desktop-review.png)
- [Mobile workspace](mobile-overview.png)

Captures use the bundled fictional consultant CSV; the desktop state includes an explicitly saved cafe correction. A browser-automation inspection confirmed no external network requests from the built application and no horizontal overflow at 390 px. Fonts are bundled local assets. A manual browser-automation correction succeeded against the running local server.

## 5,000-row smoke measurement

[`performance.json`](performance.json) records an actual bounded import of 5,000 generated synthetic rows / 173,624 bytes. One local TestClient import took **0.2453 seconds**, with all 5,000 rows present and reconciliation passing. The temporary database was isolated from the application data.

This measures one local in-process HTTP test request including parsing/classification/persistence. It is **not** an end-to-end browser benchmark, throughput guarantee, or production load test. The generator is available at `scripts/generate_statement.py`.

## Known limitations

- One non-failing upstream Starlette deprecation warning remains visible.
- CSV only, one two-decimal currency per statement, and a deliberately narrow merchant rule catalog.
- No tax deductibility claims, multi-user hosting, or cross-statement duplicate detection.
- No GitHub push/PR has been performed by the agent; explicit user approval is required.
