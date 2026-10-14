# Offline Roblox API-name checker

`star.roblox_api_checker` is a standalone, manually invoked checker for common misspelled Roblox
class, service and member names in Luau. STAR does **not** run it automatically
or change generated code: the default app behavior is unchanged.

## Get the official Full API dump

Use an installed Roblox Studio executable to produce the local dump:

```text
RobloxStudioBeta.exe --fullApi Full-API-Dump.json
```

The official instructions are in the
[Roblox Studio command-line reference](https://create.roblox.com/docs/studio/command-line-interface#api-dump).
Use `--fullApi` for the v1 **Full-API-Dump.json** format; `--apiV2` produces
a different schema and is not accepted. The actual dump is **not committed**.
Regenerate it after Studio updates to avoid stale or missing names.

## Use from Python

```python
from star.roblox_api_checker import check_luau_api, load_api_dump

api = load_api_dump("Full-API-Dump.json")  # Explicit local file path.
source = 'local p = Instance.new("Part")\np:Destry()'
for finding in check_luau_api(source, api):
    print(finding.line, finding.rule_id, finding.class_name,
          finding.name, finding.suggestion)
```

Findings report the 1-based source line, a rule ID (
`unknown-class`, `unknown-service` or `unknown-member`), the known receiver class when
applicable, the misspelling and the nearest existing spelling. Suggestions
are *spelling candidates*, not validated replacements.

The checker follows superclass inheritance, infers simple variables from
`Instance.new("Class")` and `game:GetService("Service")`, and validates direct
method calls and property assignments. It ignores comments, interpolated
or long string contents, dynamic constructor arguments, unknown receiver types,
property reads, and chained or aliased values. It is intentionally **not**
a type-flow analyzer: it does not establish whether a real member is
scriptable, writable, deprecated or correctly called. Ambiguous dynamic
children and lexical scope shadowing require a full language server.
Tests use only a small, hand-written fixture; no network, GPU, keyring,
Studio executable or production dump is required.

## Choice of validator

| Approach | License / cost | Definition upkeep | Reason |
| --- | --- | --- | --- |
| Official Roblox Studio `--fullApi` dump + this Python checker | Studio is proprietary under Roblox terms; no extra checker dependency or fee | User regenerates local dump after Studio changes | **Chosen**: authoritative input, deterministic offline tests, small opt-in surface |
| [Selene](https://github.com/Kampfkarren/selene) with `std = "roblox"` | MPL-2.0; free and open source | Roblox std refreshes automatically, normally requiring internet for first download | Wider linting is useful, but adds a binary and a definition-update workflow |
| [luau-lsp](https://github.com/JohnnyMorganz/luau-lsp) | MIT; free and open source | Roblox type-definition files or Rojo workspace integration need ongoing updates | Richer type analysis but substantial language-server integration beyond this small checker |

The dump is obtained directly from Roblox Studio rather than redistributing
a proprietary engine API snapshot or fetching data while validating code.
