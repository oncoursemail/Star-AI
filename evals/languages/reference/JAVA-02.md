`Integer` is an object, and `==` on objects compares **references** (identity), not values. Autoboxing calls
`Integer.valueOf`, which returns objects from a **cache** for values in -128..127, so both 127s are the same object.
128 is outside the cache, so two different objects are created and `==` is false.

Compare values with `equals` (or `Objects.equals` if either can be null), or use primitive `int`:

```java
Integer a = 128, b = 128;
boolean same = a.equals(b);          // true
boolean safe = Objects.equals(a, b); // true, null-safe
int x = 128, y = 128;                // primitives compare by value with ==
```
