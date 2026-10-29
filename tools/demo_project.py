#!/usr/bin/env python3
"""Build a fictional project with the kit installed and every view populated.

    python3 tools/demo_project.py [dir]          default: ./acme-shop-demo
    cd acme-shop-demo && python3 .ai-sdlc/bin/sdlc.py view --serve

"Acme Shop" is invented: a small storefront with a backlog in every column, dated commits
with Agent and Model trailers, plans, reviews, an ADR, worklog entries, two real verify
runs (the latest with a failing typecheck), a dependency audit result, a Dockerfile and a
compose file, env templates, a project skill and MCP server, living specs with a pending
change, and two claimed items. It is what the README's screenshots are taken from, and the
fastest way to see what the kit does before installing it into real work.

The check commands are small Python scripts standing in for tsc, eslint and the tests, so
the demo needs nothing but Python and git. Standard library only.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def day(n, hour=10):
    """n days ago, at a working hour, as git and the records write it."""
    return (NOW - datetime.timedelta(days=n)).replace(hour=hour, minute=12)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def git(root, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Sam Rivera", GIT_AUTHOR_EMAIL="sam@acme.example",
               GIT_COMMITTER_NAME="Sam Rivera", GIT_COMMITTER_EMAIL="sam@acme.example")
    if when is not None:
        stamp = when.strftime("%Y-%m-%dT%H:%M:%S+0000")
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = stamp
    subprocess.run(["git", "-c", "commit.gpgsign=false"] + list(args), cwd=root, env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def commit(root, message, when, item=None, agent="claude", model="claude-opus-5-5", paths=("-A",)):
    git(root, "add", *paths)
    if item:
        message += "\n\nWork-Item: %s\nAgent: %s\nModel: %s" % (item, agent, model)
    git(root, "commit", "-q", "-m", message, when=when)


def sdlc(root, *args):
    return subprocess.run([sys.executable, os.path.join(root, ".ai-sdlc", "bin", "sdlc.py")] + list(args),
                          cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)


APP_FILES = {
    "package.json": json.dumps({
        "name": "acme-shop", "private": True, "scripts": {"dev": "next dev", "build": "next build", "test": "vitest run"},
        "dependencies": {"next": "15.0.3", "react": "19.0.0", "react-dom": "19.0.0", "@prisma/client": "5.22.0",
                         "stripe": "17.3.0", "zod": "3.23.8", "lodash": "4.17.20"},
        "devDependencies": {"typescript": "5.6.3", "vitest": "2.1.4", "eslint": "9.14.0", "prisma": "5.22.0"}}, indent=2) + "\n",
    "package-lock.json": "{\n  \"lockfileVersion\": 3\n}\n",
    "tsconfig.json": "{\n  \"compilerOptions\": { \"strict\": true }\n}\n",
    "prisma/schema.prisma": "datasource db {\n  provider = \"postgresql\"\n  url = env(\"DATABASE_URL\")\n}\n",
    "src/app/page.tsx": "export default function Home() { return <main>Acme Shop</main>; }\n",
    "src/lib/stripe.ts": "import Stripe from 'stripe';\nexport const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);\n"
                         "export const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;\n",
    "src/lib/db.ts": "export const url = process.env.DATABASE_URL;\nexport const replica = process.env.DATABASE_REPLICA_URL;\n",
    "src/lib/mail.ts": "export const from = process.env.MAIL_FROM;\nexport const key = process.env.RESEND_API_KEY;\n",
    "src/cart/cart.ts": "export function total(lines: { price: number; qty: number }[]) {\n"
                        "  return lines.reduce((s, l) => s + l.price * l.qty, 0);\n}\n",
    ".env.example": "DATABASE_URL=\nSTRIPE_SECRET_KEY=\nSTRIPE_WEBHOOK_SECRET=\nMAIL_FROM=\nSENTRY_DSN=\n",
    "Dockerfile": "FROM node:20-alpine AS deps\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci\n\n"
                  "FROM node:20-alpine AS run\nWORKDIR /app\nCOPY --from=deps /app/node_modules ./node_modules\nCOPY . .\n"
                  "RUN npm run build\nEXPOSE 3000\nCMD [\"npm\", \"start\"]\n",
    "docker-compose.yml": "services:\n  web:\n    build: .\n    ports:\n      - \"3000:3000\"\n    env_file:\n      - .env\n"
                          "    depends_on:\n      - db\n  db:\n    image: postgres\n    environment:\n"
                          "      POSTGRES_PASSWORD: devpassword\n    ports:\n      - \"5432:5432\"\n",
    ".github/workflows/ci.yml": "name: CI\non:\n  pull_request:\n  push:\n    branches: [main]\njobs:\n  test:\n"
                                "    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: npm ci\n      - run: npm test\n"
                                "  deploy:\n    needs: test\n    runs-on: ubuntu-latest\n    steps:\n      - run: npx vercel deploy --prod\n",
    "vercel.json": "{}\n",
    ".gitignore": "node_modules/\n.env\n.next/\n",
    # Stand-ins for tsc, eslint and vitest, so the demo runs anywhere Python does.
    "scripts/check.py": "import os, sys, time\nstage = sys.argv[1]\ntime.sleep(0.2)\n"
                        "if stage == 'typecheck' and os.path.exists('src/cart/discount.ts'):\n"
                        "    print('> tsc --noEmit')\n"
                        "    print(\"src/cart/discount.ts(14,9): error TS2322: Type 'string' is not assignable to type 'number'.\")\n"
                        "    print(\"src/cart/discount.ts(22,17): error TS2339: Property 'percent' does not exist on type 'Coupon'.\")\n"
                        "    print('Found 2 errors in the same file, starting at: src/cart/discount.ts:14')\n"
                        "    sys.exit(2)\n"
                        "print('> %s' % stage)\nprint('ok')\n",
}

BACKLOG = """# Backlog

## Now

| ID | Task | Tier | Owner role | Depends on | Status |
| --- | --- | --- | --- | --- | --- |
| ACME-4 | Coupon codes at checkout | 2 | software-engineer | ACME-2 | In progress |
| ACME-5 | Stripe webhook retries | 1 | software-engineer | ACME-2 | In review |

## Next

| ID | Task | Tier | Owner role | Depends on | Status |
| --- | --- | --- | --- | --- | --- |
| ACME-6 | Order confirmation email | 2 | software-engineer |  | Ready |
| ACME-7 | Product search | 2 | software-engineer |  | Ready |
| ACME-8 | Saved addresses | 2 | software-engineer |  | Ready |
| ACME-9 | Guest checkout | 2 | product-manager | ACME-4 | Ready |
| ACME-11 | Admin order export | 3 | software-engineer |  | Ready |

## Blocked

| ID | Task | Tier | Owner role | Depends on | Status | Who can unblock | Since |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ACME-10 | Tax calculation for EU | 1 | software-engineer |  | Blocked | Finance lead (rates sign-off) | %(d6)s |

## Parked

| ID | Task | Tier | Owner role | Depends on | Status | Waiting on whom | For what decision | Since |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACME-12 | Loyalty points | 2 | product-manager |  | Parked | Head of product | Points or discounts first? | %(d9)s |

## Later

| ID | Task | Tier | Owner role | Depends on | Status | Becomes relevant when |
| --- | --- | --- | --- | --- | --- | --- |
| ACME-13 | Multi-currency prices | 1 | architect |  | Deferred | A second market launches |

## Done

| ID | Task | Tier | Owner role | Depends on | Status | Completed |
| --- | --- | --- | --- | --- | --- | --- |
| ACME-1 | Product catalogue pages | 2 | software-engineer |  | Done | %(d12)s |
| ACME-2 | Cart and checkout with Stripe | 1 | software-engineer | ACME-1 | Done | %(d8)s |
| ACME-3 | Fix rounding in cart totals | 3 | software-engineer |  | Done | %(d7)s |
"""

WORKLOG = """# Worklog

Newest first.

## ACME-2 — Cart and checkout with Stripe

**Date:** %(d8)s
**Status:** Done

### What changed

Cart persisted per session; Stripe Checkout for payment; order rows written on the
`checkout.session.completed` webhook. Design and ship reviews passed (security by codex).

### Verified

`sdlc.py verify` on the merge commit: lint, typecheck, unit and build pass.

### Not done

None.

- %(d7)s · ACME-3 · Fix rounding in cart totals · line totals rounded before summing; failing test first

## ACME-1 — Product catalogue pages

**Date:** %(d12)s
**Status:** Done

### What changed

Listing and detail pages from Postgres via Prisma, statically generated.

### Not done

None.
"""


def plan(item, title, files, tier=2, spec=""):
    return """---
status: approved
owner: software-engineer
last-reviewed: %(today)s
---

# Plan — %(item)s %(title)s

**Tier:** %(tier)s **Effort:** Normal **Depends on:** none

## Problem

%(title)s is the next most requested change from customer support.

## Outcome

%(title)s works end to end and is covered by tests.

## Spec changes

%(spec)s

## Files that change

%(files)s

## Order of work

1. Failing test. 2. Implementation. 3. Verify.
""" % {"item": item, "title": title, "files": "\n".join("- `%s`" % f for f in files), "tier": tier,
       "today": NOW.date().isoformat(), "spec": spec or "none: no behaviour a customer can observe changes."}


SPEC = """---
status: approved
owner: product-manager
last-reviewed: %s
---

# Checkout

## Purpose

How a customer pays for a cart and what they are told afterwards.

## Requirements

### Requirement: Card payment
The system SHALL take payment through Stripe Checkout and create the order only after Stripe confirms it.

#### Scenario: payment succeeds
- **WHEN** Stripe sends `checkout.session.completed`
- **THEN** the order is stored as paid and the cart is emptied

#### Scenario: payment abandoned
- **WHEN** the customer closes the Stripe page
- **THEN** no order is created and the cart is kept

### Requirement: Cart totals
The system SHALL compute totals from rounded line totals.

#### Scenario: fractional prices
- **WHEN** three items cost 0.333 each
- **THEN** the total is 0.99, not 1.00
"""

SPEC_CHANGE = """# Spec change — ACME-4 Coupon codes at checkout

Capability: `checkout`

## ADDED Requirements

### Requirement: Coupon codes
The system SHALL apply one valid coupon code per order and show the discount before payment.

#### Scenario: valid code
- **WHEN** the customer enters an active code
- **THEN** the discount appears on the order summary and is charged

#### Scenario: expired code
- **WHEN** the customer enters an expired code
- **THEN** the code is refused with the reason, and the total is unchanged

## MODIFIED Requirements

### Requirement: Cart totals
The system SHALL compute totals from rounded line totals, after any coupon discount.

#### Scenario: discount and rounding
- **WHEN** a 10% coupon applies to three items at 0.333
- **THEN** the total is 0.89
"""


def build(target):
    if os.path.exists(target) and os.listdir(target):
        raise SystemExit("%s exists and is not empty; pick another directory" % target)
    os.makedirs(target, exist_ok=True)
    d = os.path.abspath(target)
    subprocess.run(["git", "init", "-q", "-b", "main", d], check=True)
    for rel, text in APP_FILES.items():
        write(d, rel, text)
    commit(d, "chore: scaffold Next.js storefront", day(14, 9))

    inst = subprocess.run([sys.executable, os.path.join(KIT, "install.py"), d, "ACME", "-y", "--harness", "claude",
                           "--specs", "on", "--preset", "team"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    if inst.returncode:
        raise SystemExit("install failed:\n" + inst.stdout[-800:])
    for stage, cmd in (("lint", "python3 scripts/check.py lint"), ("typecheck", "python3 scripts/check.py typecheck"),
                       ("unit", "python3 scripts/check.py unit"), ("build", "python3 scripts/check.py build")):
        sdlc(d, "config", "--set-check", "%s=%s" % (stage, cmd))
    dates = dict(("d%d" % n, day(n).date().isoformat()) for n in range(0, 15))
    write(d, "docs/project/backlog.md", BACKLOG % dates)
    write(d, "docs/project/worklog.md", WORKLOG % dates)
    commit(d, "chore: install Nuhut and plan the first items", day(13, 11))

    # Delivered work, with trailers, on dates that make the flow chart move.
    write(d, "src/app/products/page.tsx", "export default function Products() { return null; }\n")
    commit(d, "feat(catalogue): listing and detail pages (ACME-1)", day(12), "ACME-1")
    write(d, "docs/project/plans/ACME-2.md", plan("ACME-2", "Cart and checkout with Stripe",
          ["src/cart/**", "src/lib/stripe.ts", "src/app/checkout/**"], tier=1))
    write(d, "docs/project/reviews/ACME-2-design.md", "---\nstatus: approved\nowner: architect\nlast-reviewed: %s\n---\n\n"
          "# Design review — ACME-2\n\nReviewer: codex / gpt-5 (independent)\nVerdict: Pass with conditions\n\n"
          "- Medium: create orders only from the webhook, never the redirect.\n" % dates["d11"])
    write(d, "docs/project/adr/0001-stripe-checkout.md", "---\nstatus: accepted\nowner: architect\nlast-reviewed: %s\n---\n\n"
          "# ADR 0001 — Stripe Checkout instead of a custom card form\n\nDecided for ACME-2: PCI scope stays with Stripe.\n" % dates["d11"])
    commit(d, "docs(ACME-2): plan, design review and ADR", day(11), "ACME-2", agent="claude")
    write(d, "src/app/checkout/page.tsx", "export default function Checkout() { return null; }\n")
    commit(d, "feat(checkout): Stripe Checkout session (ACME-2)", day(10), "ACME-2")
    write(d, "src/app/api/stripe/route.ts", "export async function POST() { return new Response('ok'); }\n")
    commit(d, "feat(checkout): webhook creates the order (ACME-2)", day(9), "ACME-2")
    sdlc(d, "verify")                                   # passing run on the delivered work
    write(d, "docs/project/reviews/ACME-2-ship.md", "---\nstatus: approved\nowner: security\nlast-reviewed: %s\n---\n\n"
          "# Ship review — ACME-2\n\nReviewer: codex / gpt-5 (independent)\nVerdict: Pass\n" % dates["d8"])
    commit(d, "docs(ACME-2): ship review", day(8), "ACME-2", agent="codex", model="gpt-5")
    write(d, "src/cart/cart.ts", APP_FILES["src/cart/cart.ts"].replace("l.price * l.qty", "Math.round(l.price * l.qty * 100) / 100"))
    commit(d, "fix(cart): round line totals before summing (ACME-3)", day(7), "ACME-3", agent="codex", model="gpt-5")

    # Work in flight.
    write(d, "docs/project/plans/ACME-4.md", plan("ACME-4", "Coupon codes at checkout",
          ["src/cart/discount.ts", "src/cart/cart.ts", "src/app/checkout/**"], spec="`project/specs/changes/ACME-4.md`"))
    write(d, "docs/project/specs/checkout.md", SPEC % dates["d8"])
    write(d, "docs/project/specs/changes/ACME-4.md", SPEC_CHANGE)
    commit(d, "docs(ACME-4): plan and spec change", day(4), "ACME-4")
    write(d, "src/cart/discount.ts", "export type Coupon = { code: string };\nexport const pct: number = '10';\n")
    commit(d, "feat(cart): coupon model, first pass (ACME-4)", day(2), "ACME-4")
    write(d, "docs/project/plans/ACME-5.md", plan("ACME-5", "Stripe webhook retries", ["src/app/api/stripe/**", "src/lib/stripe.ts"], tier=1))
    commit(d, "feat(stripe): idempotent webhook handling (ACME-5)", day(1), "ACME-5", agent="codex", model="gpt-5")
    sdlc(d, "verify")                                   # the latest run: typecheck fails on discount.ts

    # Ready work with plans, two of which collide on the same file.
    write(d, "docs/project/plans/ACME-6.md", plan("ACME-6", "Order confirmation email", ["src/lib/mail.ts", "src/emails/**"]))
    write(d, "docs/project/plans/ACME-7.md", plan("ACME-7", "Product search", ["src/app/search/**", "src/lib/search.ts"]))
    write(d, "docs/project/plans/ACME-8.md", plan("ACME-8", "Saved addresses", ["src/lib/mail.ts", "prisma/migrations/**"]))
    commit(d, "docs: plans for the next three items", day(0, 9))

    # Agent setup the lens reports on, plus a dependency audit result (as `sdlc.py audit`
    # would keep it; written here so the demo needs no network).
    write(d, ".claude/skills/acme-checkout/SKILL.md", "---\nname: acme-checkout\ndescription: Our Stripe and checkout rules. "
          "Use when touching payments, webhooks or order creation.\n---\n\nOrders come from the webhook only.\n")
    write(d, ".mcp.json", json.dumps({"mcpServers": {"stripe": {"type": "http", "url": "https://mcp.stripe.com"},
                                                     "postgres": {"command": "npx", "args": ["@modelcontextprotocol/server-postgres"]}}}, indent=2))
    commit(d, "chore: project skill and MCP servers", day(0, 10))
    audit_dir = os.path.join(d, ".ai-sdlc", "evidence", NOW.strftime("%Y%m%dT%H%M%SZ") + "-audit")
    os.makedirs(audit_dir, exist_ok=True)
    with open(os.path.join(audit_dir, "audit.json"), "w", encoding="utf-8") as handle:
        json.dump({"generated": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "command": "npm audit --json", "tool": "npm",
                   "exit_code": 1, "seconds": 2.1, "error": "",
                   "vulns": [{"package": "lodash", "version": "<4.17.21", "severity": "high", "id": "GHSA-35jh-r3h4-6jhm",
                              "title": "Command injection in lodash", "fix": "yes", "direct": True},
                             {"package": "cookie", "version": "<0.7.0", "severity": "low", "id": "GHSA-pxg6-pf52-xh8x",
                              "title": "cookie accepts out-of-bounds characters", "fix": "yes", "direct": False}]}, handle, indent=2)

    # Two agents holding items.
    sdlc(d, "claim", "ACME-4", "--agent", "claude", "--no-worktree")
    sdlc(d, "claim", "ACME-5", "--agent", "codex", "--no-worktree")
    return d


def main(argv):
    target = argv[0] if argv else "acme-shop-demo"
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    if not shutil.which("git"):
        raise SystemExit("git is required")
    d = build(target)
    print("Built a demo project in %s\n\n  cd %s\n  python3 .ai-sdlc/bin/sdlc.py view --serve\n\n"
          "Everything in it is fictional. Delete the folder when you are done." % (d, target))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
