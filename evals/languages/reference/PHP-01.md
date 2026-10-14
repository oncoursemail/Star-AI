`strpos('admin_bob', 'admin')` returns `0` because the match is at position 0, the start of the string. With the loose comparison `==`, PHP treats `0 == false` as true, so the name is allowed. Compare strictly with `=== false`, or better use `str_contains` (PHP 8.0+):

```php
if (!str_contains($name, 'admin')) {
    allow($name);
}
```
