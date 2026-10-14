`status` is **isolated** to the main actor because its class is `@MainActor`, but `refresh()` lives in a nonisolated
extension, so it runs outside the main actor and the Swift 6 data-race checker forbids the mutation.

Fix: isolate the method to the main actor. The `await` on `api.load()` still lets the network call run elsewhere:

```swift
extension StatusModel {
    @MainActor
    func refresh() async {
        status = await api.load()
    }
}
```

If the method must stay nonisolated, compute the value first and hop to the main actor only for the assignment:
`let value = await api.load(); await MainActor.run { self.status = value }`.
