LNK2019 means the linker found the declaration (the header) but not the compiled code, because your module does not link against the module that defines `UUserWidget`. That class lives in the `UMG` module.

Fix: open your module's `MyGame.Build.cs` and add `"UMG"` to `PublicDependencyModuleNames` (or `PrivateDependencyModuleNames` if only .cpp files use it); widget code often also needs `"Slate"` and `"SlateCore"`. Regenerate project files if the IDE is confused, then rebuild with the editor closed. Not built here.
