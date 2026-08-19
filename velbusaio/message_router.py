"""Message router for Velbus modules.

Provides declarative @register_handler decorator and routes incoming messages to handlers.
"""

# ruff: noqa: SLF001

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
import inspect
import logging
import types
from typing import TYPE_CHECKING, Any, TypeVar, Union, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
    from velbusaio.module import Module

from velbusaio.message import Message
from velbusaio.messages.channel_name_part1 import (
    ChannelNamePart1Message,
    ChannelNamePart1Message2,
    ChannelNamePart1Message3,
)
from velbusaio.messages.channel_name_part2 import (
    ChannelNamePart2Message,
    ChannelNamePart2Message2,
    ChannelNamePart2Message3,
)
from velbusaio.messages.channel_name_part3 import (
    ChannelNamePart3Message,
    ChannelNamePart3Message2,
    ChannelNamePart3Message3,
)
from velbusaio.messages.memory_data import MemoryDataMessage
from velbusaio.messages.memory_data_block import MemoryDataBlockMessage

HandlerCallable = Callable[["Module", Any], Awaitable[None]]
HANDLER_REGISTRY: dict[type[Message], list[HandlerCallable]] = defaultdict(list)
_HANDLERS_LOADED = False


def _ensure_handlers_loaded() -> None:
    """Lazily import all domain handlers so their @register_handler decorators execute."""
    global _HANDLERS_LOADED
    if not _HANDLERS_LOADED:
        _HANDLERS_LOADED = True
        import velbusaio.domains.climate.handler  # noqa: F401
        import velbusaio.domains.cover.handler  # noqa: F401
        import velbusaio.domains.input.handler  # noqa: F401
        import velbusaio.domains.lighting.handler  # noqa: F401
        import velbusaio.domains.meteo.handler  # noqa: F401
        import velbusaio.domains.power.handler  # noqa: F401


def extract_message_types(
    handler: Callable[..., Any]
) -> tuple[type[Message], ...]:
    """Inspect handler callable parameter type annotations to determine Message types."""
    func = getattr(handler, "__func__", handler)
    sig = inspect.signature(func)
    params = [p for p in sig.parameters.values() if p.name not in ("self", "cls")]
    if not params:
        raise ValueError(
            f"Handler {handler} must accept at least one message parameter"
        )
    msg_param = params[1] if len(params) >= 2 else params[0]
    param_name = msg_param.name
    try:
        hints = get_type_hints(func, localns={"Module": object})
        param_type = hints.get(param_name, msg_param.annotation)
    except Exception:
        param_type = msg_param.annotation
        if isinstance(param_type, str):
            try:
                param_type = eval(
                    param_type,
                    getattr(func, "__globals__", {}),
                    {"Module": object},
                )
            except Exception:
                pass

    origin = get_origin(param_type)
    if origin in (Union, types.UnionType):
        types_list = [
            t
            for t in get_args(param_type)
            if isinstance(t, type) and issubclass(t, Message)
        ]
        if not types_list:
            raise TypeError(
                f"Handler {handler} union type has no valid Message subclasses"
            )
        return tuple(types_list)
    elif isinstance(param_type, type) and issubclass(param_type, Message):
        return (param_type,)
    else:
        raise TypeError(
            f"Handler {handler} parameter '{param_name}' type {param_type} is not a subclass of Message"
        )


F = TypeVar("F", bound=Callable[..., Awaitable[None]])


def register_handler(handler: F) -> F:
    """Register a handler function for message types extracted from its type annotation."""
    for msg_cls in extract_message_types(handler):
        HANDLER_REGISTRY[msg_cls].append(handler)
    return handler


async def dispatch_domain_handlers(module: Module, message: Message) -> bool:
    """Dispatch an incoming message to all registered global domain handlers."""
    _ensure_handlers_loaded()
    handlers = HANDLER_REGISTRY.get(type(message))
    if not handlers:
        return False
    for handler in handlers:
        await handler(module, message)
    return True


async def route_module_message(
    module: Module, message: Message, channel_offset: int, log: logging.Logger
) -> None:
    """Route an incoming message to domain handlers and lifecycle processors."""
    await dispatch_domain_handlers(module, message)

    match message:
        # Channel name messages
        case (
            ChannelNamePart1Message()
            | ChannelNamePart1Message2()
            | ChannelNamePart1Message3()
        ):
            await module._process_channel_name_message(1, message)
            await module._cache()

        case (
            ChannelNamePart2Message()
            | ChannelNamePart2Message2()
            | ChannelNamePart2Message3()
        ):
            await module._process_channel_name_message(2, message)
            await module._cache()

        case (
            ChannelNamePart3Message()
            | ChannelNamePart3Message2()
            | ChannelNamePart3Message3()
        ):
            await module._process_channel_name_message(3, message)
            await module._cache()

        # Memory messages
        case MemoryDataMessage():
            await module._process_memory_data_message(message, channel_offset)

        case MemoryDataBlockMessage():
            await module._process_memory_data_block_message(message, channel_offset)

        case _:
            pass
