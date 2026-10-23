# Stop Killing VIS-Games

Ältere Spiele von VIS-Games (vertrieben von rondomedia) müssen beim ersten Start mit einer Seriennummer online aktiviert werden. Der Aktivierungsserver `serials.rondomedia.de` antwortet aber nicht mehr bzw. spricht nur veraltete TLS-Versionen. Selbst mit einer gültigen, gekauften Seriennummer lässt sich das Spiel deshalb nicht mehr aktivieren und nicht mehr spielen.

Dieses Repository stellt ein Script bereit, das die Aktivierung offline durchführt, damit gekaufte Spiele weiter spielbar bleiben. Es ist für Besitzer einer legal erworbenen Kopie mit eigener Seriennummer gedacht.

## Unterstützte Spiele

| Spiel | Script |
|---|---|
| Flughafen-Feuerwehr-Simulator 2013 | [`ffs2013_activate.py`](ffs2013_activate.py) |

## Benutzung

Voraussetzungen: Windows und [Python 3](https://www.python.org/downloads/), keine weiteren Pakete nötig.

1. Spiel schließen.
2. Script mit deiner Seriennummer ausführen:

   ```
   python ffs2013_activate.py ABCD-EFGH-IJKL-MNOP
   ```

3. Spiel starten – es sollte direkt ins Hauptmenü gehen.

Die Aktivierung ist an die MAC-Adresse des Netzwerkadapters gebunden. Erkennt das Script den falschen Adapter (z. B. bei VPN- oder VM-Adaptern), im Aktivierungsdialog des Spiels auf das Telefon-Symbol unten rechts klicken und den dort angezeigten Aktivierungscode übergeben:

```
python ffs2013_activate.py ABCD-EFGH-IJKL-MNOP --mac 001122AABBCC
```

Weitere Optionen:

| Option | Funktion |
|---|---|
| `--list-macs` | Netzwerkadapter in der Reihenfolge anzeigen, in der das Spiel sie auswählt |
| `--check` | Prüfen, ob die vorhandenen Registry-Einträge gültig sind |
| `--remove` | Aktivierung aus der Registry entfernen |
