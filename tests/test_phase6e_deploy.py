"""Phase 6.E smoke tests for deploy + IaC artifacts.

These tests are intentionally lightweight — they don't spin up Docker or
a Kubernetes cluster. Their job is to catch the dumb mistakes (drift
between the canonical backup script and the chart's mirror, a YAML
manifest that won't parse, a template that references a value that
doesn't exist in `values.yaml`).

End-to-end validation (`docker build`, `helm template ... | kubectl
apply --dry-run=client`) is documented in `docs/ops/deploy.md` §6 and
gated by `make docker-build` / `make helm-template` for the operator.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Helm chart paths
HELM_DIR = REPO_ROOT / "infra" / "helm" / "swarmos"
HELM_CHART = HELM_DIR / "Chart.yaml"
HELM_VALUES = HELM_DIR / "values.yaml"
HELM_VALUES_VINEYARD = HELM_DIR / "values-vineyard-01.yaml"
HELM_TEMPLATES_DIR = HELM_DIR / "templates"

# Raw k8s manifests
K8S_DIR = REPO_ROOT / "infra" / "k8s"


# ── Helm chart shape ────────────────────────────────────────────────────────

def test_chart_metadata_parses() -> None:
    chart = yaml.safe_load(HELM_CHART.read_text())
    assert chart["name"] == "swarmos"
    assert chart["apiVersion"] == "v2"
    assert chart["version"]
    # appVersion is the SwarmOS release tag — must match a semver-ish
    # string so docker tags don't choke on it.
    assert re.match(r"^\d+\.\d+\.\d+$", str(chart["appVersion"]))


def test_chart_has_all_planned_templates() -> None:
    """Each template promised in the Phase 6.E plan must exist."""
    expected = {
        "_helpers.tpl",
        "namespace.yaml",
        "configmap-site.yaml",
        "deployment-backend.yaml",
        "deployment-frontend.yaml",
        "services.yaml",
        "ingress.yaml",
        "hpa-backend.yaml",
        "networkpolicy.yaml",
        "servicemonitor.yaml",
        "cronjob-backup.yaml",
        "secrets.yaml",
    }
    actual = {p.name for p in HELM_TEMPLATES_DIR.iterdir() if p.is_file()}
    missing = expected - actual
    assert not missing, f"Helm chart missing templates: {missing}"


def test_values_yaml_has_every_referenced_top_key() -> None:
    """Walk the templates looking for `.Values.<key>` and assert each is
    declared in values.yaml. Catches the classic 'forgot to add a
    default' bug."""
    values = yaml.safe_load(HELM_VALUES.read_text())
    referenced: set[str] = set()
    for tpl in HELM_TEMPLATES_DIR.glob("*.yaml"):
        for match in re.finditer(r"\.Values\.([a-zA-Z_][\w.]*)", tpl.read_text()):
            # only the top-level segment for this smoke check; nested
            # missing keys are caught by `helm template` itself.
            referenced.add(match.group(1).split(".")[0])
    declared = set(values.keys())
    unknown = referenced - declared
    assert not unknown, (
        f"Templates reference .Values.{{{', '.join(sorted(unknown))}}}; "
        f"add defaults to values.yaml"
    )


def test_vineyard_overlay_overrides_known_keys_only() -> None:
    """The site overlay must not introduce keys that don't exist in
    the defaults — typos there are silent failures (Helm just ignores
    unknown values)."""
    base = yaml.safe_load(HELM_VALUES.read_text())
    overlay = yaml.safe_load(HELM_VALUES_VINEYARD.read_text())

    def walk(b: object, o: object, path: str = "") -> list[str]:
        bad: list[str] = []
        if not isinstance(o, dict) or not isinstance(b, dict):
            return bad
        for key, val in o.items():
            new_path = f"{path}.{key}" if path else key
            if key not in b:
                bad.append(new_path)
                continue
            bad.extend(walk(b[key], val, new_path))
        return bad

    unknown = walk(base, overlay)
    assert not unknown, (
        f"values-vineyard-01.yaml references keys not in values.yaml: "
        f"{unknown}"
    )


# ── Raw k8s manifests ───────────────────────────────────────────────────────

def test_all_k8s_manifests_parse() -> None:
    """Every `*.yaml` under infra/k8s/ must be parseable. Catches the
    indentation typo before kubectl does."""
    found = list(K8S_DIR.rglob("*.yaml"))
    assert found, "no k8s manifests found"
    for path in found:
        with path.open() as fp:
            list(yaml.safe_load_all(fp))   # raises on bad YAML


def test_k8s_pod_specs_run_non_root_with_dropped_caps() -> None:
    """Every Deployment / CronJob template must drop all capabilities,
    run as non-root, and forbid privilege escalation. The PSS
    `restricted` profile mandates this; we assert it before deploy."""
    workload_kinds = {"Deployment", "CronJob"}
    for path in K8S_DIR.glob("*.yaml"):
        with path.open() as fp:
            docs = list(yaml.safe_load_all(fp))
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if doc.get("kind") not in workload_kinds:
                continue
            spec = _container_spec(doc)
            containers: Any = spec.get("containers", [])
            for c in containers:
                sc: Any = c.get("securityContext", {})
                assert sc.get("allowPrivilegeEscalation") is False, (
                    f"{path.name}::{c.get('name')} must "
                    "allowPrivilegeEscalation=false"
                )
                assert sc.get("runAsNonRoot") is True, (
                    f"{path.name}::{c.get('name')} must runAsNonRoot=true"
                )
                caps = sc.get("capabilities", {}).get("drop", [])
                assert "ALL" in caps, (
                    f"{path.name}::{c.get('name')} must drop ALL caps "
                    f"(got {caps})"
                )


def _container_spec(doc: dict[str, Any]) -> Any:
    """Reach into Deployment.spec.template.spec or
    CronJob.spec.jobTemplate.spec.template.spec."""
    if doc.get("kind") == "Deployment":
        return (
            doc.get("spec", {})
            .get("template", {})
            .get("spec", {})
        )
    if doc.get("kind") == "CronJob":
        return (
            doc.get("spec", {})
            .get("jobTemplate", {})
            .get("spec", {})
            .get("template", {})
            .get("spec", {})
        )
    return {}


# ── compose-prod ────────────────────────────────────────────────────────────

def test_compose_prod_parses_and_pins_digests() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.prod.yml").read_text())
    services = compose["services"]
    # Every upstream image must pin by sha256. Our OWN images (ghcr.io/...)
    # are tagged at CI build time so they're allowed to use a tag
    # reference here (digest pinning happens at the Helm/compose layer
    # via --set image.<svc>.digest=...). Env-var defaults that point at
    # our own images carry the literal `ghcr.io/<owner>/swarmos-` prefix.
    for name, svc in services.items():
        img = svc.get("image", "")
        if not img:
            continue
        # Skip our own images regardless of var-template wrapping.
        if "ghcr.io/" in img and "/swarmos-" in img:
            continue
        # Upstream images (pg, redis, nginx, certbot, alpine) must be
        # digest-pinned per Phase 0 security baseline.
        assert "@sha256:" in img, (
            f"compose-prod service {name!r} image {img!r} must be "
            f"digest-pinned"
        )


def test_compose_prod_uses_structured_secret_env_not_interpolated_urls() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.prod.yml").read_text())
    backend_env = compose["services"]["backend"]["environment"]
    backup_env = compose["services"]["backup"]["environment"]

    assert "DATABASE_URL" not in backend_env
    assert "DATABASE_URL" not in backup_env
    assert backend_env["POSTGRES_HOST"] == "postgres"
    assert backup_env["POSTGRES_HOST"] == "postgres"
    assert "REDIS_URL" not in backend_env
    assert backend_env["REDIS_HOST"] == "redis"


def test_compose_prod_redis_is_tls_and_certbot_does_not_share_pid_namespace() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.prod.yml").read_text())
    redis = compose["services"]["redis"]
    backend_env = compose["services"]["backend"]["environment"]
    certbot = compose["services"]["certbot"]

    command = " ".join(redis["command"])
    assert "--tls-port" in command
    assert "--tls-auth-clients yes" in command
    assert backend_env["REDIS_TLS_CA_CERTS"] == "/run/secrets/redis/ca.crt"
    assert "pid" not in certbot


def test_dev_compose_binds_datastores_to_loopback_and_requires_passwords() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    postgres = compose["services"]["postgres"]
    redis = compose["services"]["redis"]

    assert postgres["ports"] == ["127.0.0.1:5432:5432"]
    assert redis["ports"] == ["127.0.0.1:6379:6379"]
    assert "${POSTGRES_PASSWORD:?" in postgres["environment"]["POSTGRES_PASSWORD"]
    assert any("${REDIS_PASSWORD:?" in part for part in redis["command"])


def test_env_example_has_no_default_infra_passwords_and_declares_cors() -> None:
    env_text = (REPO_ROOT / ".env.example").read_text()
    assert "POSTGRES_PASSWORD=swarm" not in env_text
    assert "REDIS_PASSWORD=swarm" not in env_text
    assert "SWARM_ALLOWED_ORIGINS=http://localhost:3000" in env_text


def test_dev_env_bootstrap_url_encodes_generated_connection_urls() -> None:
    script = (REPO_ROOT / "scripts" / "bootstrap_dev_env.sh").read_text()
    assert "urllib.parse.quote" in script
    assert "${postgres_password_url}" in script
    assert "${redis_password_url}" in script


@pytest.mark.parametrize(
    "compose_file",
    ["docker-compose.yml", "docker-compose.prod.yml"],
)
def test_compose_redis_runs_as_non_root_user(compose_file: str) -> None:
    """Both compose files declare `cap_drop: ALL` on Redis, which strips
    `CAP_SETUID`/`CAP_SETGID`/`CAP_DAC_OVERRIDE`. The official Redis
    alpine entrypoint calls `setpriv` to drop root → `redis` and that
    call fails with `setresuid: Operation not permitted` under those
    caps. The fix is to start the container as the redis user from the
    outside (`user: "999:1000"`, matching the UID/GID baked into the
    image) so the privilege drop is never attempted.

    Regression test for the bug that left a fresh `make demo` boot
    silently falling back to InMemoryBus on macOS because Redis never
    came up.
    """

    compose = yaml.safe_load((REPO_ROOT / compose_file).read_text())
    redis = compose["services"]["redis"]
    user = redis.get("user")
    assert user is not None, (
        f"{compose_file}: redis service must declare `user:` to skip "
        f"setpriv (otherwise cap_drop: ALL breaks startup)"
    )
    # The image bakes redis:redis as 999:1000. Accept either ordering and
    # numeric or name forms, but require a non-root identity.
    assert str(user) not in {"0", "root", "0:0", "root:root"}, (
        f"{compose_file}: redis service must NOT run as root"
    )


# ── Backup script parity ────────────────────────────────────────────────────

def test_backup_script_mirror_matches_canonical() -> None:
    """The script lives in two places: `scripts/backup_postgres.sh` is
    the canonical copy and the Helm chart embeds it via
    `infra/helm/swarmos/files/backup_postgres.sh`. They must stay byte-
    identical or the chart's ConfigMap drifts from the local make target."""
    canonical = (REPO_ROOT / "scripts" / "backup_postgres.sh").read_bytes()
    mirror = (REPO_ROOT / "infra" / "helm" / "swarmos" / "files" / "backup_postgres.sh").read_bytes()
    assert canonical == mirror, (
        "scripts/backup_postgres.sh and infra/helm/swarmos/files/backup_postgres.sh "
        "have drifted. Run `cp scripts/backup_postgres.sh "
        "infra/helm/swarmos/files/backup_postgres.sh` and re-commit."
    )


def test_restore_script_demands_confirmation_flag() -> None:
    """Anti-foot-gun: restore must refuse to run without the explicit
    `--i-understand-this-overwrites` flag."""
    script = (REPO_ROOT / "scripts" / "restore_postgres.sh").read_text()
    assert "--i-understand-this-overwrites" in script
    # The check must come before any pg_restore invocation.
    idx_flag = script.index("--i-understand-this-overwrites")
    idx_restore = script.find("pg_restore")
    assert idx_restore == -1 or idx_flag < idx_restore


# ── Dockerfiles ─────────────────────────────────────────────────────────────

def test_dockerfiles_pin_base_images_by_digest() -> None:
    """Every FROM in our Dockerfiles must pin by sha256 digest."""
    for df in (
        REPO_ROOT / "backend" / "Dockerfile",
        REPO_ROOT / "frontend" / "Dockerfile",
        REPO_ROOT / "infra" / "backup" / "Dockerfile",
    ):
        text = df.read_text()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.upper().startswith("FROM "):
                continue
            # Allow `FROM x@sha256:...` and `FROM x@sha256:... AS stage`.
            assert "@sha256:" in stripped, (
                f"{df.relative_to(REPO_ROOT)}: every FROM must be digest-pinned "
                f"({stripped})"
            )


def test_dockerfiles_run_as_non_root() -> None:
    """Both runtime stages must drop to a non-root USER. We grep for a
    final USER directive — the multi-stage builders are allowed root
    because their output is copied out before the runtime stage."""
    for df in (
        REPO_ROOT / "backend" / "Dockerfile",
        REPO_ROOT / "frontend" / "Dockerfile",
        REPO_ROOT / "infra" / "backup" / "Dockerfile",
    ):
        text = df.read_text()
        users = [ln for ln in text.splitlines() if ln.strip().upper().startswith("USER ")]
        assert users, f"{df.relative_to(REPO_ROOT)}: no USER directive"
        last = users[-1].strip().split()[-1]
        # accept `swarm`, `node`, or numeric uid; reject `root`/`0`.
        assert last not in ("root", "0"), (
            f"{df.relative_to(REPO_ROOT)}: final USER must be non-root (got {last})"
        )


# ── CI workflows ────────────────────────────────────────────────────────────

def test_image_workflows_sha_pin_external_actions() -> None:
    """Every `uses: <org>/<repo>@…` in the new workflows must be SHA-pinned.
    Reuses the existing repo posture (image-scan.yml, test.yml, …)."""
    for wf in (
        REPO_ROOT / ".github" / "workflows" / "image-build.yml",
        REPO_ROOT / ".github" / "workflows" / "image-sign.yml",
    ):
        for match in re.finditer(r"^\s*-?\s*uses:\s*([^\s#]+)", wf.read_text(), re.M):
            ref = match.group(1)
            if "@" not in ref:
                continue
            after_at = ref.split("@", 1)[1]
            assert re.match(r"^[a-f0-9]{40}$", after_at), (
                f"{wf.name}: {ref} must be SHA-pinned (40 hex chars), not a tag"
            )
