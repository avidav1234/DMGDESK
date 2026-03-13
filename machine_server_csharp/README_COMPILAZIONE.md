# DMG Machine Server — Istruzioni compilazione

## Requisiti
- Windows con Visual Studio (qualsiasi versione dal 2005 in poi)
- Oppure .NET Framework SDK 2.0+ (già presente su qualsiasi PC Windows moderno)

## Compilazione con Visual Studio
1. Apri `MachineServer.csproj` in Visual Studio
2. Build → Build Solution  (oppure Ctrl+Shift+B)
3. Il file `MachineServer.exe` si trova in `bin\Release\`

## Compilazione da riga di comando (senza Visual Studio)
Apri il Prompt dei comandi e digita:

```
C:\Windows\Microsoft.NET\Framework\v2.0.50727\csc.exe ^
  /target:winexe ^
  /out:MachineServer.exe ^
  /reference:System.dll ^
  /reference:System.Drawing.dll ^
  /reference:System.Windows.Forms.dll ^
  Program.cs ServerConfig.cs SocketServer.cs ServerForm.cs
```

Oppure con .NET 4.x (più comune sui PC moderni):
```
C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe ^
  /target:winexe ^
  /out:MachineServer.exe ^
  /reference:System.dll ^
  /reference:System.Drawing.dll ^
  /reference:System.Windows.Forms.dll ^
  Program.cs ServerConfig.cs SocketServer.cs ServerForm.cs
```

## Installazione sulla macchina XP
1. Copia `MachineServer.exe` nella macchina (es. `C:\MachineServer\`)
2. Avvia `MachineServer.exe` — si minimizza automaticamente nella taskbar
3. Dal menu → **Impostazioni** imposta la cartella NC corretta
4. Opzionale: aggiungi `MachineServer.exe` all'avvio automatico di Windows

## Configurazione
Il file `server_config.ini` viene creato automaticamente nella stessa cartella dell'exe:

```ini
[server]
port=9999
base_path=C:\percorso\cartella\NC
```

Modificabile sia dal menu Impostazioni che direttamente con il Blocco Note.

## Note Windows XP
- .NET 2.0 è già installato su Windows XP SP2 e SP3
- Se non presente: scarica da Microsoft .NET Framework 2.0 Redistributable
- Nessun'altra dipendenza richiesta
