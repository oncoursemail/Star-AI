It is a strong reference cycle (retain cycle). `GameScene` strongly owns the closure through `onTick`, and the closure
captures `self` strongly, so each keeps the other's reference count above zero and ARC never deallocates them.

Break it with a capture list that captures `self` weakly:

```swift
onTick = { [weak self] in
    guard let self else { return }
    self.score += 1
}
```

`[unowned self]` also breaks the cycle but crashes if the closure runs after the scene is gone, so prefer `weak`.
Instruments' Leaks tool or Xcode's Memory Graph Debugger shows such cycles.
