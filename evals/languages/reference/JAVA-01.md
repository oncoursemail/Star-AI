The for-each loop uses the list's iterator. Calling `bullets.remove(b)` modifies the list behind the iterator's back
(a structural modification), and the **fail-fast** iterator detects it on the next `next()` call and throws
`ConcurrentModificationException`. It is not about threads.

Clean fix: `removeIf` (Java 8+), or remove through the iterator itself.

```java
bullets.removeIf(Bullet::isExpired);

// or
for (Iterator<Bullet> it = bullets.iterator(); it.hasNext(); ) {
    if (it.next().isExpired()) it.remove();
}
```
