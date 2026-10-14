---
title: "Bindable events and callbacks"
url: /docs/en-us/scripting/events/bindable
last_updated: 2026-10-12T18:23:09Z
description: "Bindable events and callbacks allow for back-and-forth communication on the same side of the client-server boundary."
---

# Bindable events and callbacks

`Class.BindableEvent` and `Class.BindableFunction` objects let you bind behaviors between scripts **on the same side** of the [client-server](/docs/en-us/projects/client-server.md) boundary and communicate a specific desired outcome for in-game actions.

The most common use case for bindable events is for games that have a round-based structure. For example, you might have a "match started" event that lets other scripts start a timer and display a leaderboard, with a corresponding "match ended" event that lets other scripts know when to move players back into a lobby and display the winners.

Because they coordinate activities between scripts, bindable events are typically used on the server, but you can use them on the client, too.

Depending on how your game works, bindable events can help make your code more modular, but [module scripts](/docs/en-us/scripting/module.md) are often a better alternative for situations in which you need to share data between scripts. You can also use bindable events in conjunction with module scripts for a cleaner syntax, as noted in [Custom events](/docs/en-us/scripting/module.md#custom-events).

> **Info:** To communicate between scripts **across** the client-server boundary, see [Remote events](/docs/en-us/scripting/events/remote.md).
## Bindable events

The `Class.BindableEvent` object enables custom events through asynchronous, one-way communication between scripts.

When you fire a `Class.BindableEvent` through the `Class.BindableEvent:Fire()|Fire()` method, the firing script does **not** yield, and the target function receives the passed arguments with certain [limitations](#argument-limitations). Like all events, `Class.BindableEvent|BindableEvents` create threads of each connected function, so even if one errors, others continue.

To create a new `Class.BindableEvent` using the [Explorer](/docs/en-us/studio/explorer.md) window in Studio:

1. Hover over the container into which you want to insert the `Class.BindableEvent`. We recommend using `Class.ServerScriptService` for communication between server scripts and `Class.ReplicatedStorage` for communication between client scripts.
2. Click the **⊕** button that appears to the right of the container's name and insert a **BindableEvent** instance.
3. Rename the instance to `TestBindableEvent`.

After you've created a `Class.BindableEvent`, connect a function to its `Class.BindableEvent.Event|Event` event in one script, and then `Class.BindableEvent:Fire()|Fire()` the event from another script.

```lua
local ServerScriptService = game:GetService("ServerScriptService")

-- Get reference to bindable event instance
local bindableEvent = ServerScriptService:WaitForChild("TestBindableEvent")

-- Connect anonymous function to event
bindableEvent.Event:Connect(function(data)
