---
status: complete
---

# Phase 1: `reset_cls` and the `reset` entry on `/schema`

## Overview

Let an environment declare its reset parameters as a `ResetRequest` subclass (`reset_cls`) and publish that model's JSON schema as a `reset` entry on `GET /schema`. Mirrors the `state_cls` plumbing. Hint only: `/reset` and the WebSocket `reset` message are unchanged and never validate against `reset_cls`.

## Steps

1. `src/openenv/core/env_server/types.py`: add `reset: Optional[Dict[str, Any]] = Field(default=None, description="JSON schema for reset parameters accepted by this environment")` to `SchemaResponse`, after `state`.
2. `src/openenv/core/env_server/http_server.py`:
   - `HTTPEnvServer.__init__(..., state_cls: Type[State] = State, reset_cls: Type[ResetRequest] = ResetRequest)`; docstring entry after `state_cls`; `self.reset_cls = reset_cls`.
   - `get_schemas`: `reset=self.reset_cls.model_json_schema()`. Route description lists reset; OpenAPI example gains `"reset": {"type": "object", "properties": {"seed": {"type": "integer"}}}`.
   - `create_app(..., state_cls=State, reset_cls: Type[ResetRequest] = ResetRequest)`: pass `reset_cls=reset_cls` to both `create_web_interface_app` and `create_fastapi_app`; docstring entry.
   - `create_fastapi_app(..., state_cls=State, reset_cls: Type[ResetRequest] = ResetRequest)`: pass to `HTTPEnvServer`; docstring entry; "Schema" tag description and "Schema Access" feature bullet mention reset parameters.
   - `/reset` handler and WebSocket reset untouched.
3. `src/openenv/core/env_server/web_interface.py`: import `ResetRequest`; `create_web_interface_app(..., state_cls=State, reset_cls: Type[ResetRequest] = ResetRequest)`; pass to `create_fastapi_app`; docstring line in existing style.
4. `docs/source/guides/task-api.md`: in "Selecting a task in `reset()`", add the paragraph and `LatexOCRResetRequest` / `create_app(..., reset_cls=...)` snippet from architecture.md before "When `index` is omitted…".
5. `src/openenv/cli/templates/openenv_env/server/app.py`: docstring line -> `- GET /schema: Get action/observation/state/reset schemas`.

## Tests

New `tests/core/test_reset_schema.py` (fixtures: `EchoAction`, `EchoObservation`, `TaskResetRequest` with `task_id: int | None`, `RecordingEnvironment` recording reset kwargs at class level; `declared_client`, `default_client`).

- `TestDeclaredResetClass.test_create_app_publishes_reset_schema_in_both_modes`: parametrized over `ENABLE_WEB_INTERFACE`; `task_id` in `/schema["reset"]["properties"]`.
- `TestDeclaredResetClass.test_schema_publishes_subclass_and_base_fields`: reset properties are exactly `{"seed", "episode_id", "task_id"}`.
- `TestDeclaredResetClass.test_other_schemas_are_unaffected`: `action`, `observation`, `state` still carry their fields.
- `TestDeclaredResetClass.test_reset_is_not_validated_against_reset_cls`: `POST /reset` with `{"task_id": "not-an-int", "extra": "x"}` returns 200 and both keys reach `reset()` unchanged.
- `TestDefaultResetClass.test_schema_falls_back_to_base_reset_request`: `/schema["reset"] == ResetRequest.model_json_schema()`.
- `TestDefaultResetClass.test_server_defaults_to_base_reset_request`: `HTTPEnvServer(...).reset_cls is ResetRequest`.
