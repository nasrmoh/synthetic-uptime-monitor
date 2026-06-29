
Data types we use in `Postgres`

```sql
SERIAL -- auto-incrementing integer, use for primary keys
INTEGER -- whole number
Text    -- variable length string, no size limit
BOOlean -- True / false
TIMESTAMPZ -- timestamp with timezone
```


### `CREATE TABLE`

``` sql
CREATE TABLE pizzas (
	id SERIAL PRIMARY KEY,
	name TEXT NOT NULL,
	price INTEGER NOT NULL,
	available BOOLEAN NOT NULL DEFAULT TRUE,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```



### Key constraints:
```
PRIMARY KEY --unique + not null, one per table
NOT NULL --required value
DEFAULT X -- value to use if none provided
```


## Foreign key

``` orders
CREATE TABLE orders (
	id SERIAL PRIMARY KEY,
	pizza_id INTEGER NOT NULL REFERENCES pizzas(id),
	quantity INTEGER NOT NULL,
	ordered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
`REFERENCES pizzas(id)` means that Postgres will reject any `pizza_id` that doesn't exist in the `pizzas` table. Meaning you can't order a pizza that doesn't exist


## Insert

```sql
INSERT INTO pizzas (name, price)
VALUES ('Margherita', 12);
```

to insert we list the columns we are providing, in the above case we are providing the `name` and `price` fields of the `pizzas` table


## Select


```sql

-- all columns
SELECT * FROM pizzas;

-- specific columns
SELECT name, price FROM pizzas;

-- with a filter
SELECT * FROM pizzas
WHERE available = true;

-- one row by id
SELECT * FROM pizzas
WHERE id = 1;
```

# Order By and Limit

```SQL
-- get the most recent 5 orders from one pizza
SELECT * FROM ORDERS
WHERE pizza_id = 1
ORDERB BY ordered_at DESC
LIMIT 5;
```


## CREATE INDEX

```SQL
CREATE INDEX indx_orders_pizza_time
ON orders(pizza_id, ordered_at DESC);
```








