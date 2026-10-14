# Startup script of the STAR Blender Lab GUI (run with: blender --online-mode --factory-startup --python this.py).
# Enables the official Blender Lab MCP add-on for THIS session only and binds it to 127.0.0.1. Nothing is saved to
# the user preferences, so a plain `blender` started by hand has no MCP server.
import os
import bpy

MODULE = "bl_ext.user_default.mcp"
PORT = int(os.environ.get("BLENDER_LAB_PORT", "9876"))


def _enable():
    try:
        bpy.ops.preferences.addon_enable(module=MODULE)
        prefs = bpy.context.preferences.addons[MODULE].preferences
        prefs.host = "127.0.0.1"          # never 0.0.0.0: the add-on runs code without any guard
        prefs.port = PORT
        prefs.use_autostart = True
        prefs.use_log = False
        # The add-on starts its server from a timer after `autostart_delay` seconds; start now if that was missed.
        from bl_ext.user_default.mcp import mcp_to_blender_server as server
        if not server.is_running():
            bpy.ops.blmcp.server_start()
        print("STAR_LAB: Lab MCP bridge on 127.0.0.1:%d" % PORT)
    except Exception as error:  # a broken add-on must not stop Blender from showing the scene
        print("STAR_LAB: could not enable the Lab MCP add-on: %r" % (error,))
    return None


bpy.context.preferences.view.show_splash = False
bpy.app.timers.register(_enable, first_interval=0.5)
