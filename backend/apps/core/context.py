"""
Per-request context (who is acting, from where) stored in context variables.

Context variables are isolated per request/thread, so simultaneous users never see
each other's context. The audit log reads from here.
"""

import contextvars
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    user_id: int | None = None
    ip_address: str | None = None
    user_agent: str = ""
    request_id: str = ""


_EMPTY = RequestContext()
_current: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar("elite_request_context", default=None)


def get_context() -> RequestContext:
    return _current.get() or _EMPTY


def set_context(ctx: RequestContext) -> contextvars.Token:
    return _current.set(ctx)


def reset_context(token: contextvars.Token) -> None:
    _current.reset(token)


def new_request_id() -> str:
    return uuid.uuid4().hex
