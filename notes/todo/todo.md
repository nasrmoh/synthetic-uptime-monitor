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