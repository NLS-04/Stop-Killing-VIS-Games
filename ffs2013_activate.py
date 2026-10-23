#!/usr/bin/env python3
"""
Offline-Aktivierung fuer "Flughafen-Feuerwehr-Simulator 2013" (Unity 3.5.6).

Nachgebaut aus SerialChecker.cs / MainMenu.cs:

    CheckSerial(mac):
        HASH == sha1_hex_lower(SALT + SERIAL + mac)

    SERIAL = (block1+block2+block3+block4)[:16].strip().lower()
    mac    = SerialChecker.GetMacAddress()  -> PhysicalAddress.ToString()
             (12 Hex-Zeichen, Grossbuchstaben, ohne Trenner), oder - falls
             kein Adapter gefunden wird - die Zufallszahl in
             FFS_2013_Final_GER_ACTIVATION.

PlayerPrefs liegen unter
    HKCU\\Software\\<companyName>\\<productName>
und jeder Wertname traegt das Unity-Suffix "_h<djb2-xor-Hash des Namens>"
(beim Lesen faellt der Player auf den Namen ohne Suffix zurueck).
Unity 3.5 speichert Strings als REG_SZ (RegSetValueExA, Typ 1) und liest in
GetString() ausschliesslich REG_SZ - REG_BINARY (Unity 4+) wird ignoriert.

Der im Spiel angezeigte "Aktivierungscode" ist genau die MAC, die in den Hash
eingeht. Am zuverlaessigsten ist es daher, diesen Code per --mac zu uebergeben.

Nutzung:
    python ffs2013_activate.py ABCD-EFGH-IJKL-MNOP
    python ffs2013_activate.py ABCD-EFGH-IJKL-MNOP --mac 001122AABBCC
    python ffs2013_activate.py --list-macs
    python ffs2013_activate.py --check
    python ffs2013_activate.py --remove
"""

import argparse
import ctypes
import hashlib
import re
import sys
import winreg
from ctypes import wintypes

COMPANY_NAME = "VIS-Games"
PRODUCT_NAME = "Flughafen-Feuerwehr-Simulator 2013"
REG_PATH = rf"Software\{COMPANY_NAME}\{PRODUCT_NAME}"

SALT = "2cm6qpkw3gcpRsnXTd8rxwzrjiopud"
PREF_HASH_KEY = "FFS_2013_Final_GER_HASH"
PREF_SERIAL_KEY = "FFS_2013_Final_GER_SERIAL"
PREF_ACTIVATION_KEY = "FFS_2013_Final_GER_ACTIVATION"


# --------------------------------------------------------------------------
# Unity PlayerPrefs (Windows-Registry)
# --------------------------------------------------------------------------

def unity_key_hash(name: str) -> int:
    """djb2-xor-Variante, die Unity an PlayerPrefs-Namen anhaengt."""
    h = 5381
    for b in name.encode("utf-8"):
        h = ((h * 33) ^ b) & 0xFFFFFFFF
    return h


def unity_value_name(name: str) -> str:
    return f"{name}_h{unity_key_hash(name)}"


def set_pref_string(key, name: str, value: str) -> None:
    winreg.SetValueEx(key, unity_value_name(name), 0, winreg.REG_SZ, value)


def get_pref_string(key, name: str):
    """Wie der Player: nur REG_SZ zaehlt, sonst gilt der Wert als leer."""
    for value_name in (unity_value_name(name), name):
        try:
            data, typ = winreg.QueryValueEx(key, value_name)
        except FileNotFoundError:
            continue
        return data if typ == winreg.REG_SZ else ""
    return None


def delete_pref(key, name: str) -> bool:
    try:
        winreg.DeleteValue(key, unity_value_name(name))
        return True
    except FileNotFoundError:
        return False


# --------------------------------------------------------------------------
# Serial / Hash (SerialChecker.cs)
# --------------------------------------------------------------------------

def normalize_serial(serial: str) -> str:
    """Bloecke zusammenfuegen, auf 16 Zeichen kuerzen, Trim, ToLower."""
    blocks = re.sub(r"[\s\-]", "", serial).upper()
    return blocks[:16].strip().lower()


def compute_hash(serial: str, mac: str) -> str:
    return hashlib.sha1((SALT + serial + mac).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# MAC-Ermittlung (SerialChecker.GetMacAddress) via GetAdaptersAddresses
# --------------------------------------------------------------------------

IF_TYPE_ETHERNET_CSMACD = 6
IF_TYPE_IEEE80211 = 71
IF_TYPE_TUNNEL = 131

# System.Net.NetworkInformation.NetworkInterfaceType -> Position in der
# Liste aus GetMacAddress(). Nicht gelistete Typen haben Index -1.
# FastEthernet*/Ethernet3Megabit liefert Windows praktisch nie.
TYPE_PRIORITY = {IF_TYPE_IEEE80211: 0, IF_TYPE_ETHERNET_CSMACD: 1}


class SOCKADDR(ctypes.Structure):
    _fields_ = [("sa_family", ctypes.c_ushort), ("sa_data", ctypes.c_char * 14)]


class SOCKET_ADDRESS(ctypes.Structure):
    _fields_ = [("lpSockaddr", ctypes.POINTER(SOCKADDR)), ("iSockaddrLength", ctypes.c_int)]


class IP_ADAPTER_ADDRESSES(ctypes.Structure):
    pass


IP_ADAPTER_ADDRESSES._fields_ = [
    ("Length", wintypes.ULONG),
    ("IfIndex", wintypes.DWORD),
    ("Next", ctypes.POINTER(IP_ADAPTER_ADDRESSES)),
    ("AdapterName", ctypes.c_char_p),
    ("FirstUnicastAddress", ctypes.c_void_p),
    ("FirstAnycastAddress", ctypes.c_void_p),
    ("FirstMulticastAddress", ctypes.c_void_p),
    ("FirstDnsServerAddress", ctypes.c_void_p),
    ("DnsSuffix", ctypes.c_wchar_p),
    ("Description", ctypes.c_wchar_p),
    ("FriendlyName", ctypes.c_wchar_p),
    ("PhysicalAddress", ctypes.c_ubyte * 8),
    ("PhysicalAddressLength", wintypes.DWORD),
    ("Flags", wintypes.DWORD),
    ("Mtu", wintypes.DWORD),
    ("IfType", wintypes.DWORD),
    ("OperStatus", ctypes.c_int),
    ("Ipv6IfIndex", wintypes.DWORD),
    ("ZoneIndices", wintypes.DWORD * 16),
    ("FirstPrefix", ctypes.c_void_p),
    ("TransmitLinkSpeed", ctypes.c_uint64),
    ("ReceiveLinkSpeed", ctypes.c_uint64),
]


def enumerate_adapters():
    """Liefert dicts mit name, mac, if_type, speed fuer alle Adapter."""
    iphlpapi = ctypes.windll.iphlpapi
    size = wintypes.ULONG(16 * 1024)
    for _ in range(4):
        buf = ctypes.create_string_buffer(size.value)
        ret = iphlpapi.GetAdaptersAddresses(0, 0, None, buf, ctypes.byref(size))
        if ret == 0:
            break
        if ret != 111:  # ERROR_BUFFER_OVERFLOW
            raise OSError(ret, "GetAdaptersAddresses fehlgeschlagen")
    else:
        raise OSError("GetAdaptersAddresses: Puffer zu klein")

    adapters = []
    ptr = ctypes.cast(buf, ctypes.POINTER(IP_ADAPTER_ADDRESSES))
    while ptr:
        a = ptr.contents
        mac = "".join(f"{b:02X}" for b in a.PhysicalAddress[:a.PhysicalAddressLength])
        speed = a.TransmitLinkSpeed if a.TransmitLinkSpeed != 0xFFFFFFFFFFFFFFFF else 0
        adapters.append({"name": a.FriendlyName, "desc": a.Description, "mac": mac,
                         "if_type": a.IfType, "speed": speed})
        ptr = a.Next
    return adapters


def game_mac_candidates():
    """Filter + Sortierung wie in SerialChecker.GetMacAddress()."""
    lst = [a for a in enumerate_adapters()
           if len(a["mac"]) >= 12 and a["if_type"] != IF_TYPE_TUNNEL]
    # Der Comparator im Spiel sortiert Typen mit hoeherem Listenindex zuerst
    # (Ethernet vor WLAN vor Sonstigem) und innerhalb eines Typs nach Speed
    # absteigend.
    lst.sort(key=lambda a: (-TYPE_PRIORITY.get(a["if_type"], -1), -a["speed"]))
    return lst


def detect_mac():
    cands = game_mac_candidates()
    return cands[0]["mac"] if cands else None


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def open_key(write: bool):
    if write:
        return winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_PATH, 0,
                                  winreg.KEY_READ | winreg.KEY_WRITE)
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)


def resolve_mac(arg_mac, key=None):
    if arg_mac:
        return re.sub(r"[^0-9A-Fa-f]", "", arg_mac).upper() if re.fullmatch(
            r"[0-9A-Fa-f:\-]{12,17}", arg_mac) else arg_mac.strip()
    mac = detect_mac()
    if mac:
        return mac
    # Kein Adapter: das Spiel verwendet die gespeicherte Zufallszahl.
    if key is not None:
        stored = get_pref_string(key, PREF_ACTIVATION_KEY)
        if stored:
            return stored
    return None


def cmd_list_macs():
    cands = game_mac_candidates()
    if not cands:
        print("Keine passenden Adapter gefunden (Spiel wuerde FFS_2013_Final_GER_ACTIVATION nutzen).")
        return
    for i, a in enumerate(cands):
        mark = "  <- wird vom Spiel verwendet" if i == 0 else ""
        print(f"{a['mac']}  type={a['if_type']:<3} speed={a['speed']:<12} {a['name']}{mark}")


def cmd_check(arg_mac):
    try:
        key = open_key(write=False)
    except FileNotFoundError:
        print(f"Registry-Schluessel fehlt: HKCU\\{REG_PATH}")
        return 1
    with key:
        serial = get_pref_string(key, PREF_SERIAL_KEY)
        stored = get_pref_string(key, PREF_HASH_KEY)
        mac = resolve_mac(arg_mac, key)
    print(f"Serial : {serial}")
    print(f"Hash   : {stored}")
    print(f"MAC    : {mac}")
    if serial is None or stored is None or mac is None:
        print("Ergebnis: UNGUELTIG (Eintraege fehlen)")
        return 1
    ok = compute_hash(serial, mac) == stored
    print("Ergebnis:", "OK - CheckSerial() liefert true" if ok else "UNGUELTIG")
    return 0 if ok else 1


def cmd_remove():
    try:
        key = open_key(write=True)
    except FileNotFoundError:
        print("Nichts zu entfernen.")
        return 0
    with key:
        for name in (PREF_SERIAL_KEY, PREF_HASH_KEY, PREF_ACTIVATION_KEY):
            if delete_pref(key, name):
                print(f"Entfernt: {unity_value_name(name)}")
    return 0


def cmd_activate(serial_raw, arg_mac):
    serial = normalize_serial(serial_raw)
    if len(serial) != 16:
        print(f"Serial muss 4x4 Zeichen haben, erhalten: '{serial_raw}'", file=sys.stderr)
        return 2
    with open_key(write=True) as key:
        mac = resolve_mac(arg_mac, key)
        if mac is None:
            # Gleiches Verhalten wie GetMacAddress() ohne Netzwerkadapter.
            import random
            mac = str(random.randint(100000, 999998))
            set_pref_string(key, PREF_ACTIVATION_KEY, mac)
        digest = compute_hash(serial, mac)
        set_pref_string(key, PREF_SERIAL_KEY, serial)
        set_pref_string(key, PREF_HASH_KEY, digest)

    print(f"Registry : HKCU\\{REG_PATH}")
    print(f"Serial   : {serial}   ({unity_value_name(PREF_SERIAL_KEY)})")
    print(f"MAC      : {mac}")
    print(f"Hash     : {digest}   ({unity_value_name(PREF_HASH_KEY)})")
    print("Falls das Spiel trotzdem nach der Serial fragt: Telefon-Symbol unten rechts,")
    print("dort angezeigten Aktivierungscode mit --mac uebergeben oder Serial + obigen")
    print("Hash fuer genau diesen Code direkt im Dialog eintragen.")
    return cmd_check(mac)


def main():
    p = argparse.ArgumentParser(description="Offline-Aktivierung Flughafen-Feuerwehr-Simulator 2013")
    p.add_argument("serial", nargs="?", help="Serial, z.B. ABCD-EFGH-IJKL-MNOP")
    p.add_argument("--mac", help="Aktivierungscode/MAC wie im Spiel angezeigt (sonst Auto-Erkennung)")
    p.add_argument("--list-macs", action="store_true", help="Adapter in der Reihenfolge des Spiels anzeigen")
    p.add_argument("--check", action="store_true", help="Vorhandene Eintraege pruefen")
    p.add_argument("--remove", action="store_true", help="Serial-Eintraege loeschen")
    args = p.parse_args()

    if sys.platform != "win32":
        sys.exit("Nur unter Windows lauffaehig (Registry).")
    if args.list_macs:
        cmd_list_macs()
        return 0
    if args.remove:
        return cmd_remove()
    if args.check:
        return cmd_check(args.mac)
    if not args.serial:
        p.error("Serial fehlt")
    return cmd_activate(args.serial, args.mac)


if __name__ == "__main__":
    sys.exit(main())
