---
name: eng-verify-before-done
description: Verify-before-done method: never claim code works or is fixed without evidence; name the check that proves it and say what was and was not run.
---
# Verify before saying done (adapted from the MIT-licensed verification-before-completion skill of obra/superpowers)
- Do not claim that code works, is fixed or is tested unless you ran it and saw the result. In chat you usually cannot run Luau: say so plainly.
- Name the exact check that proves the claim (the failing input, the assert, the thing to look at) and the output to expect; trace the changed path by hand against the original failing case.
- Compare the result with each requirement of the request, one by one, and list anything that is not met or not checked.
