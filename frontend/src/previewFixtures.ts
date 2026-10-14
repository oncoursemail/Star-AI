/** PREVIEW FIXTURES — scripted events for design review in a normal browser.
 *
 *  These never run in STAR Desktop: Desktop.tsx only loads this module (by
 *  dynamic import) when the page was opened with `?preview&fixture=<name>` and
 *  there is no Qt WebChannel. The UI then shows a "Preview fixture" ribbon.
 *
 *  Every event below has exactly the shape `sanitize_event` in
 *  star/react_shell.py produces, and is fed through the same handler and the
 *  same activity reducer as real backend events. Nothing here is a claim that
 *  a model produced this text.
 */
import type {AppSettings, ChatMessage, ChatThread, RetryState, ServerStatus} from './types'
import type {ActivityRun} from './activity'

export type FixtureEvent = {wait: number; kind: 'progress' | 'result' | 'error'; data: unknown}
export type FixtureScript = {action: 'sendMessage' | 'runTeam' | 'generateImage'; mode?: 'fast' | 'auto' | 'agent'; prompt: string; events: FixtureEvent[]}
export type Fixture = {
  messages: ChatMessage[]
  /** Overrides for the preview's settings (the default is a STAR Server on the local network). */
  settings?: Partial<AppSettings>
  server?: ServerStatus
  retry?: RetryState
  script?: FixtureScript
  /** A finished run shown above the last answer (for static timeline review). */
  finishedRun?: ActivityRun
  /** Sidebar chats for this fixture (default: `fixtureChats`). The first one is the open chat. */
  chats?: ChatThread[]
  /** The current project and the other saved projects (default: the preview's own). */
  project?: string
  projects?: string[]
}

/** The preview shows the owner's real topology: the model runs on a STAR Server, not on this PC. */
export const fixtureSettings: Partial<AppSettings> = {
  provider: 'star_server',
  model: 'star-main',
  server_endpoint: 'http://192.168.1.20:8080/v1',
  server_parallel: 2,
}
export const fixtureServer: ServerStatus = {selected: true, configured: true, key_present: true, model_selected: true, ok: true, code: 'ok', checked_at: ''}
const unreachable = 'Cannot reach STAR Server. Check that the server is switched on, that this PC is on the same network, and that the address and port are right.'

const day = 86_400_000
const at = (offset: number) => new Date(Date.now() - offset).toISOString()
export const fixtureChats: ChatThread[] = [
  {id: 'fx-1', title: 'Inventory UI for Ember Hollow', created: at(3_600_000), updated: at(600_000)},
  {id: 'fx-2', title: 'Why does my RemoteEvent fire twice?', created: at(5 * 3_600_000), updated: at(4 * 3_600_000)},
  {id: 'fx-3', title: 'Low-poly lantern in Blender', created: at(day + 3_600_000), updated: at(day)},
  {id: 'fx-4', title: 'DataStore retry and session locking', created: at(3 * day), updated: at(3 * day)},
  {id: 'fx-5', title: 'Research: tycoon progression curves', created: at(5 * day), updated: at(5 * day)},
  {id: 'fx-6', title: 'Mobile HUD safe areas', created: at(12 * day), updated: at(12 * day)},
  {id: 'fx-7', title: 'R6 sword swing timing', created: at(20 * day), updated: at(20 * day)},
]

const inventoryQuestion =
  'Design the inventory UI for Ember Hollow. It is a survival game, so players open it constantly. Give me the layout, the Roblox instance hierarchy and the client code for selecting a slot.'

export const inventoryAnswer = `## Inventory for Ember Hollow

A survival inventory is opened hundreds of times a session, so the design goal is **speed first**: one key to open, no animation longer than 150 ms, and every slot reachable by keyboard, touch and gamepad.

### Layout

1. **Grid on the left** — 6 × 4 slots at 64 px, enough for a starter backpack without scrolling.
2. **Detail pane on the right** — name, weight, durability and the two actions that matter: *Use* and *Drop*.
3. **Hotbar along the bottom** — always visible, mirrors the first six slots.

Keep the frame anchored to the centre with a \`UIAspectRatioConstraint\` so it never stretches on ultrawide screens.

### Instance hierarchy

| Instance | Class | Purpose |
| --- | --- | --- |
| \`InventoryGui\` | ScreenGui | Root; \`ResetOnSpawn = false\` |
| \`Window\` | Frame | Centred container with the aspect constraint |
| \`Grid\` | ScrollingFrame | Holds slots, uses \`UIGridLayout\` |
| \`SlotTemplate\` | ImageButton | Cloned once per slot, never per item |
| \`Detail\` | Frame | Selected item, actions and weight bar |
| \`Hotbar\` | Frame | Six slots bound to keys 1 to 6 |

### Selecting a slot

The client only *asks* to move or use an item. The server owns the inventory, so a modified client cannot invent items.

\`\`\`lua
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local requestUse = Remotes:WaitForChild("RequestUseItem")

local selected: number? = nil

local function select(slot: ImageButton, index: number)
	if selected == index then
		requestUse:FireServer(index) -- second press uses the item
		return
	end
	selected = index
	slot:FindFirstChildOfClass("UIStroke").Enabled = true
end

for index, slot in grid:GetChildren() do
	if slot:IsA("ImageButton") then
		slot.Activated:Connect(function()
			select(slot, index)
		end)
	end
end
\`\`\`

> Validate \`index\` on the server and rate-limit the remote. Treat everything the client sends as a request, not a fact.

### What I have not verified

- I have not opened your place, so the hierarchy above is a proposal, not what exists in Studio.
- Sizes assume a 1080p reference; check the grid on a phone before you commit to 64 px slots.

Next step: connect Roblox Studio in read-only mode and I can compare this against your current \`StarterGui\`. The engine reference for the layout object is at [UIGridLayout](https://create.roblox.com/docs/reference/engine/classes/UIGridLayout).`

const history: ChatMessage[] = [
  {id: 'saved-0', role: 'user', text: 'I am starting a survival game called Ember Hollow. Dark forest, lantern light, small backpack.'},
  {
    id: 'saved-1',
    role: 'assistant',
    text: 'Good constraints to design around. A small backpack makes every slot a decision, and lantern light gives you a natural palette: near-black greens with one warm accent.\n\nTell me what the player does most often and I will shape the UI around that.',
  },
]

const progress = (wait: number, activity: Record<string, unknown>, phase = ''): FixtureEvent => ({wait, kind: 'progress', data: {phase, activity}})
function streamed(text: string, first: number, every: number): FixtureEvent[] {
  const parts = text.match(/[\s\S]{1,56}/g) || []
  return parts.map((delta, index) => ({wait: index ? every : first, kind: 'progress' as const, data: {phase: 'Generating response', delta}}))
}

const agentAnswer = `I read your workspace and checked the current engine reference before proposing changes.

**What exists now**

- \`src/client/InventoryController.luau\` builds every slot each time the inventory opens. That is the stutter you described.
- The \`RequestUseItem\` remote has no server-side rate limit.

**What I would change**

1. Build the 24 slots once and reuse them; only swap the image and count.
2. Add a per-player cooldown on the server before any item is used.

I asked to write the fix into your workspace, but workspace writes are turned off, so nothing was changed. Turn on *Allow workspace writes* in Settings if you want me to apply it.`

const teamAnswer = `**Recommendation: ship the fixed 24-slot grid first, and add weight later.**

- *Evidence* — your approved project notes say "small backpack" twice and never mention weight. Weight is an assumption, not a requirement.
- *Plan* — grid, detail pane, hotbar; three milestones, each testable in a private server.
- *Critique* — the largest risk is trusting the client for item use. The plan must include server validation from milestone one.

The specialists disagreed on one point: the planner wanted drag-and-drop in the first milestone, the reviewer called it a touch-screen risk. I kept it out of milestone one.

None of this was tested in Studio; it is analysis of the context you have approved.`

/* ---------------------------------------------------------------------------------------------
 * STRESS: worst-case data for break-UI review (`?preview=1&fixture=stress`). Every string here is
 * chosen to break a layout: unbreakable tokens, one letter, emoji only, right-to-left and mixed
 * direction text, a several-KB message, a very long code line, a wide table, 66 chats and a long
 * error. None of it is model output.
 * ------------------------------------------------------------------------------------------- */
const longUrl = 'https://create.roblox.com/docs/reference/engine/classes/' + 'UIGridLayout'.repeat(5) + '?section=' + 'a'.repeat(30)
const longEmail = 'ember.hollow.survival.prototype.internal.testing.team.' + 'q'.repeat(40) + '@studio-builds.example.com'
export const stressTitles = {
  /** The open chat: one long sentence, so the top bar has to shorten it. */
  open: 'Why does the inventory grid in Ember Hollow stutter on phones when the backpack has more than forty items and the hotbar is visible at the same time?',
  url: longUrl,
  email: longEmail,
  unbroken: 'a'.repeat(120),
  one: 'x',
  emoji: '🔥🌲🏮🎒⚔️🛡️🧭🗺️🪵🔦',
  arabic: 'كيف أصلح خطأ التكرار في نظام المخزون الخاص بلعبتي على الهاتف؟',
  hebrew: 'איך לשמור את נתוני השחקן בלי לאבד התקדמות כשהשרת נסגר',
  mixed: 'إصلاح RemoteEvent يعمل مرتين — fires twice on mobile',
  mixedHebrew: 'שגיאה ב-DataStore: UpdateAsync נכשל after 3 retries',
}
export const stressProject = 'Ember Hollow — survival prototype for phones, tablets and console (winter update, internal testing branch)'
const stressFiller = [
  'Lantern flicker shader', 'Wolf pack AI', 'Crafting recipes v2', 'Day and night cycle', 'Footstep sounds on snow', 'Tutorial pacing',
  'Fishing minigame', 'Shop UI', 'Badge ideas', 'Server hop', 'Anti-exploit for remotes', 'Backpack weight', 'Map streaming radius',
]
export const stressChats: ChatThread[] = [
  {id: 'fx-s1', title: stressTitles.open, created: at(1_200_000), updated: at(300_000)},
  {id: 'fx-s2', title: stressTitles.url, created: at(2_000_000), updated: at(1_800_000)},
  {id: 'fx-s3', title: stressTitles.email, created: at(2_400_000), updated: at(2_300_000)},
  {id: 'fx-s4', title: stressTitles.unbroken, created: at(3_000_000), updated: at(2_900_000)},
  {id: 'fx-s5', title: stressTitles.one, created: at(3_400_000), updated: at(3_300_000)},
  {id: 'fx-s6', title: stressTitles.emoji, created: at(3_800_000), updated: at(3_700_000)},
  {id: 'fx-s7', title: stressTitles.arabic, created: at(day + 1000), updated: at(day + 1000)},
  {id: 'fx-s8', title: stressTitles.hebrew, created: at(day + 2000), updated: at(day + 2000)},
  {id: 'fx-s9', title: stressTitles.mixed, created: at(2 * day), updated: at(2 * day)},
  {id: 'fx-s10', title: stressTitles.mixedHebrew, created: at(3 * day), updated: at(3 * day)},
  // Filler: enough chats that the sidebar must scroll and the 60-chat window applies.
  ...Array.from({length: 56}, (_, index) => ({
    id: 'fx-f' + index,
    title: stressFiller[index % stressFiller.length] + (index >= stressFiller.length ? ' (' + (Math.floor(index / stressFiller.length) + 1) + ')' : ''),
    created: at((4 + index) * day),
    updated: at((4 + index) * day),
  })),
]
const longCodeLine = 'local config = {' + Array.from({length: 24}, (_, index) => `slot${index + 1} = {id = "item_${index + 1}", count = ${index * 3}, weight = ${index / 2}}`).join(', ') + '}'
const unbrokenToken = 'InventoryGridSlotTemplateCloneBuffer'.repeat(8)
export const stressUserMessage = [
  'Here is everything I have. Sorry for the wall of text, I pasted it straight from my notes and the output window.',
  '',
  'Error from the output window (one line, it does not wrap in Studio either):',
  "ServerScriptService.InventoryService:212: attempt to index nil with 'Slots' — Stack Begin — Script 'ServerScriptService.InventoryService', Line 212 - function moveItem — Script 'ServerScriptService.InventoryService', Line 88 — Stack End",
  '',
  'My config line:',
  longCodeLine,
  '',
  'The name the plugin generated: ' + unbrokenToken,
  '',
  'The asset path: C:\\Users\\Player\\Documents\\Roblox\\Places\\EmberHollow\\Builds\\Winter\\' + 'Assets'.repeat(12) + '\\inventory_grid_final_FINAL_v7.rbxl',
  '',
  'Table I typed in my notes:',
  '| Slot | Item | Count | Weight | Durability | Rarity | Stackable | Sell price | Craftable | Notes |',
  '| 1 | Lantern | 1 | 2.5 | 100 | Common | no | 15 | yes | always in the hotbar, never dropped on death |',
  '',
  ...Array.from({length: 18}, (_, index) =>
    `Note ${index + 1}: the grid uses a UIGridLayout with CellSize 64×64 and CellPadding 6, and when the backpack holds more than forty items the frame rebuilds every slot again, which is what I think causes the stutter on my phone (an older Android with 3 GB of RAM).`),
].join('\n')
export const stressAnswer = `## Short answer 🔥

The stutter comes from rebuilding every slot. Build the slots once and only change their image and count.

### بالعربية

هذه فقرة كاملة باللغة العربية لاختبار اتجاه النص من اليمين إلى اليسار. يجب أن تبدأ من الجهة اليمنى، وأن تبقى علامات الترقيم في مكانها الصحيح، حتى عندما تحتوي على كلمات إنجليزية مثل UIGridLayout أو RemoteEvent في منتصف الجملة.

### בעברית

זוהי פסקה בעברית כדי לבדוק שהטקסט זורם מימין לשמאל. היא כוללת מילים באנגלית כמו DataStore ו-UpdateAsync באמצע המשפט, ומספרים כמו 64 ו-3.

### Plan

1. Build the grid once 🎒
   - Clone \`SlotTemplate\` 24 times at startup
     - Keep the clones in an array indexed by slot number
       - Never call \`:Destroy()\` on a slot while the inventory is open
   - Swap \`Image\` and \`Count.Text\` on change
2. Batch updates
   - Coalesce changes into one \`RenderStepped\` frame
3. Measure on the phone ⚔️🛡️

### Wide table

| Slot | Item | Count | Weight | Durability | Rarity | Stackable | Sell price | Craftable | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Lantern | 1 | 2.5 | 100 | Common | no | 15 | yes | always in the hotbar, never dropped on death |
| 2 | Wolf pelt | 12 | 0.8 | — | Uncommon | yes | 40 | no | ${'stacks'.repeat(8)} |

### Very long code line

\`\`\`lua
${longCodeLine}
\`\`\`

### Links

- Reference: [${longUrl}](${longUrl})
- Bare link: ${longUrl}
- Contact: ${longEmail}
- Inline token: \`${unbrokenToken}\`

✅🎉🌲🏮`
const stressError = 'STAR Server did not answer in time while loading the model "star-main-q4_k_m-' + 'x'.repeat(60) + '.gguf" from /srv/star/models/' + 'very-long-folder-name/'.repeat(4) + '. It may be busy with another request or still loading its model. Try again in a minute, raise the server timeout in Settings, or check the server log for the line that starts with "load failed".'

export const FIXTURES: Record<string, Fixture> = {
  /** Worst-case data everywhere at once (see the STRESS block above). */
  stress: {
    chats: stressChats,
    project: stressProject,
    projects: [stressProject, stressTitles.unbroken, 'x', 'مشروع البقاء في الغابة المظلمة', '🔥🌲'],
    messages: [
      {id: 'saved-0', role: 'user', text: stressUserMessage},
      {id: 'saved-1', role: 'assistant', text: stressAnswer},
      {id: 'saved-2', role: 'user', text: stressTitles.arabic},
      {id: 'saved-3', role: 'event', text: stressError, status: 'failed'},
    ],
    server: {...fixtureServer, ok: false, code: 'timeout'},
    retry: {status: 'failed', detail: stressError, prompt: stressTitles.arabic, message_id: 3, created: ''},
  },
  /** Finished conversation with a long Markdown answer. */
  chat: {
    messages: [...history, {id: 'saved-2', role: 'user', text: inventoryQuestion}, {id: 'saved-3', role: 'assistant', text: inventoryAnswer}],
  },
  /** Plain answer arriving as coalesced text deltas. */
  streaming: {
    messages: history,
    script: {
      action: 'sendMessage',
      mode: 'auto',
      prompt: inventoryQuestion,
      events: [
        progress(250, {type: 'route', profile: 'roblox'}, 'STAR · Roblox engineering'),
        progress(60, {type: 'turn', step: 1, max_steps: 1}, 'Thinking'),
        ...streamed(inventoryAnswer, 1400, 70),
        progress(120, {type: 'finished', model_calls: 1, tool_calls: 0}),
        progress(60, {type: 'saved'}),
        {wait: 60, kind: 'result', data: {answer: inventoryAnswer}},
      ],
    },
  },
  /** Agent mode: model turns, authorized tools, read-only specialists, one blocked request. */
  agent: {
    messages: history,
    script: {
      action: 'sendMessage',
      mode: 'agent',
      prompt: 'The inventory stutters when it opens. Look at my workspace and the current Roblox docs, then tell me what to change.',
      events: [
        progress(300, {type: 'route', profile: 'agent'}, 'STAR · Agent workflow'),
        progress(80, {type: 'turn', step: 1, max_steps: 12}, 'Thinking'),
        progress(2600, {type: 'tool', state: 'running', tool: 'workspace_search'}),
        progress(900, {type: 'tool', state: 'done', tool: 'workspace_search'}),
        progress(120, {type: 'tool', state: 'running', tool: 'workspace_read'}),
        progress(500, {type: 'tool', state: 'done', tool: 'workspace_read'}),
        progress(80, {type: 'turn', step: 2, max_steps: 12}, 'Thinking'),
        progress(2200, {type: 'tool', state: 'running', tool: 'star_roblox_docs'}),
        progress(1300, {type: 'tool', state: 'done', tool: 'star_roblox_docs'}),
        progress(80, {type: 'turn', step: 3, max_steps: 12}, 'Thinking'),
        progress(1900, {type: 'tool', state: 'running', tool: 'star_delegate_research'}),
        progress(150, {type: 'agent', group: 'specialist', id: 't4f1c2a9d01', role: 'luau', state: 'running'}, 'STAR luau specialist · working'),
        progress(4200, {type: 'agent', group: 'specialist', id: 't4f1c2a9d01', role: 'luau', state: 'done'}, 'STAR luau specialist · completed'),
        progress(150, {type: 'agent', group: 'specialist', id: 't9b7e03c552', role: 'review', state: 'running'}, 'STAR review specialist · working'),
        progress(3600, {type: 'agent', group: 'specialist', id: 't9b7e03c552', role: 'review', state: 'done'}, 'STAR review specialist · completed'),
        progress(120, {type: 'tool', state: 'done', tool: 'star_delegate_research'}),
        progress(80, {type: 'turn', step: 4, max_steps: 12}, 'Thinking'),
        progress(1700, {type: 'tool', state: 'blocked'}, 'A tool request was not permitted'),
        progress(80, {type: 'turn', step: 5, max_steps: 12}, 'Thinking'),
        progress(2400, {type: 'finished', model_calls: 5, tool_calls: 5}),
        progress(80, {type: 'saved'}),
        {wait: 80, kind: 'result', data: {answer: agentAnswer}},
      ],
    },
  },
  /** STAR Teams: the fixed four-stage plan, two stages in parallel. */
  team: {
    messages: history,
    script: {
      action: 'runTeam',
      prompt: 'Should the first version of the inventory have weight limits, or just a fixed grid?',
      events: [
        progress(300, {type: 'plan', group: 'team', steps: [
          {id: 'evidence', role: 'research', needs: []},
          {id: 'design', role: 'planner', needs: []},
          {id: 'critic', role: 'review', needs: []},
          {id: 'synthesis', role: 'integration', needs: ['evidence', 'design', 'critic']},
        ]}, 'STAR Teams: plan ready'),
        progress(80, {type: 'agent', group: 'team', id: 'evidence', role: 'research', state: 'running'}),
        progress(40, {type: 'agent', group: 'team', id: 'design', role: 'planner', state: 'running'}),
        progress(5200, {type: 'agent', group: 'team', id: 'evidence', role: 'research', state: 'done', elapsed_ms: 5240}),
        progress(60, {type: 'agent', group: 'team', id: 'critic', role: 'review', state: 'running'}),
        progress(2900, {type: 'agent', group: 'team', id: 'design', role: 'planner', state: 'done', elapsed_ms: 8180}),
        progress(3300, {type: 'agent', group: 'team', id: 'critic', role: 'review', state: 'done', elapsed_ms: 6260}),
        progress(60, {type: 'agent', group: 'team', id: 'synthesis', role: 'integration', state: 'running'}),
        progress(6100, {type: 'agent', group: 'team', id: 'synthesis', role: 'integration', state: 'done', elapsed_ms: 6090}),
        {wait: 100, kind: 'result', data: {answer: teamAnswer, agents: 4, peak_concurrency: 2, elapsed_ms: 17810}},
      ],
    },
  },
  /** A stage fails, so the stage that depends on it is blocked and the run ends in an error. */
  teamfail: {
    messages: history,
    script: {
      action: 'runTeam',
      prompt: 'Should the first version of the inventory have weight limits, or just a fixed grid?',
      events: [
        progress(200, {type: 'plan', group: 'team', steps: [
          {id: 'evidence', role: 'research', needs: []},
          {id: 'design', role: 'planner', needs: []},
          {id: 'critic', role: 'review', needs: []},
          {id: 'synthesis', role: 'integration', needs: ['evidence', 'design', 'critic']},
        ]}),
        progress(60, {type: 'agent', group: 'team', id: 'evidence', role: 'research', state: 'running'}),
        progress(40, {type: 'agent', group: 'team', id: 'design', role: 'planner', state: 'running'}),
        progress(4800, {type: 'agent', group: 'team', id: 'evidence', role: 'research', state: 'done', elapsed_ms: 4870}),
        progress(60, {type: 'agent', group: 'team', id: 'critic', role: 'review', state: 'running'}),
        progress(2100, {type: 'agent', group: 'team', id: 'design', role: 'planner', state: 'done', elapsed_ms: 7020}),
        progress(1900, {type: 'agent', group: 'team', id: 'critic', role: 'review', state: 'failed', elapsed_ms: 4010}),
        progress(40, {type: 'agent', group: 'team', id: 'synthesis', role: 'integration', state: 'blocked'}),
        {wait: 80, kind: 'error', data: 'RuntimeError: STAR Teams could not finish: critic:failed, synthesis:blocked'},
      ],
    },
  },
  /** The model cannot be reached: recovery inline, typed text kept, status turns to "Not reachable". */
  error: {
    messages: history,
    script: {
      action: 'sendMessage',
      mode: 'auto',
      prompt: inventoryQuestion,
      events: [
        progress(250, {type: 'route', profile: 'roblox'}, 'STAR · Roblox engineering'),
        progress(60, {type: 'turn', step: 1, max_steps: 1}, 'Thinking'),
        {wait: 900, kind: 'error', data: unreachable},
      ],
    },
  },
  /** Create image from the + menu: the picture is being made on this PC (shape follows the chosen size). */
  image: {
    messages: history,
    script: {
      action: 'generateImage',
      prompt: 'A lantern-lit forest clearing at dusk, painterly, for the Ember Hollow loading screen',
      events: [
        {wait: 300, kind: 'progress', data: {phase: 'Starting the picture engine on this PC'}},
        {wait: 1200, kind: 'progress', data: {phase: 'Creating the picture'}},
        // No picture engine runs in a browser preview, so the scripted turn ends honestly after a long pause.
        {wait: 45000, kind: 'error', data: 'This browser preview has no picture engine. In STAR Desktop the picture appears here.'},
      ],
    },
  },
  /** The user pressed Stop part-way through an answer. */
  stopped: {
    messages: history,
    script: {
      action: 'sendMessage',
      mode: 'auto',
      prompt: inventoryQuestion,
      events: [
        progress(250, {type: 'route', profile: 'roblox'}, 'STAR · Roblox engineering'),
        progress(60, {type: 'turn', step: 1, max_steps: 1}, 'Thinking'),
        ...streamed(inventoryAnswer.slice(0, 520), 500, 30),
        {wait: 200, kind: 'error', data: 'Request stopped. The draft answer has not been saved as a completed result.'},
      ],
    },
  },
  /** Reopened after a restart: an older failed attempt is history, the newest unanswered turn offers Retry. */
  restart: {
    messages: [
      ...history,
      {id: 'saved-2', role: 'user', text: 'Add a weight bar under the grid.'},
      {id: 'saved-3', role: 'event', text: 'STAR Server did not answer in time. It may be busy with another request or still loading its model. Try again, or raise the server timeout in Settings.', status: 'failed'},
      {id: 'saved-4', role: 'user', text: 'Add a weight bar under the grid.'},
      {id: 'saved-5', role: 'assistant', text: 'Put the weight bar inside `Detail`, under the item actions, so it is visible only when an item is selected. Use a `Frame` with a child `Frame` whose `Size.X.Scale` is the carried weight divided by the limit.'},
      {id: 'saved-6', role: 'user', text: inventoryQuestion},
      {id: 'saved-7', role: 'event', text: unreachable, status: 'failed'},
    ],
    server: {...fixtureServer, ok: false, code: 'unreachable'},
    retry: {status: 'failed', detail: unreachable, prompt: inventoryQuestion, message_id: 7, created: ''},
  },
  /** Every step state side by side, including "waiting for approval", which no backend event produces yet. */
  states: {
    messages: [...history, {id: 'saved-2', role: 'user', text: 'Show every activity state.'}],
    finishedRun: {
      id: 'fx-states',
      mode: 'chat',
      label: 'State gallery',
      outcome: 'running',
      startedAt: Date.now() - 48_000,
      phase: 'Working',
      streaming: false,
      steps: [
        {id: 's1', kind: 'think', state: 'done', title: 'Thinking', detail: 'Model call 1 of up to 12', startedAt: 0, endedAt: 2600},
        {id: 's2', kind: 'tool', state: 'done', title: 'Reading your workspace', detail: 'workspace_search', startedAt: 0, endedAt: 900},
        {id: 's3', kind: 'tool', state: 'failed', title: 'Searching the web', detail: 'star_web_search', startedAt: 0, endedAt: 12_000},
        {id: 's4', kind: 'tool', state: 'blocked', title: 'A tool request was blocked', detail: 'STAR asked for a tool this task is not permitted to use. Nothing was run.', startedAt: 0, endedAt: 0},
        {id: 's5', kind: 'agent', state: 'waiting', title: 'Write to your workspace', role: 'Needs your approval', detail: 'Design state only: STAR has no approval step during a run yet, so real runs never show this.'},
        {id: 's6', kind: 'agent', state: 'running', title: 'Evidence', role: 'Researcher', detail: 'Sorts what is supported by your project context from what is still unknown.', startedAt: Date.now() - 7000},
        {id: 's7', kind: 'agent', state: 'cancelled', title: 'Plan', role: 'Planner', detail: 'Not started.'},
        {id: 's8', kind: 'agent', state: 'queued', title: 'Synthesis', role: 'Synthesis lead', detail: 'Combines the three findings into one answer. Starts after Evidence, Plan and Critique.'},
      ],
    },
  },
}
