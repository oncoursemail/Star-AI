Don't mark it done. In a matching decompilation the oracle is the byte-identical rebuild: the project's build must produce exactly the original ROM (the CI compares the checksum), so a function only counts as matching when every instruction is the same. "The game runs fine" only shows the code is roughly equivalent; it does not match yet.

What to do:

- Check the basics first: the right compiler and compiler flags for that file (for N64 games usually IDO with -O2 or -g), and that types and signatures of the callees match the originals. Wrong types often cause swapped registers.
- Register allocation and branch order usually move when you change the order of statements, introduce or remove a temporary variable, merge or split an expression, or turn a `for` into a `while`. Try these one at a time and watch objdiff after each build.
- Upload the function to decomp.me so others can try, and run decomp-permuter on it: it generates many random variants of your C and scores them against the target.
- If it still won't match after a fair effort, commit it guarded as NON_MATCHING (the project's non-matching switch) with the original assembly still used for the build, and note what differs. That is an honest fallback; marking it as matching would break the ROM checksum and mislead everyone after you.
