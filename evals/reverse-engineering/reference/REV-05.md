The standard method is controlled experiments plus a round-trip test.

1. Collect many saves and keep the originals untouched. Open them in a hex editor (ImHex or 010 Editor work well; xxd for quick dumps).
2. Look for structure: a magic number or ID string at the start, a version field, a header with sizes or offsets, repeated record sizes, text strings. Check endianness with a value you know (gold = 1000 appears as E8 03 in little endian).
3. Make controlled changes: save, change only one thing in the game (spend 1 gold, move one unit), save again, and diff the two files. The bytes that changed are your field. Repeat for each field you care about.
4. Watch for checksums and compression: if the end of the file changes on every save, or the whole file changes after a tiny edit, there is probably a CRC or compressed data. Identify it (try common CRCs, look for zlib headers) before editing anything.
5. Write it down as you go: a spec with offset, size, type, meaning and confidence for each field (a small wiki page or a Kaitai Struct file). Mark unknown regions as unknown rather than guessing.
6. Prove the parser: write a reader and a writer together and run a round trip on every sample: read a file, write it back without changes, and check the output is byte for byte identical. Then make an edit with your tool, load it in the game, and confirm the game shows the change. Projects like OpenRCT2, OpenTTD and fheroes2 rely on the same discipline: real original files as test data.
