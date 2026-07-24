# Open Question — Historical check results vs. changing target configuration
**Question:** What should happen to historical check results when a target's
monitoring configuration changes?

**Why it matters:** Historical rows store the observed status code, but their
success or failure may be interpreted using the target's current
`expected_status`. If `expected_status` is edited after checks were recorded,
past rows get reinterpreted under a rule that didn't apply when they were
actually checked.

**Current MVP decision:** Consumers use the current target configuration.
Historical reclassification is acceptable for now because the system
primarily presents recent operational state.

**Possible future approaches:**
- Prevent changes to identity-defining configuration.
- Delete or archive prior results after a significant change.
- Treat a significant change as a new target, and find some way to link
  replacement targets so their history can still be followed.
- Preserve the configuration that applied when each check ran.

**Deferred because:** The additional historical accuracy is not necessary for
the current MVP.

---

**Related question:** which target fields describe the *identity* of a
monitor, and which are merely adjustable operating settings? Changing an
interval probably doesn't create a meaningfully new target; changing the URL
probably does. No answer needed yet, but the uncertainty itself is worth
recording, since it's the same ambiguity a "sufficient difference" patch
strategy would eventually have to resolve.