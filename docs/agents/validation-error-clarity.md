# Validation errors: what, why and repair

Existing predicates and exception types stay unchanged. Messages identify
the rejected field, permitted type/range/choices, and a next step. No raw user
input is echoed (not even 40 characters); optional metadata describes only
length or primitive type. All updated error messages are at most 200 characters.

## Old → new (45 messages)

| Module | Old | New (safe shape is not an input echo) |
| --- | --- | --- |
| `star/agent_resource_planner.py` | `Invalid resource pool id` | Invalid resource pool id: id must start alphanumeric and contain 1-80 letters, digits, dots, hyphens or underscores (got [safe input shape]). Choose a valid id. |
| `star/agent_resource_planner.py` | `Invalid memory capacity` | Invalid memory capacity: memory_mib must be an integer between 1 and 2000000 MiB. Set a supported capacity. |
| `star/agent_resource_planner.py` | `Invalid CPU capacity` | Invalid CPU capacity: cpu_threads must be an integer between 1 and 4096. Set a supported capacity. |
| `star/agent_resource_planner.py` | `Invalid worker concurrency` | Invalid worker concurrency: max_jobs must be an integer between 1 and 8. Reduce concurrency. |
| `star/agent_resource_planner.py` | `Unknown trust boundary` | Unknown trust boundary: boundary must be private or cloud. Select a supported boundary. |
| `star/agent_resource_planner.py` | `Invalid worker id` | Invalid worker id: worker id and pool_id must be 1-80 character valid identifiers. Correct the invalid id. |
| `star/agent_resource_planner.py` | `Invalid model slot count` | Invalid model slot count: slots must be an integer between 1 and 8. Set a supported slot count. |
| `star/agent_resource_planner.py` | `Invalid worker capabilities` | Invalid worker capabilities: capabilities must be a frozenset of 1-80 character identifiers. Fix invalid names or type. |
| `star/agent_resource_planner.py` | `Invalid demand task id` | Invalid demand task id: task_id must be a valid 1-80 character identifier. Match a planned task. |
| `star/agent_resource_planner.py` | `Invalid memory demand` | Invalid memory demand: memory_mib must be an integer between 1 and 2000000 MiB. Reduce demand. |
| `star/agent_resource_planner.py` | `Invalid CPU demand` | Invalid CPU demand: cpu_threads must be an integer between 1 and 4096. Reduce demand. |
| `star/agent_resource_planner.py` | `Invalid task capabilities` | Invalid task capabilities: capabilities must be a frozenset of 1-80 character identifiers. Fix invalid names or type. |
| `star/agent_resource_planner.py` | `Invalid priority` | Invalid priority: priority must be an integer between -100 and 100. Choose a supported value. |
| `star/agent_resource_planner.py` | `Explicit boolean permissions required` | Explicit boolean permissions required: interactive and allow_cloud must both be bool. Use True or False. |
| `star/agent_resource_planner.py` | `External-provider consent must be explicit` | External-provider consent must be explicit: enable_cloud must be bool. Use True or False. |
| `star/agent_resource_planner.py` | `Invalid or excessively large plan` | Invalid or excessively large plan: plan must be TaskPlan with no more than 32 tasks. Supply a valid smaller plan. |
| `star/agent_resource_planner.py` | `Resource planner only admits read-only tasks` | Resource planner only admits read-only tasks: plan.tasks must not request writes. Remove mutations or use an authorized executor. |
| `star/agent_resource_planner.py` | `Every task requires exactly one matching demand` | Every task requires exactly one matching demand: demands must match the plan task ids and each TaskDemand.task_id. Supply one demand per task. |
| `star/agent_resource_planner.py` | `Duplicate resource pool` | Duplicate resource pool: ResourcePool.id must be unique. Rename or remove duplicate pools. |
| `star/agent_resource_planner.py` | `Duplicate model worker` | Duplicate model worker: ModelWorker.id must be unique. Rename or remove duplicate workers. |
| `star/agent_resource_planner.py` | `Worker references an unknown resource pool` | Worker references an unknown resource pool: worker.pool_id must reference an existing ResourcePool.id. Supply or correct its pool. |
| `star/agent_resource_planner.py` | `Unknown task status` | Unknown task status: completed, running and finished ids must exist in plan.tasks. Remove unknown ids. |
| `star/agent_resource_planner.py` | `Contradictory task statuses` | Contradictory task statuses: task ids must occur in only one of completed, running and finished. Resolve the overlap. |
| `star/agent_resource_planner.py` | `Unknown running model worker` | Unknown running model worker: running worker ids must match ModelWorker.id. Correct the mapping. |
| `star/agent_resource_planner.py` | `Running above the plan's concurrency limit` | Running above the plan's concurrency limit: number of running tasks must not exceed plan.max_parallel. Reduce assignments. |
| `star/agent_resource_planner.py` | `Running assignments exceed declared capacity or permissions` | Running assignments exceed declared capacity or permissions: running assignments must fit pool RAM, CPU, job slots and consent. Reduce reservations. |
| `star/agent_skills.py` | `SKILL.md needs YAML frontmatter` | SKILL.md needs YAML frontmatter: SKILL.md must start with a '---' header. Add a valid YAML header. |
| `star/agent_skills.py` | `SKILL.md frontmatter is invalid or too long` | SKILL.md frontmatter is invalid or too long: YAML header must end with '---' within 8000 characters. Repair the header. |
| `star/agent_skills.py` | `Invalid skill name` | Invalid skill name: name must be lowercase letters and digits separated by single hyphens (got [safe input shape]). Choose a listed name. |
| `star/agent_skills.py` | `Skill unavailable; list the catalog first` | Skill unavailable; list the catalog first: name must exist in the catalog. Call SkillLibrary.list() and select a name. |
| `star/agent_skills.py` | `Invalid reference path` | Invalid reference path: path must be forward-slash relative text at most 300 characters (got [safe input shape]). Use references/file.md. |
| `star/agent_skills.py` | `Only skill references and text assets may be read` | Only skill references and text assets may be read: path must be under references/ or assets/ with .md, .txt, .json, .yaml or .yml extension. Fix the path. |
| `star/agent_skills.py` | `Reference is unavailable or exceeds limits` | Reference is unavailable or exceeds limits: path must reference an existing regular file within the skill, at most 64000 bytes. Choose a listed reference. |
| `star/asset_forge.py` | `Poly Haven response exceeded the metadata limit` | Poly Haven response exceeded the metadata limit: metadata response must fit 160000 bytes. Refine the search or retry. |
| `star/asset_forge.py` | `Poly Haven returned invalid JSON` | Poly Haven returned invalid JSON: metadata must be a JSON object. Retry the catalog search. |
| `star/asset_forge.py` | `Poly Haven returned unexpected metadata` | Poly Haven returned unexpected metadata: metadata must be a JSON object. Retry with valid catalog data. |
| `star/asset_forge.py` | `search query must have 1–100 characters` | search query must have 1–100 characters: query must be nonblank text in that range (got [safe input shape]). Enter a shorter search phrase. |
| `star/asset_forge.py` | `asset type must be models, textures, or hdris` | asset type must be models, textures, or hdris: kind must be one of those choices. Select a supported type. |
| `star/asset_forge.py` | `Poly Haven search response lacks ranked results` | Poly Haven search response lacks ranked results: results must be a JSON list. Retry or refine the catalog query. |
| `star/asset_forge.py` | `unknown style preset` | unknown style preset: style must be classic-studs, stylized-fantasy, grounded-realism or anime-toon (got [safe input shape]). Choose one. |
| `star/asset_forge.py` | `unknown biome` | unknown biome: biome must be temperate, desert, alpine or alien. Choose one. |
| `star/autonomous_research.py` | `Invalid research project` | Invalid research project: project must be nonblank text of 1-100 characters (got [safe input shape]). Choose a shorter label. |
| `star/autonomous_research.py` | `Invalid research objective` | Invalid research objective: objective must be 2-12000 nonblank text characters. Edit the question. |
| `star/autonomous_research.py` | `Invalid research completion status` | Invalid research completion status: status must be completed, failed or cancelled. Choose one of these values. |
| `star/autonomous_research.py` | `Invalid research metric` | Invalid research metric: book must be EvidenceBook and elapsed_ms must be between 0 and 4000000. Correct the metrics. |

## Traced surfaces

1. `ResourcePool`, `ModelWorker`, `TaskDemand` and
   `preview_assignments` propagate exceptions to their Python caller;
   planner validation does not execute tasks.
2. `SkillLibrary` and asset forge inputs are surfaced through
   `star/agent.py` intelligence-tool error serialization, which passes the
   exception type/text into the model's tool result.
3. `begin_research` and `finish_research` are called from
   `star/team_service.py`. `desktop_core.run_task` re-raises failures;
   `react_shell.py` displays formatted exception details in desktop errors.
4. `star/redact.py` remains the general credential scrubber, but these
   messages do not copy user values into exceptions in the first place.

`tests/test_validation_message_clarity.py` drives the actual paths with
ordinary invalid and synthetic hostile 5,000-character inputs, plus
nonregression positives. No network, GPU, Studio or credential store required.
