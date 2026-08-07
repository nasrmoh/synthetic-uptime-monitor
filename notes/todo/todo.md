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