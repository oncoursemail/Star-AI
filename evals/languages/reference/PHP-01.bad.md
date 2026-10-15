strpos is case sensitive, so it misses the name. Use stripos and then use `!strpos(...)` to check:

```php
if (!stripos($name, 'admin')) { allow($name); }
```
