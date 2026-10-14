Dart only applies type promotion to local variables and private final fields. `name` is a public, non-final field: another piece of code (or a subclass that overrides it with a getter) could change it between the check and the use, so the analyzer cannot prove it is still non-null and does not promote it to `String`.

Fix: copy the field into a local variable, check the local, then use the local:

```dart
int nameLength() {
  final n = name;
  if (n != null) return n.length;
  return 0;
}
```

Shorter: `return name?.length ?? 0;`.
