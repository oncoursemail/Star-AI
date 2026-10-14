It is mostly fine, but to be safe use addslashes on the name before putting it into the query:

```php
$name = addslashes($_GET['name']);
```
