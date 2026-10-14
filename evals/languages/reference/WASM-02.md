Your view points at a buffer that no longer exists. When the Rust `Vec` grows past the current linear memory, the allocator calls **memory.grow**. Growing a WebAssembly memory replaces `memory.buffer` with a new, larger `ArrayBuffer` and **detaches** the old one, so every typed-array view created over the old buffer becomes length 0 (or throws the detached ArrayBuffer error). The Vec may also have moved, so the old pointer is stale too.

The right pattern is to re-create the view from the current `wasm.memory.buffer` with a fresh pointer and length **every frame** (or after any call that may allocate):

```js
function frame() {
  world.step(1 / 60);
  const pos = new Float32Array(wasm.memory.buffer, world.positions_ptr(), world.len());
  draw(pos);
  requestAnimationFrame(frame);
}
```
Creating a view is cheap (no copy). Alternatively reserve capacity up front (`Vec::with_capacity`) or set a larger initial memory to make growth rare, but still never keep views across allocating calls.
