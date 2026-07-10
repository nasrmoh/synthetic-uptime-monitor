
**`db.add(check_result)`**: registers the object with the session. Does not touch the database. Marks it as pending.

**`db.flush()`**: sends the SQL (INSERT) to the database, inside the current transaction. Not permanent yet, a rollback undoes it. This is what assigns the real `id` from Postgres.

**`db.commit()`**: finalizes the transaction. Flushes first if needed, then makes the change permanent and visible to other connections. Can't be rolled back after this.

Typical order: `add()` → `commit()` for a simple insert. Use `flush()` alone only if you need the generated `id` mid-transaction before deciding to commit.