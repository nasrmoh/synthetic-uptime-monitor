# Fetch Recent Results for one Target

```sql
SELECT * 
FROM check_results
WHERE target_id = :target_id
ORDER BY checked_at DESC
LIMIT :limit;
```
## Index Reasoning

We index by `(target_id, checked_at DESC)` instead of just using `target_id` alone because our most common query is one where we get the most recent results for a particular endpoint. Using an index like this allows PostgreSQL to very quickly locate the rows for a specific target while ensuring that PostgreSQL doesn't have to sort. 

