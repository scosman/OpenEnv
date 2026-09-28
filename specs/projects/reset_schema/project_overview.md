---
status: draft
---

# Reset Schema

Proposal: [huggingface/OpenEnv#1215](https://github.com/huggingface/OpenEnv/issues/1215) — add the `reset()` schema to `/schema`.

Today `/schema` returns only schemas for action, observation, and state. `ResetRequest` is `extra="allow"`, so a client can pass anything to `reset()`, but there's no way for a client to discover what's allowed.

## What to build

- Add a `reset` entry to the existing `/schema` endpoint, in parallel with `action`, `observation` and `state`.
- Add a `reset_cls` parameter, following the existing `action_cls` / `observation_cls` / `state_cls` convention. It is optional.
- No validation: `reset_cls` is a type hint that is published in the schema. It does not change how `reset()` requests are parsed or which keys reach the environment.

## Reference

A version of this was built in Seahaven ([Kiln-AI/Seahaven#33](https://github.com/Kiln-AI/Seahaven/pull/33)) as a namespaced `GET /seahaven/schemas`, written as if this proposal were already accepted upstream (`create_app(reset_cls=...)`, a `reset` key on `/schema`). Lessons from it may or may not apply here.
