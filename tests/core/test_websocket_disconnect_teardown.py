# SPDX-License-Identifier: BSD-3-Clause

"""
Tests that a clean websocket disconnect tears down without raising.

Clients (see [`~openenv.core.env_client.EnvClient`]) close their socket as soon
as a session ends, so the `websocket.close()` in each endpoint's `finally` block
usually runs against a peer that is already gone. Uvicorn raises
`ClientDisconnected` (an `OSError`) from the underlying send, and Starlette
re-raises it as `WebSocketDisconnect`. If that escapes the endpoint, uvicorn
logs a full traceback for what is an ordinary teardown.

Test coverage:
- `/ws` swallows the disconnect raised by its closing handshake
- `/mcp` swallows the disconnect raised by its closing handshake
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.routing import APIWebSocketRoute
from starlette.websockets import WebSocket

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "envs"))

from openenv.core.env_server.http_server import HTTPEnvServer
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import Action, Observation, State


# ============================================================================
# Test Fixtures - Minimal Environment and a Peer That Hangs Up
# ============================================================================


class MinimalEnvironment(Environment):
    """Minimal environment implementation for testing session teardown."""

    SUPPORTS_CONCURRENT_SESSIONS = True

    def reset(self, **kwargs) -> Observation:
        """Reset the environment."""
        return Observation(done=False, reward=None)

    def step(self, action: Action, **kwargs) -> Observation:
        """Execute an action."""
        return Observation(done=False, reward=None)

    @property
    def state(self) -> State:
        """Return current state."""
        return State(episode_id="teardown", step_count=0)


class DisconnectedPeer:
    """
    ASGI receive/send pair for a client that hangs up right after connecting.

    Sending the closing handshake fails with an `OSError`, which is what uvicorn
    raises (as `ClientDisconnected`) once the peer is gone; Starlette turns it
    into `WebSocketDisconnect` before the endpoint sees it.
    """

    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []
        self._incoming: List[Dict[str, Any]] = [
            {"type": "websocket.connect"},
            {"type": "websocket.disconnect", "code": 1000},
        ]

    async def receive(self) -> Dict[str, Any]:
        return self._incoming.pop(0)

    async def send(self, message: Dict[str, Any]) -> None:
        self.sent.append(message)
        if message["type"] == "websocket.close":
            raise OSError("Client is disconnected")


def make_websocket(peer: DisconnectedPeer, path: str) -> WebSocket:
    """Build a `WebSocket` bound to a peer that has already hung up."""
    scope = {
        "type": "websocket",
        "path": path,
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
    }
    return WebSocket(scope, peer.receive, peer.send)


def websocket_endpoint(
    app: FastAPI, path: str
) -> Callable[[WebSocket], Coroutine[Any, Any, None]]:
    """Return the handler registered for a websocket route."""
    for route in app.routes:
        if isinstance(route, APIWebSocketRoute) and route.path == path:
            return route.endpoint
    raise AssertionError(f"No websocket route registered at {path}")


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app exposing both websocket endpoints."""
    app = FastAPI()
    server = HTTPEnvServer(
        env=MinimalEnvironment,
        action_cls=Action,
        observation_cls=Observation,
    )
    server.register_routes(app)
    return app


# ============================================================================
# Clean Disconnect Teardown Tests
# ============================================================================


@pytest.mark.parametrize("path", ["/ws", "/mcp"])
def test_clean_disconnect_does_not_escape_endpoint(app: FastAPI, path: str) -> None:
    """
    A peer that hangs up first must not turn teardown into an ASGI error.

    The endpoint still attempts its closing handshake; the resulting
    `WebSocketDisconnect` belongs to the endpoint, not to uvicorn's error log.
    """
    peer = DisconnectedPeer()

    asyncio.run(websocket_endpoint(app, path)(make_websocket(peer, path)))

    assert peer.sent[-1]["type"] == "websocket.close", (
        "Endpoint should still attempt the closing handshake"
    )
