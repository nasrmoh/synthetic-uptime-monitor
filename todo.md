- [ ] Composite indexing on `check_result(target_id, checked at DESC)` left over as getting the syntax setup to have Alembic pickup automatically is a bit awkward.
- [ ] API-level validation (Pydantic `model_validator`) and a database CHECK
      constraint both enforce `timeout_seconds < interval_seconds` for
      endpoint targets. The DB constraint correctly rejects PATCH requests
      that would violate this (including partial updates the schema
      validator can't catch, since it only checks fields present in the
      payload). But the failure currently surfaces as an unhandled
      IntegrityError → raw 500, not a clear 4xx response. Catch
      IntegrityError in the PATCH route and return a readable 400/422
      instead.
- [ ] add a constraint to prevent invalid/unexpected values from being inserted into target data, need to define exactly what that constraint is
- [ ] `TargetDown` alert rule (`increase(checks_total{status="error"}[5m]) > 2`)
      measures total errors in a window, not consecutive errors. It can't
      distinguish 3 errors in a row from 3 scattered errors with successes
      in between, both trip the same threshold. Consider exposing our
      existing `current_failed_checks` value as a Prometheus gauge instead,
      it resets to zero on any success, giving a true "consecutive
      failures" signal. Requires a new metric and new call sites in the
      check-completion flow. Deferred to Phase 2, not justified for MVP
      scope.
 - [ ] `/targets/{target_id}/results` hardcodes limit=100 with no pagination.
      Decide: is 100 a permanent cap (document why) or does this need
      offset/cursor pagination before Phase 2? Revisit once real result
      volume is known.
- [ ] No format validation on TargetCreate/TargetUpdate: `url` accepts any
      string (not checked as a valid URL), `expected_status` accepts any
      int (not constrained to 100-599), `method` accepts any string (not
      checked against valid HTTP methods). Only cross-field constraint
      enforced is timeout_seconds < interval_seconds. Decide whether to
      add Pydantic field validators (e.g. HttpUrl, Field(ge=100, le=599),
      a Literal/enum for method) before Phase 2.
- [ ] TargetUpdate's checktime_lt_timeout_interval only validates when
      BOTH timeout_seconds and interval_seconds are present in the same
      PATCH request. A PATCH that updates only one of them isn't checked
      against the other's existing stored value, so an update could leave
      the row in a state where interval < timeout without either field
      individually looking invalid.
- [ ] Confirm `from pydantic.v1 import ConfigDict` in schemas.py is
      intentional. BaseModel and model_validator are imported from
      pydantic (v2); ConfigDict should likely also come from pydantic,
      not pydantic.v1.
- [ ] target_scanner only reconciles jobs based on enabled/disabled state
      (expected_ids vs current_ids). If a target's interval_seconds is
      changed via PATCH while it's already enabled and scheduled, the
      existing APScheduler job keeps its original interval, nothing
      currently detects or applies the change. Confirmed empirically:
      changing interval_seconds on a live target does not update its job.
      Fix options: (1) have target_scanner also compare each enabled
      target's stored interval_seconds against the corresponding job's
      current trigger interval and reschedule on mismatch, or (2) have the
      PATCH route itself call scheduler.reschedule_job() directly when
      interval_seconds changes. Option 1 keeps target_scanner as the
      single source of truth for scheduler state; option 2 is more
      immediate but couples the route to the scheduler.
- [ ] Consider moving this to an env var (${ALERT_WEBHOOK_URL}) to match how other secrets/config are handled elsewhere in the project, rather than hardcoding a URL directly into a tracked file.
- [ ] Base images unpinned (python:3.12-slim floating tag, observability stack on latest) — deliberate MVP scope decision, revisit before any real hardening pass.