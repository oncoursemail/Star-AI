Authored responsiveness fixture
==============================

Respect the smallest supported viewport.

.. warning:: Raw directive body must remain visible.

.. code-block:: gdscript

   var previous_tween = null
   func stop_previous():
       previous_tween = null

.. include:: ../../outside-secret.txt

Final constraint: focus order must survive relayout.
