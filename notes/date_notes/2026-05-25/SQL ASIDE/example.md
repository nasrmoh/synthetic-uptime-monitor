```SQL
CREATE TABLE pizzas (
	id SERIAL PRIMARY KEY,
	name TEXT NOT NULL,
	price INTEGER NOT NULL,
	available BOOLEAN NOT NULL default true,
	created_at TIMESTAMPTZ NOT NULL default now()
);
```


```
CREATE TABLE orders (
	id SERIAL PRIMARY KEY,
	pizza_id INTEGER NOT NULL references pizzas(id),
	quantity INTEGER NOT NULL,
	ordered_at TIMESTAMPTZ NOt NUll default now()
);
```


now we'll insert in some tables


```sql
INSERT INTO pizzas (name, price)
VALUES ('Margherita', 12), ('Pepperoni', 15), ('Veggie', 10), ('Hawaiian' ,11);
```


now we set an order for hawaiian

```
INSERT INTO orders (pizza_id, quantity)
VALUES (2, 4), (3, 1), (4, 4), (1, 1);
```



query to fetch all orders for a specific pizza, lets do hawaiian which has a id of 3


```
SELECT * FROM Orders
WHERE pizza_id = 3;
```

```
INSERT INTO orders (pizza_id, quantity)
VALUES (3, 2), (3, 4), (3, 10), (3, 11), (3, 45);
```


```
SELECT * FROM Orders
WHERE pizza_id = 3
ORDER BY ordered_at DESC
LIMIT 3;
```


```
CREATE INDEX indx_orders_pizza_time
ON orders(pizza_id, ordered_at DESC);
```








