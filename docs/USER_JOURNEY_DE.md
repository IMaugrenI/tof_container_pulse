# Nutzerreise aus der Praxis

## Ziel

Pulse starten, ein auffälliges Signal schnell erkennen, verstehen wo man hinschauen sollte und dabei nichts am Rechner verändern.

## Normaler Ablauf

1. Den passenden Starter für dein Betriebssystem ausführen.
2. Die Containerübersicht öffnet sich.
3. Auf **Läuft**, **Prüfen**, **Braucht Aufmerksamkeit** und **Unbekannt** schauen.
4. Wenn **Braucht Aufmerksamkeit** null ist, Hardware, Verbindungen, Speicher, Dienste und Sicherheit kurz durchsehen.
5. Wenn eine Seite **Prüfen** zeigt, die Empfehlung lesen und entscheiden, ob du weiter nachsehen möchtest.
6. Browser schließen, wenn du fertig bist.

**Erfolgreiches Ergebnis:** Du verstehst den aktuellen lokalen Zustand, ohne dass Pulse etwas am Rechner verändert hat.

## Etwas braucht Aufmerksamkeit

Wenn die Containerseite einen Eintrag unter **Braucht Aufmerksamkeit** zeigt:

1. die passende Zeile finden
2. Zustand und sichtbare Messwerte lesen
3. mit deinen normalen Systemwerkzeugen entscheiden, was genauer geprüft werden soll
4. nicht erwarten, dass Pulse den Container automatisch neu startet oder repariert

Pulse ist die Übersicht, nicht die Steuerung.

## Informationen fehlen

Wenn ein Wert **Unbekannt** oder **N/A** ist, prüfe zuerst, ob dieses Signal auf deinem Betriebssystem verfügbar ist oder ob das zugrunde liegende Werkzeug, zum Beispiel Docker, läuft.

Ein fehlendes Signal soll nicht die gesamte Suite unbrauchbar machen.

## Stoppen und später zurückkehren

Ein Einmallauf braucht keinen Stop-Befehl. Browser schließen reicht.

Wenn du den Watch-Modus genutzt hast, beendest du ihn mit `Ctrl+C`. Für eine neue Übersicht startest du Pulse später einfach erneut.
