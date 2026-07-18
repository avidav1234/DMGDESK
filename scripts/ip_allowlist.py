"""
scripts/ip_allowlist.py — CLI di riserva per l'allowlist IP di DMG Desk.
=======================================================================

Rete di sicurezza: se attivando il filtro IP ci si chiude fuori dalla UI, si
recupera SEMPRE da console su CAM35 (la macchina del backend). Opera sullo stesso
`ip_allowlist.json` usato dal backend.

Eseguire dalla root del progetto:
    py scripts/ip_allowlist.py --list
    py scripts/ip_allowlist.py --add 192.168.244.140
    py scripts/ip_allowlist.py --add 192.168.244.0/24
    py scripts/ip_allowlist.py --remove 192.168.244.140
    py scripts/ip_allowlist.py --enable
    py scripts/ip_allowlist.py --disable          # sblocco d'emergenza
    py scripts/ip_allowlist.py --clear            # svuota lista e disabilita
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Punta allo stesso file del backend (che lo legge da cwd = root del progetto).
os.environ.setdefault("DMG_IP_ALLOWLIST_FILE", os.path.join(ROOT, "ip_allowlist.json"))
sys.path.insert(0, ROOT)

from api import ip_allowlist as ipa  # noqa: E402


def _stampa():
    s = ipa.stato()
    stato = "ATTIVO" if s["enabled"] else "disattivo"
    print(f"Filtro IP: {stato}")
    if s["ips"]:
        print("IP/reti ammessi:")
        for ip in s["ips"]:
            print(f"  - {ip}")
    else:
        print("IP/reti ammessi: (nessuno)")
    print("Nota: loopback (127.0.0.1) è SEMPRE ammesso.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Allowlist IP DMG Desk (riserva CLI)")
    ap.add_argument("--list", action="store_true", help="mostra lo stato")
    ap.add_argument("--add", metavar="IP", help="aggiunge un IP o rete CIDR")
    ap.add_argument("--remove", metavar="IP", help="rimuove un IP/CIDR")
    ap.add_argument("--enable", action="store_true", help="attiva il filtro")
    ap.add_argument("--disable", action="store_true", help="disattiva il filtro (sblocco)")
    ap.add_argument("--clear", action="store_true", help="svuota la lista e disattiva")
    args = ap.parse_args()

    fatto = False
    if args.clear:
        for ip in list(ipa.stato()["ips"]):
            ipa.rimuovi(ip)
        ipa.imposta_abilitato(False)
        print("Lista svuotata e filtro disattivato.")
        fatto = True
    if args.add:
        r = ipa.aggiungi(args.add)
        print(f"add {args.add}: {'OK' if r.get('ok') else 'NON valido'}")
        fatto = True
    if args.remove:
        ipa.rimuovi(args.remove)
        print(f"remove {args.remove}: OK")
        fatto = True
    if args.enable:
        ipa.imposta_abilitato(True)
        print("Filtro ATTIVATO.")
        fatto = True
    if args.disable:
        ipa.imposta_abilitato(False)
        print("Filtro disattivato (sblocco).")
        fatto = True

    if not fatto and not args.list:
        ap.print_help()
        return
    print("―" * 40)
    _stampa()


if __name__ == "__main__":
    main()
