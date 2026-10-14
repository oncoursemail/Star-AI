ARC handles closures automatically, so there is no cycle. The scene is probably kept by SpriteKit; set onTick to a
global function instead. unowned is always safe if you prefer.
