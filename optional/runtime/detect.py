"""Stack detection: what a repository is built from, deployed to and tested with.

Shared by the installer (which turns it into the charter's facts and check commands) and
the runtime (which shows it live in the viewer's Project lens), so there is one detector
and it never goes stale. Read-only, standard library only, Python 3.8+.

This file must never contain two opening braces in a row (see sdlc.py).
"""

import json
import os
import re
from pathlib import Path

# ---------------------------------------------------------------- detection
# All read-only and best-effort. Anything not established stays empty: the process reads
# a blank cell as Unknown, which is recoverable, while a wrong check command produces
# confidently false "verified" claims, which is not.

LOCALE_DIRS = ("locales", "messages", "public/locales", "src/locales", "src/i18n",
               "i18n", "app/locales", "config/locales", "lang", "translations",
               "src/messages", "content/i18n")
LOCALE_RE = re.compile(r"^([a-z]{2,3})(?:[-_]([A-Za-z]{2,4}))?(\.(json|ya?ml|po|arb|ts|js|mjs))?$")

I18N_LIBS = (
    ("next-intl", "next-intl"), ("next-i18next", "next-i18next"),
    ("react-i18next", "react-i18next"), ("i18next", "i18next"),
    ("vue-i18n", "vue-i18n"), ("@nuxtjs/i18n", "@nuxtjs/i18n"),
    ("react-intl", "react-intl"), ("@formatjs/intl", "FormatJS"),
    ("svelte-i18n", "svelte-i18n"), ("@angular/localize", "@angular/localize"),
    ("@inlang/paraglide-js", "Paraglide"), ("astro-i18next", "astro-i18next"),
    ("gettext", "gettext"), ("intlayer", "intlayer"),
)

INTEGRATIONS = (
    ("stripe", "Stripe", "payments"),
    ("@stripe/stripe-js", "Stripe", "payments"),
    ("@supabase/supabase-js", "Supabase", "database, auth, storage"),
    ("@aws-sdk/client-s3", "AWS S3", "object storage"),
    ("@google-cloud/storage", "Google Cloud Storage", "object storage"),
    ("resend", "Resend", "transactional email"),
    ("@sendgrid/mail", "SendGrid", "transactional email"),
    ("nodemailer", "SMTP (nodemailer)", "transactional email"),
    ("openai", "OpenAI API", "model inference"),
    ("@anthropic-ai/sdk", "Anthropic API", "model inference"),
    ("twilio", "Twilio", "SMS / voice"),
    ("@sentry/nextjs", "Sentry", "error reporting"),
    ("@sentry/node", "Sentry", "error reporting"),
    ("@sentry/react", "Sentry", "error reporting"),
    ("posthog-js", "PostHog", "product analytics"),
    ("@vercel/analytics", "Vercel Analytics", "web analytics"),
    ("algoliasearch", "Algolia", "search"),
    ("meilisearch", "Meilisearch", "search"),
    ("ioredis", "Redis", "cache / queue"),
    ("bullmq", "BullMQ", "background jobs"),
    ("firebase", "Firebase", "backend services"),
    ("mapbox-gl", "Mapbox", "maps"),
    ("googleapis", "Google APIs", "integration"),
)

PY_INTEGRATIONS = (
    ("stripe", "Stripe", "payments"),
    ("boto3", "AWS", "cloud services"),
    ("sentry-sdk", "Sentry", "error reporting"),
    ("openai", "OpenAI API", "model inference"),
    ("anthropic", "Anthropic API", "model inference"),
    ("celery", "Celery", "background jobs"),
    ("redis", "Redis", "cache / queue"),
)

# Domain markers. Each family answers one question — does this repository do that
# kind of work? — and the answer becomes a project-type default, which becomes a
# fact, which decides roles and skills. Detection is evidence, never a declaration.
ML_NODE = (("langchain", "LangChain"), ("@langchain/core", "LangChain"),
           ("langgraph", "LangGraph"), ("llamaindex", "LlamaIndex"),
           ("ai", "Vercel AI SDK"), ("@ai-sdk/openai", "Vercel AI SDK"),
           ("@ai-sdk/anthropic", "Vercel AI SDK"), ("@ai-sdk/google", "Vercel AI SDK"),
           ("openai", "OpenAI API"), ("@anthropic-ai/sdk", "Anthropic API"),
           ("@google/genai", "Google Gemini SDK"), ("@google/generative-ai", "Google Gemini SDK"),
           ("ollama", "Ollama"), ("@huggingface/inference", "Hugging Face"),
           ("promptfoo", "promptfoo"), ("langfuse", "Langfuse"),
           ("braintrust", "Braintrust"), ("@mastra/core", "Mastra"))
ML_PY = (("langchain", "LangChain"), ("langgraph", "LangGraph"),
         ("llama-index", "LlamaIndex"), ("transformers", "Transformers"),
         ("torch", "PyTorch"), ("tensorflow", "TensorFlow"),
         ("scikit-learn", "scikit-learn"), ("xgboost", "XGBoost"),
         ("vllm", "vLLM"), ("litellm", "LiteLLM"), ("dspy-ai", "DSPy"),
         ("sentence-transformers", "sentence-transformers"),
         ("instructor", "Instructor"), ("haystack-ai", "Haystack"),
         ("ragas", "Ragas"), ("deepeval", "DeepEval"), ("promptfoo", "promptfoo"),
         ("mlflow", "MLflow"), ("wandb", "Weights & Biases"), ("dvc", "DVC"),
         ("bentoml", "BentoML"), ("kubeflow", "Kubeflow"), ("langfuse", "Langfuse"),
         ("google-genai", "Google Gemini SDK"), ("google-generativeai", "Google Gemini SDK"),
         ("anthropic", "Anthropic API"))
VECTOR_NODE = (("@pinecone-database/pinecone", "Pinecone"),
               ("weaviate-ts-client", "Weaviate"), ("weaviate-client", "Weaviate"),
               ("@qdrant/js-client-rest", "Qdrant"), ("chromadb", "Chroma"),
               ("@zilliz/milvus2-sdk-node", "Milvus"), ("@lancedb/lancedb", "LanceDB"))
VECTOR_PY = (("pinecone", "Pinecone"), ("pinecone-client", "Pinecone"),
             ("weaviate-client", "Weaviate"), ("qdrant-client", "Qdrant"),
             ("chromadb", "Chroma"), ("faiss-cpu", "FAISS"), ("faiss-gpu", "FAISS"),
             ("pymilvus", "Milvus"), ("lancedb", "LanceDB"), ("pgvector", "pgvector"))
DATA_NODE = (("@google-cloud/bigquery", "BigQuery"), ("snowflake-sdk", "Snowflake"),
             ("duckdb", "DuckDB"), ("@dbt-labs/dbt", "dbt"))
DATA_PY = (("apache-airflow", "Airflow"), ("dagster", "Dagster"), ("prefect", "Prefect"),
           ("luigi", "Luigi"), ("dbt-core", "dbt"), ("sqlmesh", "SQLMesh"),
           ("pyspark", "Spark"), ("apache-flink", "Flink"), ("apache-beam", "Beam"),
           ("duckdb", "DuckDB"), ("polars", "Polars"),
           ("great-expectations", "Great Expectations"), ("soda-core", "Soda"),
           ("pandera", "Pandera"), ("snowflake-connector-python", "Snowflake"),
           ("google-cloud-bigquery", "BigQuery"))
DATA_FILES = (("dbt_project.yml", "dbt"), ("dagster.yaml", "Dagster"),
              ("airflow.cfg", "Airflow"), ("dags", "Airflow DAGs"),
              ("dbt_project.yaml", "dbt"))
MSG_NODE = (("kafkajs", "Kafka"), ("kafka-node", "Kafka"), ("amqplib", "RabbitMQ"),
            ("nats", "NATS"), ("@aws-sdk/client-sqs", "SQS"),
            ("@google-cloud/pubsub", "Pub/Sub"), ("@temporalio/client", "Temporal"),
            ("bullmq", "BullMQ"), ("bull", "Bull"), ("agenda", "Agenda"))
MSG_PY = (("confluent-kafka", "Kafka"), ("kafka-python", "Kafka"), ("aiokafka", "Kafka"),
          ("pika", "RabbitMQ"), ("kombu", "RabbitMQ"), ("nats-py", "NATS"),
          ("celery", "Celery"), ("dramatiq", "Dramatiq"), ("rq", "RQ"),
          ("temporalio", "Temporal"), ("google-cloud-pubsub", "Pub/Sub"))
IAC_FILES = (("main.tf", "Terraform"), ("versions.tf", "Terraform"),
             (".terraform.lock.hcl", "Terraform"), ("terraform", "Terraform"),
             ("Pulumi.yaml", "Pulumi"), ("ansible.cfg", "Ansible"),
             ("playbooks", "Ansible"), ("Chart.yaml", "Helm"),
             ("kustomization.yaml", "Kustomize"), ("cdk.json", "AWS CDK"),
             ("serverless.yml", "Serverless Framework"),
             ("template.yaml", "AWS SAM / CloudFormation"), ("k8s", "Kubernetes manifests"),
             ("kubernetes", "Kubernetes manifests"), ("charts", "Helm"))
SCRAPE_NODE = (("crawlee", "Crawlee"), ("cheerio", "cheerio"), ("apify", "Apify"),
               ("got-scraping", "got-scraping"))
SCRAPE_PY = (("scrapy", "Scrapy"), ("beautifulsoup4", "BeautifulSoup"),
             ("selectolax", "selectolax"), ("feedparser", "feedparser"),
             ("apify", "Apify"), ("crawlee", "Crawlee"))
LOAD_NODE = (("k6", "k6"), ("artillery", "Artillery"), ("autocannon", "autocannon"),
             ("@types/k6", "k6"), ("lighthouse", "Lighthouse"))
LOAD_PY = (("locust", "Locust"), ("pytest-benchmark", "pytest-benchmark"),
           ("asv", "airspeed velocity"))


DEPLOY_PLATFORMS = (
    ("cloudflare-workers", "Cloudflare Workers & Pages"),
    ("cloudflare-edge", "Cloudflare proxy / CDN / WAF in front of an origin"),
    ("vercel", "Vercel"),
    ("netlify", "Netlify"),
    ("fly", "Fly.io"),
    ("railway", "Railway"),
    ("render", "Render"),
    ("heroku", "Heroku / Dokku (Procfile buildpack)"),
    ("dokploy", "Dokploy"),
    ("coolify", "Coolify"),
    ("kamal", "Kamal"),
    ("vps", "Self-managed server (VPS / bare metal, systemd, PM2, nginx, Caddy)"),
    ("kubernetes", "Kubernetes (Helm, Kustomize, manifests)"),
    ("aws", "AWS (Lambda, ECS, App Runner, Amplify, EC2)"),
    ("gcp", "Google Cloud / Firebase (Cloud Run, App Engine, Hosting)"),
    ("azure", "Azure (App Service, Functions, Static Web Apps)"),
    ("digitalocean", "DigitalOcean App Platform"),
)
DEPLOY_IDS = tuple(pid for pid, _ in DEPLOY_PLATFORMS)
DEPLOY_LABELS = dict(DEPLOY_PLATFORMS)
DEPLOY_OTHER = "other"

WEB_FRAMEWORKS = ("Next.js", "Nuxt", "Astro", "Remix", "TanStack Start", "TanStack Router",
                  "Angular", "Svelte", "SvelteKit", "Vue", "React", "SolidJS")
API_FRAMEWORKS = ("NestJS", "Express", "Fastify", "FastAPI", "Django", "Flask",
                  "Laravel", "Rails", "Hono", "Elysia")


def add(seq, value):
    if value and value not in seq:
        seq.append(value)


class Detected(object):
    def __init__(self):
        self.lang = []
        self.pm = []
        self.fw = []
        self.db = []
        self.auth = []
        self.host = []
        self.ci = []
        self.test = []
        self.migrations = []
        self.adapters = []
        self.cmds = {}
        self.command_sources = {}
        self.platforms = []
        self.deploy = []           # DEPLOY_PLATFORMS ids with repository evidence
        self.mono_tool = ""
        self.components = []       # (name, kind, path)
        self.services = []
        self.integrations = []     # (service, used for)
        self.i18n_libs = []
        self.locales = []
        self.catalog = ""
        self.ml = []               # models, prompts, retrieval, eval tooling
        self.vector = []           # vector stores / indexes
        self.dataeng = []          # orchestration, transformation, warehouses
        self.messaging = []        # queues, brokers, workflow engines
        self.iac = []              # infrastructure this repository provisions
        self.scrape = []           # third-party acquisition
        self.load = []             # benchmark / load tooling
        self.types = [12]

    def csv(self, field):
        return ", ".join(getattr(self, field))


class Repo(object):
    """Read-only view of the target directory."""

    def __init__(self, root):
        self.root = Path(root)
        self._pkg = None
        self._pkg_read = False

    def has(self, rel):
        return (self.root / rel).exists()

    def text(self, rel):
        p = self.root / rel
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except (IOError, OSError):
            return ""

    def pkg(self):
        if not self._pkg_read:
            self._pkg_read = True
            try:
                self._pkg = json.loads(self.text("package.json"))
            except ValueError:
                self._pkg = None
        return self._pkg or {}

    def json_file(self, rel):
        try:
            value = json.loads(strip_jsonc(self.text(rel)))
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}

    def deps(self):
        if hasattr(self, "_all_deps") and self._all_deps is not None:
            return self._all_deps
        p = self.pkg()
        out = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            value = p.get(key)
            if isinstance(value, dict):
                out.update(value)
        scan_parents = ["apps", "packages", "services", "libs", "src"]
        workspaces = p.get("workspaces")
        if isinstance(workspaces, list):
            for pattern in workspaces:
                if isinstance(pattern, str) and pattern.endswith("/*"):
                    parent = pattern[:-2].strip("/")
                    if parent and parent not in scan_parents:
                        scan_parents.append(parent)
        for parent in scan_parents:
            p_dir = self.root / parent
            if p_dir.is_dir():
                for child in self.subdirs(parent):
                    if child.name.lower() in NON_PRODUCT_DIRS or child.name.lower().startswith("test"):
                        continue
                    pkg_file = child / "package.json"
                    if pkg_file.is_file():
                        try:
                            sub_p = json.loads(pkg_file.read_text(encoding="utf-8", errors="replace"))
                            if isinstance(sub_p, dict):
                                for key in ("dependencies", "devDependencies", "peerDependencies"):
                                    val = sub_p.get(key)
                                    if isinstance(val, dict):
                                        out.update(val)
                        except (ValueError, IOError, OSError):
                            pass
        self._all_deps = out
        return out

    def has_ts(self):
        if self.has("tsconfig.json") or self.has("tsconfig.base.json"):
            return True
        for parent in ("apps", "packages", "services", "libs", "src"):
            p_dir = self.root / parent
            if p_dir.is_dir():
                for child in self.subdirs(parent):
                    if (child / "tsconfig.json").is_file():
                        return True
        return False

    def scripts(self):
        s = self.pkg().get("scripts")
        return s if isinstance(s, dict) else {}

    def pydep(self, name):
        pattern = re.compile(r"(^|[^A-Za-z0-9_.-])%s([^A-Za-z0-9_.-]|$)" % re.escape(name),
                             re.IGNORECASE | re.MULTILINE)
        for f in ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"):
            if self.has(f) and pattern.search(self.text(f)):
                return True
        return any(pattern.search(text) for text in self.child_python_manifests())

    def child_python_manifests(self):
        """Python manifests of workspace children, read once: pydep runs per name."""
        if getattr(self, "_child_py", None) is not None:
            return self._child_py
        texts = []
        for parent in ("services", "backend", "packages", "apps"):
            for child in self.subdirs(parent):
                name = child.name.lower()
                if name in NON_PRODUCT_DIRS or name.startswith("test"):
                    continue
                for f in ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"):
                    p = child / f
                    if p.is_file():
                        try:
                            texts.append(p.read_text(encoding="utf-8", errors="replace"))
                        except (IOError, OSError):
                            pass
        self._child_py = texts
        return texts

    def subdirs(self, rel):
        p = self.root / rel
        if not p.is_dir():
            return []
        try:
            return sorted([c for c in p.iterdir() if not c.name.startswith(".")],
                          key=lambda c: c.name)
        except OSError:
            return []


# Children of a scanned parent that hold samples rather than the product itself.
NON_PRODUCT_DIRS = ("fixtures", "fixture", "examples", "example", "samples", "__tests__")


def strip_jsonc(text):
    """Drop // and /* */ comments and trailing commas outside strings, for deno.jsonc."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


WALK_SKIP_DIRS = ("node_modules", "dist", "build", "vendor", "venv", "env", "target",
                  "coverage", "__pycache__", "out", "tmp")


def find_prisma_schema(root, max_depth=4):
    """First prisma/schema.prisma below root, pruning dependency, build and sample
    directories while walking and judging only the part of the path inside the repository."""
    base = str(root).rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(str(root)):
        if dirpath.count(os.sep) - base >= max_depth:
            dirnames[:] = []
        dirnames[:] = sorted(x for x in dirnames
                             if not x.startswith(".") and x not in WALK_SKIP_DIRS
                             and x.lower() not in NON_PRODUCT_DIRS
                             and not x.lower().startswith("test"))
        if os.path.basename(dirpath) == "prisma" and "schema.prisma" in filenames:
            return Path(dirpath) / "schema.prisma"
    return None


def add_markers(text, mappings, destination):
    """Append labels for dependency/config markers found in ecosystem text."""
    lowered = text.lower()
    for marker, label in mappings:
        if marker.lower() in lowered:
            add(destination, label)


def adapter_command(detected, adapter, key, command):
    """Compose one stage across languages, but keep one default per adapter."""
    sources = detected.command_sources.setdefault(key, [])
    if adapter in sources:
        return
    if key in detected.cmds and detected.cmds[key] != command:
        detected.cmds[key] = "%s && %s" % (detected.cmds[key], command)
    else:
        detected.cmds[key] = command
    sources.append(adapter)


def detect_deploy(repo, dep):
    """Deployment platforms with evidence in the repository. Only files that exist to
    configure a deploy count -- an SDK import says the code talks to a cloud, not that it
    runs there -- and a Traefik label alone names no platform: every Docker PaaS uses it."""
    found = []

    def has_any(*rels):
        return any(repo.has(rel) for rel in rels)

    compose = "\n".join(repo.text(f) for f in ("docker-compose.yml", "docker-compose.yaml",
                                               "compose.yml", "compose.yaml"))
    kamal = repo.text("config/deploy.yml")
    sam = repo.text("template.yaml") + repo.text("template.yml")
    app_yaml = repo.text("app.yaml")

    if (has_any("wrangler.toml", "wrangler.json", "wrangler.jsonc")
            or dep("@cloudflare/workers-types") or dep("@opennextjs/cloudflare")
            or dep("@cloudflare/next-on-pages")):
        add(found, "cloudflare-workers")
    if has_any("vercel.json", ".vercel/project.json"):
        add(found, "vercel")
    if has_any("netlify.toml"):
        add(found, "netlify")
    if has_any("fly.toml"):
        add(found, "fly")
    if has_any("railway.json", "railway.toml"):
        add(found, "railway")
    if has_any("render.yaml"):
        add(found, "render")
    if has_any("Procfile") or "heroku" in repo.text("app.json"):
        add(found, "heroku")
    if "dokploy" in compose.lower() or has_any("dokploy.json"):
        add(found, "dokploy")
    if ("coolify" in compose.lower() or "SERVICE_FQDN_" in compose
            or "SERVICE_URL_" in compose):
        add(found, "coolify")
    if has_any(".kamal") or (re.search(r"^service:", kamal, re.M)
                             and re.search(r"^image:", kamal, re.M)):
        add(found, "kamal")
    if (has_any("Caddyfile", "nginx.conf", "ecosystem.config.js", "ecosystem.config.cjs")
            or [p for p in repo.root.glob("*.service") if p.is_file()]):
        add(found, "vps")
    if (has_any("Chart.yaml", "kustomization.yaml", "skaffold.yaml", "helmfile.yaml")
            or repo.subdirs("k8s") or repo.subdirs("helm")):
        add(found, "kubernetes")
    if (has_any("cdk.json", "samconfig.toml", "amplify.yml", "apprunner.yaml",
                "serverless.yml", "serverless.yaml", ".ebextensions")
            or repo.subdirs("copilot") or "AWSTemplateFormatVersion" in sam
            or "AWS::Serverless" in sam):
        add(found, "aws")
    if (has_any("cloudbuild.yaml", "firebase.json", ".firebaserc")
            or re.search(r"^runtime:", app_yaml, re.M)):
        add(found, "gcp")
    if has_any("azure.yaml", "staticwebapp.config.json", "host.json"):
        add(found, "azure")
    if has_any(".do/app.yaml", ".do/deploy.template.yaml"):
        add(found, "digitalocean")
    return found


def parse_deploy(raw):
    """--deploy value -> list of ids, or an error message."""
    ids = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip().lower()
        if not part or part == "none":
            continue
        if part not in DEPLOY_IDS and part != DEPLOY_OTHER:
            return None, part
        add(ids, part)
    return ids, None


def detect(root):
    repo = Repo(root)
    d = Detected()
    deps = repo.deps()
    scripts = repo.scripts()

    def dep(name):
        return name in deps

    # -- node ------------------------------------------------------------------
    if repo.has("package.json"):
        add(d.adapters, "node")
        add(d.lang, "Node.js + TypeScript" if repo.has_ts() else "Node.js")
        if repo.has("bun.lockb") or repo.has("bun.lock"):
            pm = "bun"
        elif repo.has("pnpm-lock.yaml"):
            pm = "pnpm"
        elif repo.has("yarn.lock"):
            pm = "yarn"
        else:
            pm = "npm"
        add(d.pm, pm)

        for name, label in (("next", "Next.js"), ("nuxt", "Nuxt"), ("astro", "Astro"),
                            ("@remix-run/react", "Remix"),
                            ("@tanstack/react-start", "TanStack Start"),
                            ("@tanstack/react-router", "TanStack Router"),
                            ("@nestjs/core", "NestJS"), ("@angular/core", "Angular"),
                            ("express", "Express"), ("fastify", "Fastify"),
                            ("hono", "Hono"), ("elysia", "Elysia"),
                            ("@sveltejs/kit", "SvelteKit"), ("svelte", "Svelte"),
                            ("solid-js", "SolidJS"), ("vue", "Vue")):
            if dep(name):
                add(d.fw, label)
        if dep("react") and not any(f in d.fw for f in WEB_FRAMEWORKS):
            add(d.fw, "React")
        if dep("vite"):
            add(d.fw, "Vite")
        if dep("tailwindcss"):
            add(d.fw, "Tailwind CSS")

        prisma_schema = ""
        if repo.has("prisma/schema.prisma"):
            prisma_schema = repo.text("prisma/schema.prisma")
        else:
            p = find_prisma_schema(repo.root) if (dep("@prisma/client") or dep("prisma")) else None
            if p is not None:
                try:
                    prisma_schema = p.read_text(encoding="utf-8", errors="replace")
                except (IOError, OSError):
                    pass
        if dep("@prisma/client") or prisma_schema or repo.has("prisma/schema.prisma"):
            provider = re.search(r'provider\s*=\s*"([a-z]+)"', prisma_schema) if prisma_schema else None
            add(d.db, "Prisma (%s)" % provider.group(1) if provider else "Prisma")
            add(d.migrations, "Prisma Migrate")
        has_drizzle_config = (repo.has("drizzle.config.ts") or repo.has("drizzle.config.js")
                              or repo.has("drizzle.config.json"))
        if not has_drizzle_config:
            for p in ("packages", "apps", "services"):
                if any(child.is_dir() and (
                        (child / "drizzle.config.ts").is_file()
                        or (child / "drizzle.config.js").is_file()
                        or (child / "drizzle.config.json").is_file())
                       for child in repo.subdirs(p)):
                    has_drizzle_config = True
                    break
        if dep("drizzle-orm") or has_drizzle_config:
            add(d.db, "Drizzle")
        for name, label in (("@supabase/supabase-js", "Supabase (Postgres)"),
                            ("typeorm", "TypeORM"), ("sequelize", "Sequelize"),
                            ("@mikro-orm/core", "MikroORM"), ("knex", "Knex"),
                            ("mongoose", "MongoDB"), ("pg", "PostgreSQL"),
                            ("mysql2", "MySQL"), ("better-sqlite3", "SQLite"),
                            ("sqlite3", "SQLite"), ("mssql", "SQL Server"),
                            ("oracledb", "Oracle")):
            if dep(name):
                add(d.db, label)
        if dep("drizzle-kit") or has_drizzle_config:
            add(d.migrations, "Drizzle Kit")
        if dep("ioredis") or dep("redis"):
            add(d.db, "Redis")
        for name, label in (("next-auth", "Auth.js / NextAuth"),
                            ("@clerk/nextjs", "Clerk"),
                            ("@supabase/supabase-js", "Supabase Auth"),
                            ("passport", "Passport"), ("@nestjs/jwt", "JWT (@nestjs/jwt)"),
                            ("lucia", "Lucia")):
            if dep(name):
                add(d.auth, label)
        for name, label in (("vitest", "Vitest"), ("jest", "Jest"), ("mocha", "Mocha"),
                            ("@playwright/test", "Playwright"), ("cypress", "Cypress"),
                            ("supertest", "Supertest"), ("@pact-foundation/pact", "Pact"),
                            ("@testing-library/react", "Testing Library")):
            if dep(name):
                add(d.test, label)

        if "dev" in scripts:
            d.cmds["run"] = "%s run dev" % pm
        elif "start" in scripts:
            d.cmds["run"] = "%s start" % pm
        script_candidates = {
            "format": ("format:check", "check:format", "format"),
            "lint": ("lint",),
            "typecheck": ("typecheck", "type-check", "check:types"),
            "unit": ("test:unit", "unit", "test"),
            "integration": ("test:integration", "integration"),
            "contract": ("test:contract", "contract"),
            "build": ("build",),
            "scan": ("security", "scan", "audit"),
            "a11y": ("test:a11y", "a11y", "accessibility"),
            "e2e": ("test:e2e", "e2e"),
        }
        for key, candidates in script_candidates.items():
            for script in candidates:
                if script in scripts:
                    d.cmds[key] = "%s run %s" % (pm, script)
                    break
        # A bare `tsc` reads only ./tsconfig.json; a monorepo without one needs its own
        # script, and a blank row is recoverable where a gate that always fails is not.
        if "typecheck" not in d.cmds and repo.has("tsconfig.json") and dep("typescript"):
            d.cmds["typecheck"] = {"npm": "npm exec tsc -- --noEmit",
                                   "pnpm": "pnpm exec tsc --noEmit",
                                   "yarn": "yarn tsc --noEmit",
                                   "bun": "bunx tsc --noEmit"}[pm]
        if "unit" not in d.cmds and pm == "bun":
            d.cmds["unit"] = "bun test"
        if "e2e" not in d.cmds and dep("@playwright/test"):
            d.cmds["e2e"] = {"npm": "npm exec playwright test",
                              "pnpm": "pnpm exec playwright test",
                              "yarn": "yarn playwright test",
                              "bun": "bunx playwright test"}[pm]
        d.cmds["install"] = {"npm": "npm ci" if repo.has("package-lock.json") else "npm install",
                             "pnpm": "pnpm install --frozen-lockfile" if repo.has("pnpm-lock.yaml") else "pnpm install",
                             "yarn": "yarn install", "bun": "bun install"}[pm]
        if "scan" not in d.cmds and pm == "npm":
            d.cmds["scan"] = "npm audit --audit-level=high"
        elif "scan" not in d.cmds and pm == "pnpm":
            d.cmds["scan"] = "pnpm audit --audit-level high"
        for key in d.cmds:
            add(d.command_sources.setdefault(key, []), "node")

    # -- deno ------------------------------------------------------------------
    if repo.has("deno.json") or repo.has("deno.jsonc") or repo.has("deno.lock"):
        add(d.adapters, "deno")
        add(d.lang, "Deno")
        add(d.pm, "deno")
        add(d.test, "deno test")
        deno_cfg = repo.text("deno.json") + repo.text("deno.jsonc")
        if "hono" in deno_cfg.lower():
            add(d.fw, "Hono")
        deno_json = repo.json_file("deno.json") or repo.json_file("deno.jsonc")
        tasks = deno_json.get("tasks", {})
        if not isinstance(tasks, dict):
            tasks = {}

        # A project task wins over the built-in command: adapter_command keeps the first.
        def task_or(names, fallback):
            for name in names:
                if name in tasks:
                    return "deno task %s" % name
            return fallback

        adapter_command(d, "deno", "install", "deno install")
        adapter_command(d, "deno", "unit", task_or(("test", "test:unit"), "deno test"))
        adapter_command(d, "deno", "lint", task_or(("lint",), "deno lint"))
        adapter_command(d, "deno", "format", task_or(("fmt", "format"), "deno fmt --check"))
        adapter_command(d, "deno", "typecheck", task_or(("check", "typecheck"), "deno check"))
        if "run" not in d.cmds:
            if "dev" in tasks:
                d.cmds["run"] = "deno task dev"
            elif "start" in tasks:
                d.cmds["run"] = "deno task start"

    # -- python ----------------------------------------------------------------
    if (repo.has("pyproject.toml") or repo.has("requirements.txt") or repo.has("setup.py")
            or repo.has("Pipfile")):
        add(d.adapters, "python")
        add(d.lang, "Python")
        if repo.has("uv.lock"):
            add(d.pm, "uv")
            adapter_command(d, "python", "install", "uv sync")
        elif repo.has("poetry.lock"):
            add(d.pm, "Poetry")
            adapter_command(d, "python", "install", "poetry install")
        elif repo.has("Pipfile"):
            add(d.pm, "pipenv")
            adapter_command(d, "python", "install", "pipenv install")
        elif repo.has("requirements.txt"):
            add(d.pm, "pip")
            adapter_command(d, "python", "install", "pip install -r requirements.txt")
        for name, label in (("django", "Django"), ("fastapi", "FastAPI"),
                            ("flask", "Flask")):
            if repo.pydep(name):
                add(d.fw, label)
        for name, label in (("sqlalchemy", "SQLAlchemy"), ("django", "Django ORM"),
                            ("psycopg", "PostgreSQL"), ("psycopg2", "PostgreSQL"),
                            ("asyncpg", "PostgreSQL"), ("pymysql", "MySQL"),
                            ("mysqlclient", "MySQL"), ("pymongo", "MongoDB"),
                            ("motor", "MongoDB"), ("redis", "Redis"),
                            ("aiosqlite", "SQLite")):
            if repo.pydep(name):
                add(d.db, label)
        if repo.pydep("alembic") or repo.has("alembic.ini"):
            add(d.migrations, "Alembic")
        if repo.pydep("django") and repo.has("manage.py"):
            add(d.migrations, "Django migrations")
        if repo.pydep("pytest") or repo.has("pytest.ini"):
            add(d.test, "pytest")
            adapter_command(d, "python", "unit", "pytest")
            if repo.has("tests/integration"):
                adapter_command(d, "python", "integration", "pytest tests/integration")
            if repo.has("tests/contract"):
                adapter_command(d, "python", "contract", "pytest tests/contract")
        for name, label in (("hypothesis", "Hypothesis"), ("tox", "tox"),
                            ("nox", "nox"), ("playwright", "Playwright")):
            if repo.pydep(name):
                add(d.test, label)
        if repo.pydep("pip-audit"):
            adapter_command(d, "python", "scan", "pip-audit")
        if repo.pydep("ruff"):
            adapter_command(d, "python", "lint", "ruff check .")
            adapter_command(d, "python", "format", "ruff format --check .")
        if repo.pydep("mypy"):
            adapter_command(d, "python", "typecheck", "mypy .")

    # -- other runtimes --------------------------------------------------------
    if repo.has("go.mod"):
        add(d.adapters, "go")
        add(d.lang, "Go")
        add(d.pm, "go modules")
        add(d.test, "go test")
        adapter_command(d, "go", "install", "go mod download")
        adapter_command(d, "go", "unit", "go test ./...")
        adapter_command(d, "go", "build", "go build ./...")
        adapter_command(d, "go", "format", "test -z \"$(find . -name '*.go' -not -path "
                        "'./vendor/*' -exec gofmt -l {} +)\"")
        adapter_command(d, "go", "lint", "go vet ./...")
        go_mod = repo.text("go.mod")
        add_markers(go_mod, (("gorm.io/gorm", "GORM"), ("github.com/jackc/pgx", "PostgreSQL"),
                             ("github.com/lib/pq", "PostgreSQL"),
                             ("github.com/go-sql-driver/mysql", "MySQL"),
                             ("modernc.org/sqlite", "SQLite"),
                             ("go.mongodb.org/mongo-driver", "MongoDB"),
                             ("github.com/redis/go-redis", "Redis")), d.db)
        add_markers(go_mod, (("github.com/stretchr/testify", "testify"),
                             ("github.com/onsi/ginkgo", "Ginkgo")), d.test)
        if repo.has("sqlc.yaml") or repo.has("sqlc.yml"):
            add(d.db, "sqlc")
            add(d.migrations, "sqlc-managed SQL migrations")
        for migration_dir in ("migrations", "db/migrations"):
            if repo.has(migration_dir):
                add(d.migrations, "SQL migration files (%s)" % migration_dir)
    if repo.has("Cargo.toml"):
        add(d.adapters, "rust")
        add(d.lang, "Rust")
        add(d.pm, "cargo")
        add(d.test, "cargo test")
        adapter_command(d, "rust", "install", "cargo fetch")
        adapter_command(d, "rust", "unit", "cargo test")
        adapter_command(d, "rust", "build", "cargo build --release")
        adapter_command(d, "rust", "format", "cargo fmt --check")
        adapter_command(d, "rust", "lint", "cargo clippy --all-targets --all-features -- -D warnings")
        cargo = repo.text("Cargo.toml")
        add_markers(cargo, (("diesel", "Diesel"), ("sqlx", "SQLx"),
                            ("sea-orm", "SeaORM"), ("mongodb", "MongoDB"),
                            ("redis", "Redis")), d.db)
        add_markers(cargo, (("proptest", "proptest"), ("rstest", "rstest"),
                            ("mockall", "mockall")), d.test)
        if repo.has("migrations"):
            add(d.migrations, "Rust migration directory")
    if repo.has("composer.json"):
        add(d.adapters, "php")
        add(d.lang, "PHP")
        add(d.pm, "Composer")
        adapter_command(d, "php", "install", "composer install --no-interaction --prefer-dist")
        composer = repo.json_file("composer.json")
        php_deps = {}
        for section in ("require", "require-dev"):
            if isinstance(composer.get(section), dict):
                php_deps.update(composer[section])
        if "laravel/framework" in php_deps:
            add(d.fw, "Laravel")
            add(d.db, "Eloquent ORM")
            add(d.migrations, "Laravel migrations")
        if "doctrine/orm" in php_deps:
            add(d.db, "Doctrine ORM")
        for name, label in (("ext-pdo_pgsql", "PostgreSQL"), ("ext-pgsql", "PostgreSQL"),
                            ("ext-pdo_mysql", "MySQL/MariaDB"),
                            ("ext-mongodb", "MongoDB"), ("predis/predis", "Redis")):
            if name in php_deps:
                add(d.db, label)
        for name, label in (("pestphp/pest", "Pest"), ("phpunit/phpunit", "PHPUnit"),
                            ("behat/behat", "Behat"),
                            ("laravel/dusk", "Laravel Dusk")):
            if name in php_deps:
                add(d.test, label)
        php_scripts = composer.get("scripts", {})
        if isinstance(php_scripts, dict):
            for script, key in (("test", "unit"), ("test:unit", "unit"),
                                ("test:integration", "integration"),
                                ("test:contract", "contract"), ("test:e2e", "e2e"),
                                ("lint", "lint")):
                if script in php_scripts:
                    adapter_command(d, "php", key, "composer %s" % script)
        if "php" not in d.command_sources.get("unit", []) and "pestphp/pest" in php_deps:
            adapter_command(d, "php", "unit", "vendor/bin/pest")
        elif "php" not in d.command_sources.get("unit", []) and "phpunit/phpunit" in php_deps:
            adapter_command(d, "php", "unit", "vendor/bin/phpunit")
    if repo.has("Gemfile"):
        add(d.adapters, "ruby")
        add(d.lang, "Ruby")
        add(d.pm, "Bundler")
        adapter_command(d, "ruby", "install", "bundle install")
        gemfile = repo.text("Gemfile")
        if re.search(r"\bgem\s+['\"]rails['\"]", gemfile):
            add(d.fw, "Rails")
            add(d.db, "Active Record")
            add(d.migrations, "Rails migrations")
        add_markers(gemfile, (("gem 'pg'", "PostgreSQL"), ("gem \"pg\"", "PostgreSQL"),
                              ("gem 'mysql2'", "MySQL"), ("gem \"mysql2\"", "MySQL"),
                              ("gem 'sqlite3'", "SQLite"), ("gem \"sqlite3\"", "SQLite"),
                              ("mongoid", "MongoDB"), ("redis", "Redis")), d.db)
        add_markers(gemfile, (("rspec", "RSpec"), ("minitest", "Minitest"),
                              ("cucumber", "Cucumber"), ("capybara", "Capybara")), d.test)
        if "RSpec" in d.test:
            adapter_command(d, "ruby", "unit", "bundle exec rspec")
        elif "Minitest" in d.test:
            adapter_command(d, "ruby", "unit", "bundle exec rake test")
    if repo.has("pom.xml"):
        add(d.adapters, "jvm-maven")
        add(d.lang, "Java")
        add(d.pm, "Maven")
        adapter_command(d, "jvm-maven", "install", "mvn dependency:go-offline")
        adapter_command(d, "jvm-maven", "unit", "mvn test")
        adapter_command(d, "jvm-maven", "build", "mvn package -DskipTests")
    if repo.has("build.gradle") or repo.has("build.gradle.kts"):
        add(d.adapters, "jvm-gradle")
        add(d.lang, "Java / Kotlin")
        add(d.pm, "Gradle")
        adapter_command(d, "jvm-gradle", "install", "./gradlew dependencies")
        adapter_command(d, "jvm-gradle", "unit", "./gradlew test")
        adapter_command(d, "jvm-gradle", "build", "./gradlew assemble")
    java_text = "\n".join(repo.text(name) for name in
                            ("pom.xml", "build.gradle", "build.gradle.kts"))
    if java_text.strip():
        add_markers(java_text, (("spring-boot", "Spring Boot"),
                                ("hibernate", "Hibernate/JPA")), d.fw)
        add_markers(java_text, (("spring-data-jpa", "JPA"),
                                ("hibernate-core", "Hibernate"),
                                ("postgresql", "PostgreSQL"), ("mysql", "MySQL"),
                                ("mariadb", "MariaDB"), ("mssql-jdbc", "SQL Server"),
                                ("ojdbc", "Oracle"), ("mongodb", "MongoDB"),
                                ("redis", "Redis")), d.db)
        add_markers(java_text, (("junit", "JUnit"), ("testng", "TestNG"),
                                ("mockito", "Mockito"), ("rest-assured", "REST Assured"),
                                ("testcontainers", "Testcontainers")), d.test)
        add_markers(java_text, (("flyway", "Flyway"),
                                ("liquibase", "Liquibase")), d.migrations)
    csproj_files = list(Path(root).glob("*.csproj"))
    if csproj_files or list(Path(root).glob("*.sln")):
        add(d.adapters, "dotnet")
        add(d.lang, "C# / .NET")
        add(d.pm, "NuGet")
        adapter_command(d, "dotnet", "install", "dotnet restore")
        adapter_command(d, "dotnet", "unit", "dotnet test")
        adapter_command(d, "dotnet", "build", "dotnet build")
        dotnet_text = "\n".join(path.read_text(encoding="utf-8", errors="replace")
                                 for path in csproj_files[:20])
        add_markers(dotnet_text, (("Microsoft.EntityFrameworkCore", "Entity Framework Core"),
                                  ("Npgsql.EntityFrameworkCore", "PostgreSQL"),
                                  ("Pomelo.EntityFrameworkCore.MySql", "MySQL/MariaDB"),
                                  ("Microsoft.EntityFrameworkCore.SqlServer", "SQL Server"),
                                  ("Microsoft.EntityFrameworkCore.Sqlite", "SQLite"),
                                  ("MongoDB.Driver", "MongoDB"),
                                  ("StackExchange.Redis", "Redis"), ("Dapper", "Dapper")), d.db)
        add_markers(dotnet_text, (("xunit", "xUnit"), ("NUnit", "NUnit"),
                                  ("MSTest", "MSTest"),
                                  ("Microsoft.AspNetCore.Mvc.Testing", "ASP.NET integration tests"),
                                  ("Testcontainers", "Testcontainers")), d.test)
        if "Entity Framework Core" in d.db:
            add(d.migrations, "EF Core migrations")

    # -- hosting, CI, platforms ------------------------------------------------
    d.deploy = detect_deploy(repo, dep)
    for pid in d.deploy:
        add(d.host, DEPLOY_LABELS[pid].split(" (")[0])
    if not d.deploy and (dep("@aws-sdk/client-s3") or repo.pydep("boto3")):
        add(d.host, "AWS")           # a client library: uses AWS, not proven to run there
    if not d.deploy and (dep("@google-cloud/storage") or dep("@google-cloud/bigquery")
                         or repo.pydep("google-cloud-storage")
                         or repo.pydep("google-cloud-bigquery")):
        add(d.host, "Google Cloud")
    if repo.has("Dockerfile") or repo.has("docker-compose.yml") or repo.has("compose.yaml"):
        add(d.host, "Docker")
    for f, label in ((".github/workflows", "GitHub Actions"), (".gitlab-ci.yml", "GitLab CI"),
                     ("Jenkinsfile", "Jenkins"), (".circleci", "CircleCI"),
                     ("azure-pipelines.yml", "Azure Pipelines")):
        if repo.has(f):
            add(d.ci, label)

    if repo.has(".replit") or repo.has("replit.nix") or repo.has("replit.md"):
        add(d.platforms, "Replit")
    if repo.has(".lovable") or "lovable" in repo.text("package.json"):
        add(d.platforms, "Lovable")
    for f, label in ((".bolt", "Bolt"), (".idx", "Firebase-Studio"),
                     ("glitch.json", "Glitch"), ("sandbox.config.json", "CodeSandbox"),
                     (".codesandbox", "CodeSandbox")):
        if repo.has(f):
            add(d.platforms, label)

    # -- architecture ----------------------------------------------------------
    for f, label in (("pnpm-workspace.yaml", "pnpm workspaces"), ("turbo.json", "Turborepo"),
                     ("nx.json", "Nx"), ("lerna.json", "Lerna"), ("go.work", "Go workspace")):
        if repo.has(f):
            d.mono_tool = label
    if not d.mono_tool and repo.pkg().get("workspaces"):
        d.mono_tool = "npm/yarn workspaces"
    if not d.mono_tool and re.search(r"^\[workspace\]", repo.text("Cargo.toml"), re.M):
        d.mono_tool = "cargo workspace"

    for parent, kind in (("apps", "application"), ("packages", "package"),
                         ("services", "service"), ("libs", "library")):
        for child in repo.subdirs(parent):
            if child.is_dir():
                d.components.append((child.name, kind, "%s/%s" % (parent, child.name)))
    if len(d.components) > 16:
        d.components = d.components[:16]

    compose = repo.text("docker-compose.yml") or repo.text("compose.yaml")
    if compose:
        in_services = False
        for line in compose.splitlines():
            if re.match(r"^services:\s*$", line):
                in_services = True
                continue
            if in_services:
                if re.match(r"^\S", line):
                    break
                m = re.match(r"^  ([A-Za-z0-9._-]+):\s*$", line)
                if m:
                    add(d.services, m.group(1))

    for name, service, used_for in INTEGRATIONS:
        if dep(name) and service not in [s for s, _ in d.integrations]:
            d.integrations.append((service, used_for))
    for name, service, used_for in PY_INTEGRATIONS:
        if repo.pydep(name) and service not in [s for s, _ in d.integrations]:
            d.integrations.append((service, used_for))

    # -- domain markers --------------------------------------------------------
    for table, dest in ((ML_NODE, d.ml), (VECTOR_NODE, d.vector), (DATA_NODE, d.dataeng),
                        (MSG_NODE, d.messaging), (SCRAPE_NODE, d.scrape),
                        (LOAD_NODE, d.load)):
        for name, label in table:
            if dep(name):
                add(dest, label)
    for table, dest in ((ML_PY, d.ml), (VECTOR_PY, d.vector), (DATA_PY, d.dataeng),
                        (MSG_PY, d.messaging), (SCRAPE_PY, d.scrape), (LOAD_PY, d.load)):
        for name, label in table:
            if repo.pydep(name):
                add(dest, label)
    for f, label in DATA_FILES:
        if repo.has(f):
            add(d.dataeng, label)
    for f, label in IAC_FILES:
        if repo.has(f):
            add(d.iac, label)
    add_markers(repo.text("Gemfile"),
                (("sidekiq", "Sidekiq"), ("resque", "Resque")), d.messaging)
    add_markers(repo.text("go.mod"),
                (("segmentio/kafka-go", "Kafka"), ("Shopify/sarama", "Kafka"),
                 ("rabbitmq/amqp091-go", "RabbitMQ"), ("nats-io/nats.go", "NATS")),
                d.messaging)
    add_markers(repo.text("go.mod"), (("gocolly/colly", "Colly"),), d.scrape)

    # -- i18n ------------------------------------------------------------------
    for name, label in I18N_LIBS:
        if dep(name):
            add(d.i18n_libs, label)
    if repo.pydep("django") and (repo.has("locale") or "USE_I18N" in repo.text("settings.py")):
        add(d.i18n_libs, "Django i18n")
    if repo.has("config/locales"):
        add(d.i18n_libs, "Rails i18n")
    if re.search(r"\bi18n\s*:", repo.text("astro.config.mjs") + repo.text("next.config.js")
                 + repo.text("next.config.mjs") + repo.text("nuxt.config.ts")):
        add(d.i18n_libs, "framework i18n config")

    for rel in LOCALE_DIRS:
        entries = repo.subdirs(rel)
        if not entries:
            continue
        found_here = []
        for child in entries:
            m = LOCALE_RE.match(child.name)
            if m:
                code = m.group(1) if not m.group(2) else "%s-%s" % (m.group(1), m.group(2))
                found_here.append(code)
        if found_here:
            if not d.catalog:
                d.catalog = rel + "/"
            for code in found_here:
                add(d.locales, code)

    # -- the project types this repository looks like --------------------------
    types = []
    if any(f in d.fw for f in ("Astro",)):
        types.append(2)
    if any(f in d.fw for f in WEB_FRAMEWORKS if f != "Astro"):
        types.append(1)
    if any(f in d.fw for f in API_FRAMEWORKS):
        types.append(3)
    if d.dataeng:
        types.append(6)
    if d.ml or d.vector:
        types.append(7)
    if d.messaging or len(d.services) > 2 or len(
            [c for c in d.components if c[1] == "service"]) > 1:
        types.append(8)
    if d.iac:
        types.append(9)
    if d.scrape:
        types.append(10)
    if not types:
        if not d.lang:
            types = [11]
        elif d.host:
            types = [3]
        else:
            types = [4]
    d.types = sorted(set(types))
    return d
