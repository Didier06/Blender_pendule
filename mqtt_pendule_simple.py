import sys
import site
import os
import bpy
import json

# --- Correcting the path to find paho-mqtt ---
# Blender sometimes ignores the user's site-packages folder where pip installed the module.
# We add it manually to the search path (sys.path).
try:
    # 1. Via site.getusersitepackages()
    user_paths = site.getusersitepackages()
    if not isinstance(user_paths, list):
        user_paths = [user_paths]
    for p in user_paths:
        if p not in sys.path:
            sys.path.append(p)
    
    # 2. Fallback explicite pour Windows (Roaming profile)
    if 'APPDATA' in os.environ:
        appdata_path = os.path.join(os.environ['APPDATA'], "Python", "Python311", "site-packages")
        if appdata_path not in sys.path and os.path.exists(appdata_path):
            sys.path.append(appdata_path)

except Exception as e:
    print(f"Erreur lors de la configuration du path: {e}")

# Importing the library after correcting the path
import paho.mqtt.client as mqtt

# --- MQTT configuration ---
# Secure TCP (SSL/TLS)
# Add the current folder (where the .blend file is located) to the path to find secrets.py
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
TOPIC = "FABLAB_21_22/Blender/Pendule/out"

# --- Configuration Blender ---
PENDULUM_NAME = "Pendule" # Ensure that the object is named "Pendulum" in Blender.
STOP_FRAME = 1000

# Global variable for the MQTT client
client = None

def on_connect(client, userdata, flags, rc):
    """Callback when connecting to the broker."""
    if rc == 0:
        print(f"Successfully connected to the broker {HOST}:{PORT}")
    else:
        print(f"Échec de la connexion MQTT. Code : {rc}")

def init_mqtt():
    """Initialises and connects the MQTT client asynchronously."""
    global client
    
    # Client creation (Compatible with paho-mqtt v2)
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    else:
        client = mqtt.Client()
    
    # Authentication configuration
    client.username_pw_set(USERNAME, PASSWORD)
    
    # TLS configuration for secure port 8443
    # Use the system's default CAs
    client.tls_set()
    
    # Callback
    client.on_connect = on_connect
    
    try:
        # Connexion (keepalive de 60s)
        client.connect(HOST, PORT, 60)
        
        # Start the network management loop in a separate thread.
        # This prevents Blender's interface from blocking.
        client.loop_start()
        print("MQTT thread started.")
        
    except Exception as e:
        print(f"Critical error during MQTT initialisation : {e}")

def my_handler(scene):
    """Fonction exécutée à chaque changement d'image."""
    global client
    
    current_frame = scene.frame_current

    # --- Auto login on start-up (Frame 1) ---
    if current_frame == 1:
        # If the client does not exist or is disconnected, the connection is initiated.
        if client is None or not client.is_connected():
            print("Frame 1 : Initialisation de la connexion MQTT...")
            # If an old client is lingering (disconnected but object still exists), we clean it up to be sure.
            if client is not None:
                stop_mqtt()
            init_mqtt()
    
    # Connection verification
    if client is None or not client.is_connected():
        return

    # Recovery of the pendulum object
    obj = bpy.data.objects.get(PENDULUM_NAME)
    if obj is None:
        # Essai avec minuscule si Majuscule échoue, ou vice versa
        obj = bpy.data.objects.get("pendule")
    
    if obj is None:
        print(f"Pendule object not found!")
        return

    # Time calculation
    fps = scene.render.fps
    tps = current_frame / fps
    
    # CAngle calculation (Rotation X in degrees)
    angle = obj.matrix_world.to_euler().x * 180 / 3.14159265
    
    # Preparing the JSON payload
    payload = {
        "temps": round(tps, 4),
        "angle": round(angle, 4)
    }
    json_payload = json.dumps(payload)
    
    # Publication
    try:
        client.publish(TOPIC, json_payload)
    except Exception as e:
        print(f"Publication error : {e}")

    # Managing the end of the animation
    if current_frame >= STOP_FRAME:
        print("End of animation reached.")
        bpy.ops.screen.animation_cancel(restore_frame=False)
        stop_mqtt()

def stop_mqtt():
    """Properly stop the MQTT client."""
    global client
    if client:
        print("MQTT client shutdown...")
        client.loop_stop()
        client.disconnect()
        client = None

def register():
    """Register the handler in Blender."""
    # Preliminary cleaning to avoid duplicates
    if my_handler in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(my_handler)
        print("Former handler retired.")
    
    # Add handler ONLY (connection will be made to frame 1)
    bpy.app.handlers.frame_change_pre.append(my_handler)
    print("Handler 'my_handler' enregistré. La connexion se fera au lancement de l'animation (Frame 1).")

def unregister():
    """Removes the handler and closes the connection."""
    if my_handler in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(my_handler)
    stop_mqtt()

if __name__ == "__main__":
    register()
