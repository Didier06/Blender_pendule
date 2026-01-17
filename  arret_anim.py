import bpy

# The function that checks whether we are at the end
def stop_at_end(scene):
    if scene.frame_current >= scene.frame_end:
        bpy.ops.screen.animation_cancel(restore_frame=False)

# 1. Remove the old function so that it is not duplicated if the script is restarted.
# (Use a loop to clean up properly.)
my_handlers = bpy.app.handlers.frame_change_pre
to_remove = [h for h in my_handlers if h.__name__ == "stop_at_end"]
for h in to_remove:
    my_handlers.remove(h)

# 2. We add the function
bpy.app.handlers.frame_change_pre.append(stop_at_end)

print("Script d'arrêt activé !")

