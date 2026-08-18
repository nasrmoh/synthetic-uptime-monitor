# SQLAlchemy `relationship()`

## Three Way Split

`ForeignKey` defines the relationship in the database

`relationship()` defines the relationship for the Python Objects. It doesn't create foreign keys instead it reads already existing foreign keys

`back_populates` connects two python-side attributes together so SQLAlchemy knows they represent the same relationship


Here are our SQLAlchemy schemas

``` python
class EndpointTarget(Base):  
    __tablename__ = "endpoint_target"  
    id: Mapped[int] = mapped_column(primary_key=True)  
    url: Mapped[str]  
    method: Mapped[str]  
    timeout_seconds: Mapped[int]  
    interval_seconds: Mapped[int]  
    failure_threshold: Mapped[int]  
    expected_status: Mapped[int]  
    enabled: Mapped[bool] = mapped_column(default=True)  
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())  
    updated_at: Mapped[Optional[datetime]]  
    results: Mapped[list["CheckResult"]] = relationship(back_populates="target")
```


``` python
class CheckResult(Base):  
    __tablename__ = "check_result"  
    id: Mapped[int] = mapped_column(primary_key=True)  
    status_code: Mapped[int]  
    error_class: Mapped[Optional[str]]  
    target_id: Mapped[int] = mapped_column(ForeignKey("endpoint_target.id"))  
    checked_at: Mapped[datetime] = mapped_column(server_default=func.now())  
    latency_ms: Mapped[int]  
    target: Mapped["EndpointTarget"] = relationship(back_populates="results")
```

for an instance of `CheckResults` say `check_result` and an instance of `EndpointTarget` say `endpoint_target` then `check_result.target_id` will reference `endpoint_target.id`. Now SQLAlchemy can infer the relationship

`EndpointTarget` is the one side

`CheckResult` is the many side

> One endpoint target can hold many check results



## Where Does the Foreign Key Belong?

the foreign key belongs on the many side. That is `CheckResult` has a foreign key to `EndpointTarget`:

```python
target_id: Mapped[int] = mapped_column(ForeignKey("endpoint_target.id"))
```

In database terms:
`check_results.target_id -> endpoint_target.id`


In python terms

`target.results`
- all the results for a given endpoint target


`result.target`
- for this result, what endpoint does it belong to?



## What `back_populates` syncs


The following lines are linked together
   
```python
results: Mapped[list["CheckResult"]] = relationship(back_populates="target")
target: Mapped["EndpointTarget"] = relationship(back_populates="results")
```

This tells SQLAlchemy that `EndpointTarget.results` and `CheckResult.target` are two "views" of the same relationship

`result.target = endpoint`
- this will make `endpoint.results` contain the given result


Likewise
`endpoint.results.append(result)`
- this will make `result.target` be set to `endpoint`

Database correctness still comes from the Foreign key constraints.



## Lazy Loading and the N+1 seam

`target.results` will not immediately fetch rows. But it will load when the attribute is accessed. 

So the following line could trigger a database query:
- `target.results`


This is a problem if this is our main way of querying. If an endpoint has millions of results than a simple attribute access could take a lot of time to complete instead:

`GET /targets/{target_id}/results`  should not rely on:

`target.results`

And then slicing the returned table

Instead we should use a query that is bounded


```SQL
SELECT *
FROM check_result
WHERE target_id=:target_id
ORDERED BY checked_at DESC
LIMIT :limit;
```

With this we can even use an index to make query easier

```sql
CREATE INDEX ...
ON check_result (target_id, checked_at DESC);
```


## `checked_at`


for `CheckResult.checked_at` uses:

``` python
checked_at: Mapped[datetime] = mapped_column(server_default=func.now())  
```
- this means the database assigns the `checked_at` value at insertion time. So it isn't necessary to pass a value for `checked_at` PostgreSQL will handle it. 

## `error_class`


`error_class` is nullable:

``` python
error_class: Mapped[Optional[str]]
```
This means that `NULL` would represent no error

Then successful checks should have:

`error_class IS NULL`


A failed check can have values like timeout, connection error, DNS error, or status mismatch.

Later failure queries can rely on:

`WHERE error_class IS NOT NULL`

## Main Takeaway


`ForeignKey("endpoint_target.id")` is the database relationship
`relationship(backpopulates="...")` is the Python object relationship.

Foreign key lives on `CheckResult`. The relationship is convenient, but our database reads shouldn't use it. 


## Side Note

`relationship()` can also model self-referential relationships where a class points back to itself.
































