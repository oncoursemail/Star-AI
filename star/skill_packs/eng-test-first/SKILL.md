---
name: eng-test-first
description: Test-first method for code requests: write the tests first, then the simplest code that passes, then refactor; reproduce a bug with a test before fixing it.
---
# Test-first (adapted from the MIT-licensed test-driven-development skills of obra/superpowers and addyosmani/agent-skills)
- Red: write the tests first, one behaviour each with a clear name, covering normal, edge and invalid input. They must fail against an empty stub.
- Green: write the simplest code that passes them and nothing the tests do not need. Refactor only while they still pass.
- A bug fix starts with a test that reproduces the bug.
- Show the tests as plain assert calls in a block that can run on its own, then the implementation, then how to run them. Say that you have not run them unless you did.
