# Programmi NC — Sincronizzazione automatica TOOL_SYNC

**Macchina:** DMG DMC 160U | **CNC:** Siemens 840D PowerLine

## File

| File | Tipo | Descrizione |
|------|------|-------------|
| `TOOL_SYNC.MPF` | MPF | Programma principale — chiama i due SPF |
| `SAVE_TOA.SPF` | SPF | Genera TOOL_SYNC.TOA con dati utensili live |
| `SAVE_TMA.SPF` | SPF | Genera TOOL_SYNC.TMA con posizioni magazzino live |

## Come funziona

Il programma legge le variabili di sistema Siemens con **indici costanti** (obbligatorio su 840D PowerLine — gli indici variabili causano allarme 17020) e scrive i file TOA/TMA usando `WRITE()` nella memoria NC locale, poi li copia sulla share di rete con `COPYFILE()`.

**Valori letti live:**
- `$TC_TP8[T]` — stato utensile (enabled/disabled)
- `$TC_DP3[T,D]` — lunghezza Z (compensazione attuale)
- `$TC_DP6[T,D]` — raggio (compensazione attuale)
- `$TC_MOP1[T,D]` — flag monitoraggio vita
- `$TC_MOP2[T,D]` — vita residua (il valore chiave per Tool Manager)
- `$TC_MOP11[T,D]` — vita di riferimento
- `$TC_MPP6[mag,pos]` — T-number per ogni posizione magazzino

## Prerequisiti

### 1. Creare la cartella WPD dalla macchina
Da HMI → Gestione programmi → creare cartella:
```
//NC/WKS.DIR/_TOOLSYNC.WPD/
```
⚠️ NON creare da Windows Explorer — le cartelle WPD devono essere create dall'HMI.

### 2. Caricare i file SPF/MPF sulla NCU
Da HMI → Gestione programmi → caricare nella directory appropriata:
```
//NC/SPF.DIR/SAVE_TOA.SPF
//NC/SPF.DIR/SAVE_TMA.SPF
//NC/MPF.DIR/TOOL_SYNC.MPF
```

### 3. Configurare il path di copia rete
In `SAVE_TOA.SPF` e `SAVE_TMA.SPF` adattare il path `COPYFILE`:

```
; Opzione A — drive ACTTRANSFER (se configurato)
_TS_RET = COPYFILE("//NC/WKS.DIR/_TOOLSYNC.WPD/TOOL_SYNC.TOA",
                   "//ACTTRANSFER/P_DRIVE/DMG_DMC_160U/TOOL_SYNC.TOA")

; Opzione B — path rete Windows diretto (se NCU ha accesso)
_TS_RET = COPYFILE("//NC/WKS.DIR/_TOOLSYNC.WPD/TOOL_SYNC.TOA",
                   "//192.168.214.241/DMG_DMC_160U/TOOL_SYNC.TOA")
```

## Utilizzo

### Automatico — fine programma pezzo
Aggiungere **prima di M30** nel programma principale:
```gcode
CALL "SAVE_TOA.SPF"
CALL "SAVE_TMA.SPF"
M30
```

### Automatico — fine pallet
Aggiungere nel programma pallet dopo l'ultimo ciclo:
```gcode
; ... lavorazioni ...
CALL "TOOL_SYNC.MPF"
M99
```

### Manuale — da MDI
```
CALL "TOOL_SYNC.MPF"
```

## Stima tempi di esecuzione

| Programma | Istruzioni WRITE | Tempo stimato |
|-----------|-----------------|---------------|
| SAVE_TOA.SPF | ~1394 | ~60-90 secondi |
| SAVE_TMA.SPF | ~24 | ~2-3 secondi |
| **Totale** | **~1418** | **~60-95 secondi** |

⚠️ Il tempo dipende dalla velocità del filesystem NCU. Su 840D PowerLine WRITE() è sincrono.

## Note tecniche

- Il programma **non interrompe la produzione** — va chiamato dopo M30/M99 quando il ciclo è terminato
- Gli utensili nel file sono quelli presenti **al momento della generazione del TOA** (98 utensili, 100 taglienti)
- Il file TOA viene prima cancellato (`DELETEFILE`) poi riscritto — nessun rischio di file corrotto
- Il TMA usa `$TC_MPP6[mag,pos]` con tutti gli indici costanti: 120 posizioni Regal + 4 Belade + 4 buffer + 1 punto carico
