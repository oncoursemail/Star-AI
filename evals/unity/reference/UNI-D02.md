Unity only sends trigger messages when the physics engine tracks at least one of the two objects as a body. Two colliders without any Rigidbody are both treated as static, so they never report contacts to each other.

Check these in order:
- Rigidbody: add a Rigidbody to the player or to the pickup. For a script-moved player make it kinematic (`isKinematic = true`) and move it with `Rigidbody.MovePosition` in `FixedUpdate`; a kinematic Rigidbody still generates trigger events.
- Is Trigger: enable Is Trigger on the pickup's SphereCollider (`Collider.isTrigger`). Without it the shapes collide instead and `OnCollisionEnter` would be the message.
- Signature: the method must be spelled exactly `void OnTriggerEnter(Collider other)`, so the parameter must be a Collider. For 2D colliders you would need `OnTriggerEnter2D(Collider2D)` and 2D components.
- Layers: make sure the two objects' layers are allowed to interact in the Layer Collision Matrix (Project Settings > Physics).
- The script must sit on the GameObject that has the trigger collider (or the Rigidbody's GameObject).
