# Self-learning: how STAR gets better, and how to undo it

STAR does **not** retrain its AI model. Instead it keeps short written **lessons** ("use task.wait instead of
wait", "I prefer British spelling") that you can read, change and remove. Accepted lessons are added to later
answers in the same project. Other projects never see them.

Everything on this page lives in **Projects → What STAR has learned**.

## Lessons

**Status: Available**

Lessons are sorted into three tabs:

| Tab | What is in it |
|---|---|
| **Waiting** | Notes STAR worked out for itself (from retries, failed checks, thumbs, summaries). **Not used** until you approve them. |
| **Accepted** | Lessons STAR uses in answers for this project. |
| **Set aside** | Lessons you rejected or undid. Not used. |

Buttons on each lesson: **Approve**, **Edit**, **Reject** (called **Stop using** on accepted lessons),
**Delete** and **Restore**. To add one yourself, use **Teach STAR something for this project** and click
**Save as accepted**.

Things you say yourself in your own words (a preference, or a correction) are accepted straight away. To
review even those first, turn off **Accept my own corrections automatically**.

STAR keeps at most 200 self-made notes waiting at once; your own words are always kept. Accepted lessons do
not expire.

## Correct an answer

**Status: Available**

1. Under the answer, click the thumbs-down (**Not helpful**).
2. A box appears: **What was wrong? (optional)**. Type what should have happened, for example "use task.wait
   instead of wait, and the door should tween open".
3. Click **Save correction**.

STAR keeps your question, its answer and your words. It also adds your words as a lesson (accepted at once if
**Accept my own corrections automatically** is on, otherwise under **Waiting**). Text that looks like a key or
password is refused, and private network addresses are removed before saving.

Your corrections are listed under **Your corrections** (inside **What STAR learned this week**, on the same
page). There you can:

- **Make it a test**: adds it to your personal corrections test list, so the same mistake can be checked
  for later.
- **Dismiss**: sets it aside.

## Night school

**Status: Coming soon** for most people. It needs a STAR Server, and its results are not yet shipped to the app.

Night school is STAR practising by itself on a [STAR Server](star-server.md). When nobody has used the server
for 10 minutes, it works through Roblox Luau practice tasks, writes a one-sentence lesson when it fails, and
keeps a lesson only if it does measurably better on practice tasks it never learned from. It stops as soon as
someone else uses the server. It never runs on your PC, never changes the model, and never sees your chats.

Its lessons reach the desktop app only after a person reviews them and they are included in a STAR release.
No such lessons are included in the current version yet, so **What STAR learned this week** will say
"Nothing new this week".

## What STAR learned this week

**Status: Available** (the list is empty until a release includes night school lessons)

This section (on **Projects → What STAR has learned**, and also on **More → Model & connection**) shows what
STAR started using from night school in the last week. Each item says whether it is a **Lesson** or a
**Checked example**, how many days it has left, and an **Evidence** fold-out with the practice results.

New items are on a **14-day trial**: STAR uses them for 14 days and then stops, unless you keep them.

| Button | What it does |
|---|---|
| **Undo** | STAR stops using it at once. A lesson moves to **Set aside**; nothing is lost. |
| **Restore** | Puts an undone item back exactly as it was (only while its 14 days are not over). |
| **Keep for good** | Ends the trial. A kept lesson becomes a normal accepted lesson. |

To stop new night school items being used automatically, turn off **Use what night school learns, on a 14-day
trial**. They will then wait under **Waiting** for your approval. Items already in use stay until you undo them
or their 14 days end.

## Undo and forget

**Status: Available**

| You want to… | Do this |
|---|---|
| Stop STAR using a lesson | **Stop using** (it moves to **Set aside**; **Restore** brings it back) |
| Remove a lesson for good | **Delete**, then **Yes, delete** (cannot be undone) |
| Take back a correction you just made | Click the thumbs-down again to remove it. This deletes the correction and its waiting lesson, if it has not been reviewed yet. |
| Undo a night school item | **Undo** in **What STAR learned this week** |
| Keep a copy of your lessons | **Export** saves them as a `.json` file where you choose |
| Forget everything | There is no single button yet. Delete lessons one by one, or close STAR and remove the `knowledge` folder and `corrections.sqlite3` from your [STAR files](privacy-and-data.md#what-is-stored-where). |

Two things to know:

- Deleting a **chat** does not delete the lessons or corrections that came from it. Remove those here.
- A correction you turned into a test with **Make it a test** cannot be removed from inside the app yet.

## Learning settings

All on **Projects → What STAR has learned**; they take effect at once.

| Setting | Starts | What it does |
|---|---|---|
| **Accept my own corrections automatically** | On | Your own words become accepted lessons at once. Off: they wait for review too. |
| **Use what night school learns, on a 14-day trial** | On | See [night school](#what-star-learned-this-week). |
| **Summarise raw notes in the background** | On | After answers, a spare model rewords raw notes into tidy lesson suggestions. Suggestions always wait for review. |
| **Also summarise with a hosted provider** | Off | Only shown when a cloud provider is selected. The notes quote your chats, so they would be sent to that provider. |
| **Import bundled STAR practice lessons** | Off | Adds practice lessons shipped with STAR (the current bundle is empty). |

In Settings → **Advanced settings** → **Knowledge & expert tools**, **Use checked practice examples** (off) lets
STAR use checked night school answers as reference examples.
