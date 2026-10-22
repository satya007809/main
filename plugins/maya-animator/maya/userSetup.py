"""
Optional: copy this file (and claude_bridge.py) into your Maya scripts folder so the
bridge starts automatically with Maya.

Windows : C:\\Users\\<you>\\Documents\\maya\\<version>\\scripts\\
macOS   : ~/Library/Preferences/Autodesk/maya/<version>/scripts/
Linux   : ~/maya/<version>/scripts/

If a userSetup.py already exists there, paste the two lines below into it instead.
"""
import maya.utils

maya.utils.executeDeferred(lambda: __import__("claude_bridge").start())
