import sys
import site
import os
import bpy
import json
import math

# --- 1. PATH SETUP (As in your original) ---
try:
    user_paths = site.getusersitepackages()
    if not isinstance(user_paths, list):
        user_paths = [user_paths]
    for p in user_paths:
        if p not in sys.path:
            sys.path.append(p)
    if 'APPDATA' in os.environ:
        appdata_path = os.path.join(os.environ['APPDATA'], "Python", "Python311", "site-packages")
        if appdata_path not in sys.path and os.path.exists(appdata_path):
            sys.path.append(appdata_path)
except Exception as e:
    print(f"Path error: {e}")

import paho.mqtt.client as mqtt

# --- 2. CONFIGURATION ---
# Add current folder (where .blend is) to path to find secrets.py
import os
dir_path = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else "."
if dir_path not in sys.path:
    sys.path.append(dir_path)

try:
    from mqtt_secrets import HOST, PORT, USERNAME, PASSWORD
except ImportError:
    print(f"ERROR: File mqtt_secrets.py missing in {dir_path} !")
    print("Please copy mqtt_secrets_template.py to mqtt_secrets.py and enter your credentials.")
    HOST, PORT, USERNAME, PASSWORD = "", 0, "", ""

TOPIC = "FABLAB_21_22/Blender/Pendules_coupl/out"

# Exact names of your objects
PENDULE_1_NAME = "Pendule1" 
PENDULE_2_NAME = "Pendule2" 
STOP_FRAME = 1500

client = None

# --- 3. MQTT FUNCTIONS ---
def init_mqtt():
    global client
    # Manage paho-mqtt v2 compatibility (CallbackAPIVersion)
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    else:
        client = mqtt.Client()
        
    client.username_pw_set(USERNAME, PASSWORD)
    client.tls_set()
    try:
        client.connect(HOST, PORT, 60)
        client.loop_start()
        print("MQTT Connected and Thread started.")
    except Exception as e:
        print(f"MQTT Connection Error: {e}")

def stop_mqtt():
    global client
    if client:
        client.loop_stop()
        client.disconnect()
        client = None
        print("MQTT Stopped.")

# --- 4. THE HANDLER (Core of the script) ---
def my_handler(scene):
    global client
    current_frame = scene.frame_current

    # Start connection at frame 1
    if current_frame == 1:
        if client: stop_mqtt()
        init_mqtt()
    
    # If no client, exit
    if not client: return

    # Object retrieval (Simple method that worked for you)
    obj1 = bpy.data.objects.get(PENDULE_1_NAME)
    obj2 = bpy.data.objects.get(PENDULE_2_NAME)
    
    if obj1 and obj2:
        # Time calculation
        fps = scene.render.fps
        tps = current_frame / fps
        
        # --- READING ANGLES ---
        # Using your method: matrix_world.to_euler().x
        # (This is global rotation on X axis)
        
        # Pendulum 1
        angle1_rad = obj1.matrix_world.to_euler().x
        angle1_deg = angle1_rad * 180 / 3.14159265
        
        # Pendulum 2
        angle2_rad = obj2.matrix_world.to_euler().x
        angle2_deg = angle2_rad * 180 / 3.14159265
        
        # Message preparation
        payload = {
            "temps": round(tps, 3),
            "theta1": round(angle1_deg, 2),
            "theta2": round(angle2_deg, 2)
        }
        
        # Send
        try:
            client.publish(TOPIC, json.dumps(payload))
        except Exception as e:
            print(f"Send error: {e}")

    # Auto stop at end
    if current_frame >= STOP_FRAME:
        bpy.ops.screen.animation_cancel(restore_frame=False)
        stop_mqtt()

# --- 5. REGISTRATION ---
def register():
    # Clean up everything before
    if my_handler in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(my_handler)
    if my_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(my_handler)
    
    # IMPORTANT: Using 'frame_change_POST' 
    # This runs AFTER physics has moved the objects.
    bpy.app.handlers.frame_change_post.append(my_handler)
    
    print("Double Pendulum Script (Simple) activated on frame_change_post !")

if __name__ == "__main__":
    register()