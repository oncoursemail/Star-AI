Treat it like archaeology: understand first, change one thing at a time, and never risk the real player records.

1. Map before you move. Get the place into files (Rojo) so you have git history and search. Inventory every DataStore name and key pattern, every script that calls GetAsync/SetAsync/UpdateAsync, every _G value that ends up in saved data, and every RemoteEvent that changes it. Write down what you observed versus what you guess.
2. Capture current behaviour as characterization (golden master) tests: take copies of real saved records, run the existing load and save code on them in a test place, and record exactly what comes out. Those outputs are your oracle.
3. Put a seam around saving: move the load/save logic out of _G into one ModuleScript with load(player) and save(player), with no behaviour change. Check it against the characterization tests.
4. Add a schema version field. Version 1 is today's shape. Write a migration on load: if the record has no version or version 1, migrate it to version 2 by adding an empty pets table and keeping every existing field (never drop unknown fields). Save writes version 2.
5. Test the migration on copied real records in a test place or test universe, including empty, very old and odd records, before it ever touches the live game. Keep using UpdateAsync, session locking and BindToClose as before.
6. Ship the pets system on top only after the migration has run cleanly; keep old-format reading in place for a long time.

Don't rewrite the save system in one go; replace it piece by piece with the tests as your safety net.
