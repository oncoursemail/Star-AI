`-pthread` builds use **shared Wasm memory**, which is a `SharedArrayBuffer`. Browsers only expose `SharedArrayBuffer` when the page is **cross-origin isolated** (a Spectre mitigation). `emrun` sends the needed headers; your host does not, so the global is undefined.

Send two headers on the HTML page (and the worker scripts): `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`. As server config:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```
(`credentialless` is an alternative COEP value that is easier with third-party images.) With COEP, every cross-origin resource you load must allow it (CORS or a `Cross-Origin-Resource-Policy` header), or it will be blocked. Check `self.crossOriginIsolated` in the console: it must be `true`.

If your host or game portal cannot set headers, build a single-threaded version without `-pthread` (or use a service-worker header shim as a stopgap).
