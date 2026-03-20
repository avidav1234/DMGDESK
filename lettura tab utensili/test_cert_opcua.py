"""
Test connessione OPC UA - DMG DMC 160U / Sinumerik 840D
"""

from opcua import Client
import sys
import traceback
import socket

ENDPOINT = "opc.tcp://192.168.214.241:4840"
USERNAME = "admin"
PASSWORD = "admin123"   # <-- sostituisci con la tua password

def test_ping():
    """Verifica raggiungibilità porta 4840"""
    host = "192.168.214.241"
    port = 4840
    print(f"Test connessione TCP a {host}:{port} ...")
    try:
        s = socket.create_connection((host, port), timeout=5)
        s.close()
        print(f"✅ Porta {port} raggiungibile!\n")
        return True
    except socket.timeout:
        print(f"❌ Timeout - host non raggiungibile o porta chiusa\n")
        return False
    except ConnectionRefusedError:
        print(f"❌ Connessione rifiutata - porta {port} chiusa (server non in ascolto?)\n")
        return False
    except Exception as e:
        print(f"❌ Errore TCP: {e}\n")
        return False

def test_opcua():
    client = Client(ENDPOINT)
    client.set_user(USERNAME)
    client.set_password(PASSWORD)

    print(f"Connessione OPC UA a {ENDPOINT} ...")
    try:
        client.connect()
        print("✅ Connesso!\n")

        objects = client.get_objects_node()
        children = objects.get_children()
        print(f"Nodi figli di Objects ({len(children)}):")
        for child in children:
            try:
                print(f"  - {child.get_browse_name()}")
            except:
                pass

        client.disconnect()
        print("\n✅ Test completato con successo!")

    except Exception as e:
        print(f"❌ Errore OPC UA: {type(e).__name__}: {e}")
        print("\n--- Traceback completo ---")
        traceback.print_exc()
        print("--------------------------")

if __name__ == "__main__":
    ok = test_ping()
    if ok:
        test_opcua()
    else:
        print("Impossibile procedere - verifica rete e che opcUa_Server_xp.exe sia avviato")