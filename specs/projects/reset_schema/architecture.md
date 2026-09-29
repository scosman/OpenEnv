---
status: draft
---

# Architecture: Reset Schema

Small, additive change that mirrors `state_cls` (#1174) line for line. No new modules. Everything fits in this doc; no component designs.

## 1. Changes by File

### `src/openenv/core/env_server/types.py`

`SchemaResponse` gains a fourth field after `state`:

```python
reset: Optional[Dict[str, Any]] = Field(
    default=None,
    description="JSON schema for reset parameters accepted by this environment",
)
```

`ResetRequest` is unchanged (stays `extra="allow"`).

### `src/openenv/core/env_server/http_server.py`

`ResetRequest` is already imported from `.types`.

**`HTTPEnvServer.__init__`**
- New last parameter `reset_cls: Type[ResetRequest] = ResetRequest`, after `state_cls`.
- Docstring entry after `state_cls`, HF doc-builder format:
  ```
  reset_cls (`Type[ResetRequest]`, *optional*, defaults to `ResetRequest`):
      The `ResetRequest` subclass describing this environment's reset parameters.
      Published as the `reset` entry of `/schema`. It is not used to validate
      reset requests.
  ```
- `self.reset_cls = reset_cls` next to `self.state_cls = state_cls`.

**`/schema` route (`get_schemas` in `register_routes`)**
- Add `reset=self.reset_cls.model_json_schema()` to the `SchemaResponse(...)` call.
- Route `description`: "Get JSON schemas for actions, observations, state, and reset parameters in a single response." and add a bullet `- **reset**: JSON schema for reset parameters accepted by this environment`.
- OpenAPI `example`: add `"reset": {"type": "object", "properties": {"seed": {"type": "integer"}}}` after `state`.

**`/reset` route and `reset_handler`, WebSocket reset**: no change. They keep `ResetRequest`. Do not touch `Body(default_factory=ResetRequest)`.

**`create_app`, `create_fastapi_app`**
- New last parameter `reset_cls: Type[ResetRequest] = ResetRequest`.
- Pass `reset_cls=reset_cls` everywhere `state_cls=state_cls` is passed (`create_app` → `create_web_interface_app` and `create_fastapi_app`; `create_fastapi_app` → `HTTPEnvServer`).
- Docstring entry mirroring the existing `state_cls` entry in each:
  ```
  reset_cls (`Type[ResetRequest]`, *optional*, defaults to `ResetRequest`):
      The `ResetRequest` subclass describing this environment's reset parameters,
      published as the `reset` entry of `/schema`. Not used for validation.
  ```
- `create_fastapi_app`'s `openapi_tags` "Schema" description: "JSON Schema endpoints for actions, observations, state, and reset parameters". The "Schema Access" feature bullet in the app description: "Retrieve JSON schemas for actions, observations, state, and reset parameters".

### `src/openenv/core/env_server/web_interface.py`

- `create_web_interface_app`: new last parameter `reset_cls: Type[ResetRequest] = ResetRequest`; pass `reset_cls=reset_cls` to `create_fastapi_app`.
- Import `ResetRequest` from `.types` alongside `State`.
- Docstring entry in that function's existing (non-HF) style, matching its `state_cls` line:
  `reset_cls: The ResetRequest subclass describing reset parameters. Published as the reset entry of /schema; not used for validation. Defaults to ResetRequest.`

### `docs/source/guides/task-api.md`

In "Selecting a task in `reset()`", after the paragraph on signature filtering and before "When `index` is omitted…", add:

````markdown
To let clients discover these parameters, declare them on a `ResetRequest` subclass and pass it as `reset_cls`. `/schema` publishes it under `reset`. It is a hint only: requests are not validated against it.

```python
class LatexOCRResetRequest(ResetRequest):
    split: str = "test"
    index: Optional[int] = None

app = create_app(
    LatexOCREnvironment,
    LatexOCRAction,
    LatexOCRObservation,
    env_name="latex_ocr_env",
    reset_cls=LatexOCRResetRequest,
)
```
````

Defaults and names match the guide's `LatexOCREnvironment.reset()` and its earlier `create_app` example.

### `src/openenv/cli/templates/openenv_env/server/app.py`

Module docstring line `- GET /schema: Get action/observation schemas` → `- GET /schema: Get action/observation/state/reset schemas`. No code change.

## 2. Design Notes

- **Why subclass `ResetRequest`:** inherits `seed`/`episode_id`, so every published reset schema carries the base fields. Matches `Type[State]`.
- **Why the body model stays `ResetRequest`:** using `reset_cls` in `Body(...)` would make FastAPI validate and 422. The spec says hint only.
- **Schema generated per request:** same as the other three entries. A `reset_cls` pydantic cannot schema-fy fails `/schema` with a 500, same as a bad `state_cls` today. No startup check.
- **Keyword position:** last, after `state_cls`, so positional callers are unaffected. Callers of `create_web_interface_app` that pass positionally stop at `concurrency_config`, so no conflict.

## 3. Error Handling

None new. No new raises, no logging.

## 4. Tests: `tests/core/test_reset_schema.py`

Module docstring: one-line purpose (reset parameters published on `/schema`, never enforced). Structure mirrors `tests/core/test_state_schema_subclass.py`.

Fixtures:
- `EchoAction(Action)`, `EchoObservation(Observation)`: minimal.
- `TaskResetRequest(ResetRequest)`: `task_id: int | None = Field(default=None, description="Task to load")`.
- `RecordingEnvironment(Environment[...])`: `reset(self, seed=None, episode_id=None, task_id=None, **kwargs)` records received kwargs on a module-level or class-level list (the HTTP handler creates a fresh env per request), returns `EchoObservation`. `step` returns `EchoObservation`. `state` returns `State()`.
- `declared_client`: `create_fastapi_app(..., reset_cls=TaskResetRequest)` in a `TestClient`.
- `default_client`: same without `reset_cls`.

`class TestDeclaredResetClass`:
1. `test_create_app_publishes_reset_schema_in_both_modes` — parametrized `web_enabled` over `ENABLE_WEB_INTERFACE`; `"task_id" in /schema["reset"]["properties"]`.
2. `test_schema_publishes_subclass_and_base_fields` — `set(properties) == {"seed", "episode_id", "task_id"}`.
3. `test_other_schemas_are_unaffected` — `action`, `observation`, `state` still carry their fields.
4. `test_reset_is_not_validated_against_reset_cls` — `POST /reset` with `{"task_id": "not-an-int", "extra": "x"}` returns 200; the recorded kwargs show `task_id == "not-an-int"` and `extra == "x"` reached `reset()`.

`class TestDefaultResetClass`:
5. `test_schema_falls_back_to_base_reset_request` — `/schema["reset"] == ResetRequest.model_json_schema()`.
6. `test_server_defaults_to_base_reset_request` — `HTTPEnvServer(...).reset_cls is ResetRequest`.

Existing tests need no changes; none assert the exact key set of `/schema`.

## 5. Validation

Lint and tests per CLAUDE.md: `usort check`, `ruff format --check`, `ruff check` on `src/ tests/`; `PYTHONPATH=src:envs uv run pytest tests/core/ -v`. The full suite should still pass. No doc stubs change (`sync_env_docs.py` is for env READMEs only).
