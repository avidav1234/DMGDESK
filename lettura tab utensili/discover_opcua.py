# discover_opcua.py
import asyncio
from asyncua import Client

async def discover():
    url = "opc.tcp://10.95.20.29:4840"
    client = Client(url=url)
    try:
        endpoints = await client.connect_and_get_server_endpoints()
        print("=== ENDPOINT DISPONIBILI ===")
        for ep in endpoints:
            print(f"  URL: {ep.EndpointUrl}")
            print(f"  Security: {ep.SecurityPolicyUri.split('#')[-1]}")
            print(f"  Mode: {ep.SecurityMode}")
            tokens = [str(t.TokenType) for t in ep.UserIdentityTokens]
            print(f"  Token types: {tokens}")
            print()
    except Exception as e:
        print(f"Errore discovery: {e}")

asyncio.run(discover())