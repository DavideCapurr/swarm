"""Runtime environment helpers shared by backend and transport code."""

from __future__ import annotations

import os

PROD_LIKE_ENVS = frozenset({"prod", "production", "staging", "bench"})
DEV_LIKE_ENVS = frozenset({"dev", "test"})
TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def swarm_env() -> str:
    """Return the normalized SwarmOS runtime environment name."""

    return os.getenv("SWARM_ENV", "dev").strip().lower()


def is_prod_like_env(env: str | None = None) -> bool:
    """Return True for environments that must fail closed."""

    return (env.strip().lower() if env is not None else swarm_env()) in PROD_LIKE_ENVS


def is_dev_like_env(env: str | None = None) -> bool:
    """Return True for environments allowed to use local/demo shortcuts."""

    return (env.strip().lower() if env is not None else swarm_env()) in DEV_LIKE_ENVS


def env_flag(name: str) -> bool:
    """Read a boolean environment flag using the project-wide truthy set."""

    return os.getenv(name, "").strip().lower() in TRUTHY_ENV_VALUES


__all__ = (
    "DEV_LIKE_ENVS",
    "PROD_LIKE_ENVS",
    "TRUTHY_ENV_VALUES",
    "env_flag",
    "is_dev_like_env",
    "is_prod_like_env",
    "swarm_env",
)
