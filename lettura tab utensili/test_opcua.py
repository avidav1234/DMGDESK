"""
Test connessione OPC UA - DMG DMC 160U / Sinumerik 840D
Server: opcUa_Server_xp.exe (OpcUaLegacy)
"""

from opcua import Client
from opcua.ua import SecurityPolicy
import sys

# --- CONFIGURAZIONE ---
ENDPOINT = "opc.tcp://192.168.214.241:4840"
USERNAME = "admin"
PASSWORD = "admin123"   # <-- sostituisci con la password che hai impostato

# Nodi dal NodeTreeConfig.ini
NODES = {
    "opMode":           "/BAG/State/opmode",
    "progStatus":       "/Channel/State/progStatus",
    "actTNumber":       "/Channel/State/actTNumber",
    "actToolIdent":     "/Channel/State/actToolIdent",
    "PartProgramName":  "/Channel/ProgramInfo/workPandProgName[u1]",
    "OpcUaAlarm1":      "/Hmi/OpcUaAlarm1",
    "OpcUaAlarmNumbers":"/Hmi/OpcUaAlarmNumbers",
}

def test_connection():
    client = Client(ENDPOINT)
    client.set_user(USERNAME)
    client.set_password(PASSWORD)

    print(f"Connessione a {ENDPOINT} ...")
    try:
        client.connect()
        print("✅ Connesso!\n")

        # Leggi info server
        root = client.get_root_node()
        print(f"Root node: {root}")

        # Prova a navigare il namespace
        objects = client.get_objects_node()
        print(f"Objects node: {objects}")
        children = objects.get_children()
        print(f"\nNodi figli di Objects ({len(children)}):")
        for child in children:
            try:
                name = child.get_browse_name()
                print(f"  - {name}")
            except Exception as e:
                print(f"  - (errore browse: {e})")

        print("\n--- Fine test ---")
        client.disconnect()

    except Exception as e:
        print(f"❌ Errore: {e}")
        print("\nVerifica:")
        print("  1. Il server opcUa_Server_xp.exe è in esecuzione sulla XP?")
        print("  2. La porta 4840 è raggiungibile? (firewall XP)")
        print("  3. Le credenziali sono corrette?")
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
