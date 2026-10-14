The stutter comes from mixing two clocks. Unity simulates physics on the fixed timestep (`FixedUpdate`, 0.02 s by default), while `Update` runs once per rendered frame. Writing `transform.position` on a Rigidbody object in `Update` teleports it outside the simulation, and the physics step then corrects it, so its rendered position alternates between frame time and physics time. A camera that follows from another `Update` reads that position at an arbitrary moment, which makes it worse at high frame rates.

Fix:
- Read input in `Update` and store it, then move the body in `FixedUpdate` through the Rigidbody: `Rigidbody.MovePosition` for a kinematic body, or `AddForce` / setting `Rigidbody.linearVelocity` for a dynamic one. Do not touch the Transform directly.
- Turn on interpolation on the player's Rigidbody (`Rigidbody.interpolation = RigidbodyInterpolation.Interpolate`) so the rendered pose is smoothed between physics steps. Only the followed body needs it.
- Move the camera in `LateUpdate`, after all movement for the frame, reading the interpolated transform (or let Cinemachine do the following).
