No. The value from `$_GET['name']` is pasted into the SQL text, so a request like `name=' OR '1'='1` changes the query: this is SQL injection. Use a prepared statement with a placeholder so the value is sent separately from the SQL and is never parsed as SQL:

```php
$stmt = $pdo->prepare('SELECT score FROM players WHERE name = :name');
$stmt->execute(['name' => $_GET['name'] ?? '']);
$rows = $stmt->fetchAll();
```

Also create the PDO connection with `PDO::ATTR_EMULATE_PREPARES => false` and `PDO::ERRMODE_EXCEPTION`.
