This happens because two threads touch the list. Make the method synchronized to fix it, or wrap the loop in
try/catch and ignore ConcurrentModificationException.
