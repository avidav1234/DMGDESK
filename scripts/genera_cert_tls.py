"""
scripts/genera_cert_tls.py — Genera un certificato TLS self-signed per DMG Desk.
==============================================================================

Usa la libreria `cryptography` (già dipendenza del progetto: la usa il relay VNC),
quindi NON serve openssl. Produce `certs/cert.pem` e `certs/key.pem` con SAN
(Subject Alternative Name) per l'hostname E l'IP del server — necessario perché i
browser moderni validano il SAN, non il CN.

Uso:
    py scripts/genera_cert_tls.py                      # auto-rileva hostname + IP LAN
    py scripts/genera_cert_tls.py --host dmgdesk --ip 10.95.20.50
    py scripts/genera_cert_tls.py --host dmgdesk --ip 10.95.20.50 --giorni 825

Poi (via consigliata, reverse proxy): vedi deploy/Caddyfile.
Alternativa (uvicorn TLS nativo):
    uvicorn api.main:app --host 0.0.0.0 --port 8000 \
        --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem

NOTA: un cert self-signed dà l'avviso "non attendibile" nel browser (accettabile su
LAN interna). Per toglierlo, importare `certs/cert.pem` tra le CA fidate dei client,
oppure usare una CA interna aziendale.
"""

import argparse
import datetime as _dt
import ipaddress
import socket
import sys
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    sys.exit("Manca 'cryptography'. Installa con: py -m pip install cryptography")


def _ip_lan_locale() -> str:
    """Best-effort: IP dell'interfaccia usata per uscire in rete (no traffico reale)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera cert TLS self-signed per DMG Desk")
    ap.add_argument("--host", default=socket.gethostname(), help="hostname (default: hostname macchina)")
    ap.add_argument("--ip", default=None, help="IP LAN del server (default: auto-rilevato)")
    ap.add_argument("--giorni", type=int, default=825, help="validità in giorni (default 825, max browser)")
    ap.add_argument("--out", default="certs", help="cartella output (default: certs/)")
    args = ap.parse_args()

    host = args.host.strip()
    ip = (args.ip or _ip_lan_locale()).strip()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # SAN: hostname, localhost, IP del server, 127.0.0.1
    san = [x509.DNSName(host), x509.DNSName("localhost")]
    ip_list = {ip, "127.0.0.1"}
    for ips in ip_list:
        try:
            san.append(x509.IPAddress(ipaddress.ip_address(ips)))
        except ValueError:
            pass

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, host),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DMG Desk"),
    ])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(minutes=5))
        .not_valid_after(now + _dt.timedelta(days=args.giorni))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    (out / "key.pem").write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    (out / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    print(f"OK — certificato generato in {out.resolve()}")
    print(f"  host: {host}")
    print(f"  IP  : {ip}")
    print(f"  SAN : {[getattr(n, 'value', str(n)) for n in san]}")
    print(f"  scadenza: {(now + _dt.timedelta(days=args.giorni)).date().isoformat()}")
    print("\nProssimo passo: avviare il reverse proxy (deploy/Caddyfile) "
          "oppure uvicorn con --ssl-keyfile/--ssl-certfile.")


if __name__ == "__main__":
    main()
