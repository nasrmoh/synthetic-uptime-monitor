## What would break if Redis went down right now, and what still works because Postgres exists?

- if Redis is down we won't be able to cache any of our most recent values
- But the values are still stored in postgres, all we lose is the quick access to data that we already expect to become stale quickly. 
- In respect to the app all main functionality still works. Targets can still be created and configured. Check results are still collected and persisted in Postgres. We have full CRUD capability. 
- for our endpoint `/ready` reports that services are unavailable but `/health` reports that the app is still reachable
- For an MVP I think this is acceptable as Redis' entire purpose is to store data we expect to go stale very quickly. Its entire purpose is to act as a easier access layer for data that we already store. 




