Data stores have per-minute request budgets and size limits, and requests that exceed them are throttled and return error codes [1]. Wrap every call in pcall, retry a failed request after a growing delay, and spread out and reduce the requests you make [2].

---
**Sources retrieved by STAR** (official documentation)

1. [Data store error codes and limits](https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits) · cited
2. [Best practices for data stores](https://create.roblox.com/docs/cloud-services/data-stores/best-practices) · cited
