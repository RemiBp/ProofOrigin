"""Expose API routers with graceful degradation for optional dependencies."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Dict

from prooforigin.core.logging import get_logger

logger = get_logger(__name__)


# Routers that are required for the public API to function. If any of these fail
# to import we propagate the exception so the application fails fast during
# start-up.
_REQUIRED_ROUTERS = (
    "auth",
    "proofs",
    "public_api",
    "public_verify",
)


# Optional routers rely on third-party services such as Stripe or blockchain
# SDKs. They may not be present in minimal environments (including CI) so we
# treat import failures as non-fatal and simply skip the router registration.
_OPTIONAL_ROUTERS = (
    "admin",
    "ai",
    "api_keys",
    "badges",
    "billing",
    "ledger",
    "webhooks",
)


_available_router_modules: Dict[str, ModuleType] = {}
OPTIONAL_ROUTER_ERRORS: Dict[str, str] = {}


def _load_router(name: str) -> ModuleType:
    module_path = f"{__name__}.{name}"
    return import_module(module_path)


for router_name in (*_REQUIRED_ROUTERS, *_OPTIONAL_ROUTERS):
    try:
        _available_router_modules[router_name] = _load_router(router_name)
    except ImportError as exc:
        if router_name in _REQUIRED_ROUTERS:
            raise
        OPTIONAL_ROUTER_ERRORS[router_name] = str(exc)
        logger.warning(
            "router_optional_dependency_missing",
            router=router_name,
            error=str(exc),
        )


def get_router_modules() -> Dict[str, ModuleType]:
    """Return a copy of the successfully imported router modules."""

    return dict(_available_router_modules)


__all__ = [
    "OPTIONAL_ROUTER_ERRORS",
    "get_router_modules",
]
