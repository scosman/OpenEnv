---
status: draft
---

# Functional Spec: Reset Schema

## 1. Purpose

`GET /schema` publishes JSON schemas for `action`, `observation` and `state`. Nothing publishes what `reset()` accepts. `ResetRequest` is `extra="allow"` and the server forwards extra keys to the environment's `reset()` (filtered against its signature), so environments already take custom reset parameters (`task_id`, `problem_id`, `fen`, `split`/`index`, ...), but a client cannot discover them.

This project lets an environment declare its reset parameters as a `ResetRequest` subclass, `reset_cls`, and publishes that model's JSON schema as a `reset` entry on `/schema`. It follows the `state_cls` precedent (#1174) as closely as possible.

## 2. Out of Scope

- **Validation.** `reset_cls` is a published type hint only. How `/reset` and the WebSocket `reset` message parse, filter and forward keys is unchanged (§4).
- Deriving a reset schema automatically from the environment's `reset()` signature.
- Checking that `reset_cls` fields match the `reset()` signature, at runtime or via a shipped test helper.
- `openenv validate` changes (§6).
- Client changes: `EnvClient` has no schema method today and gets none.
- The Gradio web interface's reset controls.
- Adopting `reset_cls` in any `envs/` environment.
- A WebSocket schema message (none exists for the other schemas either).

## 3. `reset_cls` Parameter

- Type `Type[ResetRequest]`, default `ResetRequest`.
- Added as the **last** keyword parameter, after `state_cls`, to every factory that takes `state_cls`:
  - `HTTPEnvServer.__init__`
  - `create_app`
  - `create_fastapi_app`
  - `create_web_interface_app`
- Threaded through exactly as `state_cls` is: `create_app` passes it to whichever of the two app factories it calls; both pass it to `HTTPEnvServer`.
- Stored as the public attribute `HTTPEnvServer.reset_cls`, like `state_cls`.
- No existing call site changes behaviour or shifts a positional argument.

Typical use:

```python
class GitResetRequest(ResetRequest):
    task_id: str | None = Field(default=None, description="Task to load")

app = create_app(GitTaskEnvironment, GitAction, GitObservation, reset_cls=GitResetRequest)
```

## 4. Wire Behaviour

### 4.1 `GET /schema`

Response gains a fourth key:

| Key           | Value                                   |
|---------------|-----------------------------------------|
| `action`      | unchanged                               |
| `observation` | unchanged                               |
| `state`       | unchanged                               |
| `reset`       | `reset_cls.model_json_schema()`         |

- Always present from a server with this change. With no `reset_cls`, it is the base `ResetRequest` schema: `seed`, `episode_id`, `additionalProperties: true`.
- Generated per request, the same way the other three are.
- A subclass inherits `seed` and `episode_id`, so they appear in every published reset schema.
- The subclass's own `model_config` is published as-is. A subclass that sets `extra="forbid"` publishes `additionalProperties: false`, but the server does not enforce it (§4.2). This is the author's choice and is documented as a hint.
- The `/schema` route's description and its OpenAPI example gain `reset`.

### 4.2 `POST /reset` and WebSocket `reset` — unchanged

- The HTTP body model stays `ResetRequest`; the OpenAPI schema for `/reset` is unchanged.
- A body that does not match `reset_cls` (wrong type, missing field, extra key) is handled exactly as today. `reset_cls` never produces a 422 or an error frame.
- Keys are still filtered against the environment's `reset()` signature. A `reset_cls` field that `reset()` does not accept is still dropped silently (the existing behaviour, already documented in the Task API guide).

## 5. `SchemaResponse`

- Gains `reset: Optional[Dict[str, Any]]`, default `None`, description "JSON schema for reset parameters accepted by this environment".
- Optional so the model can describe a response from a server without this change. The server in this repo always fills it.

## 6. `openenv validate` — unchanged

The `schema_endpoint` criterion keeps requiring only `action`, `observation` and `state`.

`state_cls` needed no validator change because the `state` key was always present; only its contents changed. `reset` is a new key. Requiring it would fail `openenv validate` against any server on an older `openenv` (for example, a deployed Space pinned to a previous release). Reporting it without requiring it adds output that no one acts on. It can be added later if `reset` becomes required.

## 7. Documentation

Match existing verbosity; this is a small feature.

- **Docstrings** (HF doc-builder format) for `reset_cls` on the four factories, mirroring the `state_cls` entries.
- **`/schema` route description** lists `reset`.
- **`docs/source/guides/task-api.md`**, "Selecting a task in `reset()`": a short paragraph with a snippet showing a `ResetRequest` subclass passed as `reset_cls`, so clients can find `split`/`index` in `/schema`. It says the schema is not enforced.
- **CLI env template** `src/openenv/cli/templates/openenv_env/server/app.py`: the `GET /schema` line in the module docstring reads "Get action/observation/state/reset schemas".
- `docs/source/reference/core.md` already autodocs `ResetRequest` and `SchemaResponse`; no change.

## 8. Tests

New `tests/core/test_reset_schema.py`, modelled on `tests/core/test_state_schema_subclass.py`:

- A declared `reset_cls` publishes its own fields plus `seed` and `episode_id` under `/schema`'s `reset`.
- `create_app` publishes it with `ENABLE_WEB_INTERFACE` both on and off.
- With no `reset_cls`, `reset` is the base `ResetRequest` schema; `HTTPEnvServer.reset_cls is ResetRequest`.
- `action`, `observation` and `state` are unaffected.
- `/reset` is not validated against `reset_cls`: a body with a value of the wrong type for a `reset_cls` field, and a key `reset_cls` does not declare, both return 200 and reach `reset()` as they do today.
