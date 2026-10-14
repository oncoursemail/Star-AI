This is an analyzer bug in Dart null safety. Make `name` dynamic so the check is skipped:

```dart
dynamic name;
```
