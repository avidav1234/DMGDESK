# 🎯 GUIDA INSTALLAZIONE - CALIBRA ONLY CONFIGURABILE V14

## 📦 COSA INCLUDE QUESTO UPGRADE

### **Nuove Funzionalità:**
1. ⚙️ **Dialog Impostazioni** - Popup configurazione CALIBRA ONLY
2. 🧠 **Logica Avanzata** - 4 modalità intelligenti
3. 📝 **Genera MAIN Migliorato** - Con CALIBRA ONLY configurabile
4. 📊 **Anteprima** - Preview prima di generare

### **4 Modalità CALIBRA ONLY:**
- ❌ **Mai** - Nessun CALIBRA ONLY
- ▶️ **Solo Inizio** - Solo primo utensile
- ✨ **Finitura** - Ogni utensile FF (frese finitura)
- ⚡ **Avanzato** - FF sempre + ogni 3° richiamo stesso utensile

---

## 📁 FILE DA COPIARE (3 file)

```
tool_manager_v14/
├── ui/
│   └── calibra_only_settings_dialog.py    ⭐ NUOVO
├── logic/
│   ├── calibra_only_logic.py              ⭐ NUOVO
│   └── main_generator_v14.py              ⭐ SOSTITUISCI main_generator.py
```

---

## 🔧 INSTALLAZIONE

### **STEP 1: Copia file nuovi**

```powershell
# Vai nella cartella progetto
cd tool_manager_v14

# Copia i file forniti:
# 1. ui/calibra_only_settings_dialog.py
# 2. logic/calibra_only_logic.py
# 3. logic/main_generator_v14.py
```

**IMPORTANTE:** Rinomina `main_generator_v14.py` in `main_generator.py` oppure aggiorna l'import in `tab_macchina.py`.

---

### **STEP 2: Modifica tab_macchina.py**

#### **A. Aggiungi imports (all'inizio del file):**

```python
# Dopo gli altri import, aggiungi:
from ui.calibra_only_settings_dialog import show_calibra_settings
from logic.calibra_only_logic import get_calibra_logic
```

Se usi `main_generator_v14.py`:
```python
# Sostituisci:
from logic.main_generator import genera_programma_main

# Con:
from logic.main_generator_v14 import genera_programma_main_with_preview
```

---

#### **B. Aggiungi pulsante ⚙️ nella toolbar**

Trova la sezione dove crei la toolbar (di solito in `_create_ui()`).

**PRIMA (esempio):**
```python
ctk.CTkButton(
    toolbar,
    text="📝 GENERA MAIN",
    command=self._genera_main
).pack(side="left", padx=5)
```

**DOPO:**
```python
# Gruppo MAIN
main_group = ctk.CTkFrame(toolbar, fg_color="transparent")
main_group.pack(side="left", padx=10)

# Pulsante GENERA MAIN
ctk.CTkButton(
    main_group,
    text="📝 GENERA MAIN",
    width=140,
    height=40,
    fg_color="#2196F3",
    hover_color="#1976D2",
    font=("Segoe UI", 12, "bold"),
    command=self._genera_main
).pack(side="left", padx=2)

# Pulsante IMPOSTAZIONI ⚙️
ctk.CTkButton(
    main_group,
    text="⚙️",
    width=45,
    height=40,
    fg_color="#9E9E9E",
    hover_color="#757575",
    font=("Segoe UI", 16),
    command=self._apri_impostazioni_calibra
).pack(side="left", padx=2)

# Label modalità corrente (opzionale)
self.calibra_mode_label = ctk.CTkLabel(
    main_group,
    text="",
    font=("Segoe UI", 9),
    text_color="#757575"
)
self.calibra_mode_label.pack(side="left", padx=10)

self._update_calibra_mode_label()
```

---

#### **C. Aggiungi funzioni alla classe TabMacchina**

Alla fine della classe `TabMacchina`, aggiungi:

```python
def _apri_impostazioni_calibra(self):
    """Apre dialog impostazioni CALIBRA ONLY."""
    show_calibra_settings(self.parent)
    self._update_calibra_mode_label()

def _update_calibra_mode_label(self):
    """Aggiorna label con modalità corrente."""
    try:
        calibra_logic = get_calibra_logic()
        mode_desc = calibra_logic.get_mode_description()
        self.calibra_mode_label.configure(text=f"Modalità: {mode_desc}")
    except:
        self.calibra_mode_label.configure(text="")
```

---

#### **D. Modifica funzione _genera_main esistente**

**PRIMA:**
```python
def _genera_main(self):
    # ... codice esistente ...
    success, msg = genera_programma_main(df_macchina, "MAIN")
    # ...
```

**DOPO:**
```python
def _genera_main(self):
    """Genera programma MAIN con CALIBRA ONLY configurabile."""
    if self.main.df.empty:
        messagebox.showwarning("Attenzione", "Nessun utensile in macchina")
        return
    
    # Filtra solo utensili IN_MACCHINA
    df_macchina = self.main.df[
        self.main.df['Stato_Utensile'] == 'IN_MACCHINA'
    ].copy()
    
    if df_macchina.empty:
        messagebox.showwarning("Attenzione", "Nessun utensile in macchina")
        return
    
    # Genera con preview e logica CALIBRA ONLY
    success, msg = genera_programma_main_with_preview(
        df_macchina,
        nome_cartella="MAIN",
        parent=self.parent
    )
    
    if success:
        messagebox.showinfo("✅ Successo", msg, parent=self.parent)
    else:
        if msg not in ["Generazione annullata", "Annullato"]:
            messagebox.showerror("Errore", msg, parent=self.parent)
```

---

## 🧪 TEST

### **1. Avvia applicazione:**
```powershell
python main.py
```

### **2. Vai al tab "In Macchina"**

### **3. Click su pulsante ⚙️ (impostazioni)**

Dovresti vedere il popup con 4 opzioni:
```
❌ Mai
▶️ Solo Inizio
✨ Finitura
⚡ Avanzato
```

### **4. Seleziona una modalità e salva**

### **5. Click su "GENERA MAIN"**

Dovresti vedere:
1. **Anteprima** con statistiche CALIBRA ONLY
2. Chiede conferma
3. Genera file MAIN con CALIBRA ONLY secondo impostazioni

---

## 📊 ESEMPI OUTPUT

### **Modalità: Mai**
```
; PROGRAMMA MAIN O9999 - MAIN
; Generato: 2025-12-26 10:30
; Utensili: 12
; CALIBRA ONLY: ❌ Nessun CALIBRA ONLY
%
O9999
;
T1 (FF10R0.5L50F60G3)
T2 (FS12R1L60F70H8)
T3 (FF8R0.3L40F50G2)
...
;
M30
%
```

### **Modalità: Finitura**
```
; PROGRAMMA MAIN O9999 - MAIN
; Generato: 2025-12-26 10:30
; Utensili: 12
; CALIBRA ONLY: ✨ Tutti gli utensili FF
%
O9999
;
T1 (FF10R0.5L50F60G3)
G65 P9832 T1 ;CALIBRA ONLY
T2 (FS12R1L60F70H8)
T3 (FF8R0.3L40F50G2)
G65 P9832 T3 ;CALIBRA ONLY
...
;
M30
%
```

### **Modalità: Avanzato**
```
; PROGRAMMA MAIN O9999 - MAIN
; Generato: 2025-12-26 10:30
; Utensili: 12
; CALIBRA ONLY: ⚡ FF + ogni 3 richiami
%
O9999
;
T1 (FF10R0.5L50F60G3)
G65 P9832 T1 ;CALIBRA ONLY
T2 (FS12R1L60F70H8)
T3 (FF8R0.3L40F50G2)
G65 P9832 T3 ;CALIBRA ONLY
T4 (FS12R1L60F70H8)  ; 2° richiamo
T5 (P10-30VDF60E3)
T6 (FS12R1L60F70H8)  ; 3° richiamo
G65 P9832 T6 ;CALIBRA ONLY
...
;
M30
%
```

---

## 📂 FILE GENERATI

### **calibra_only_settings.json**

Quando salvi le impostazioni, viene creato questo file nella root del progetto:

```json
{
  "mode": "finitura",
  "last_updated": "2025-12-26T10:30:00"
}
```

Questo file salva le preferenze dell'utente e viene letto all'avvio.

---

## 🎨 INTERFACCIA UTENTE

### **Toolbar "In Macchina":**
```
┌─────────────────────────────────────────────────────────┐
│ ➕ Aggiungi  ✏️ Modifica  🗑️ Elimina  │  📝 GENERA MAIN ⚙️  │
│                                       Modalità: ✨ Finitura│
└─────────────────────────────────────────────────────────┘
```

### **Popup Impostazioni:**
```
┌──────────────────────────────────────────────┐
│  ⚙️ CONFIGURAZIONE CALIBRA ONLY              │
├──────────────────────────────────────────────┤
│ Scegli quando inserire CALIBRA ONLY:         │
│                                              │
│ ○ ❌ Mai - Nessun CALIBRA ONLY              │
│   Il MAIN non conterrà alcun comando...     │
│                                              │
│ ● ✨ Finitura - Ogni utensile FF            │
│   CALIBRA ONLY per tutti gli utensili FF    │
│                                              │
│ ○ ⚡ Avanzato - Finitura + ogni 3 richiami │
│   FF sempre + ogni terzo uso...             │
│                                              │
│                        [❌ Annulla] [✅ Salva]│
└──────────────────────────────────────────────┘
```

### **Anteprima MAIN:**
```
┌──────────────────────────────────────────────┐
│  📊 ANTEPRIMA CALIBRA ONLY                   │
├──────────────────────────────────────────────┤
│ ⚙️ Modalità: ✨ Tutti gli utensili FF        │
│                                              │
│ 🔧 Utensili totali: 12                       │
│ 📏 Con CALIBRA ONLY: 4                       │
│ 📈 Percentuale: 33.3%                        │
│                                              │
│ Procedere con la generazione?               │
│                        [No] [Sì]            │
└──────────────────────────────────────────────┘
```

---

## 🔍 CLASSIFICAZIONE UTENSILI

### **Finitura (FF):**
```python
UTENSILI_FINITURA = ['FF']
```

Riconosciuti:
- `FF10R0.5L50F60G3`
- `FFHSC12R1L60F70E2`
- `FFPI8R0.3L40F50G1`

### **Sgrosatura (FS, P, PI, ecc):**
```python
UTENSILI_SGROSATURA = ['FS', 'FSHSC', 'FSHPC', 'P', 'PI', 'R', 'C', 'FP', 'FR', 'SMS', 'D']
```

Riconosciuti:
- `FS12R1L60F70H8`
- `FSHSC10R0.8L55F65G3`
- `P10-30VDF60E3`
- `PI8-25VDF55G2`
- `R60R2L10F80H10`
- `D100R3L5F90H12`
- `SMS10X90F60H8`

---

## 📝 NOTE IMPLEMENTAZIONE

### **Contatore richiami (modalità Avanzato):**

La logica tiene traccia di quante volte ogni utensile viene chiamato:

```python
tool_call_count = {
    'FS12R1L60F70H8': 3,  # Terzo richiamo → CALIBRA ONLY
    'P10-30VDF60E3': 1,
    'FF10R0.5L50F60G3': 2
}
```

Il contatore viene resettato all'inizio di ogni generazione MAIN.

### **Persistenza impostazioni:**

Le impostazioni vengono salvate in `calibra_only_settings.json` nella root del progetto e ricaricate all'avvio.

---

## 🐛 TROUBLESHOOTING

### **Pulsante ⚙️ non appare:**
→ Verifica di aver aggiunto il codice nella toolbar
→ Controlla che `calibra_only_settings_dialog.py` sia in `ui/`

### **Errore "No module named 'ui.calibra_only_settings_dialog'":**
→ Verifica che il file sia nella cartella `ui/`
→ Controlla che ci sia `__init__.py` in `ui/`

### **CALIBRA ONLY non appare nel MAIN:**
→ Controlla che hai sostituito/aggiornato `main_generator.py`
→ Verifica che la modalità non sia "Mai"
→ Controlla che gli utensili siano classificati correttamente

### **Anteprima non si apre:**
→ Usa `genera_programma_main_with_preview` invece di `genera_programma_main`

---

## ✅ CHECKLIST INSTALLAZIONE

Prima di testare, verifica:

```
✅ File calibra_only_settings_dialog.py in ui/
✅ File calibra_only_logic.py in logic/
✅ File main_generator_v14.py in logic/
✅ Import aggiunti in tab_macchina.py
✅ Pulsante ⚙️ aggiunto nella toolbar
✅ Funzioni _apri_impostazioni_calibra() e _update_calibra_mode_label() aggiunte
✅ Funzione _genera_main() aggiornata
✅ App si avvia senza errori
```

---

## 🚀 ESTENSIONI FUTURE

Possibili miglioramenti:
1. **Profili multipli** - Salva più configurazioni
2. **CALIBRA EVERY N** - Ogni N richiami invece di 3 fisso
3. **Per tipo utensile** - Configurazione diversa per P, PI, R, ecc.
4. **Import/Export** - Condividi configurazioni
5. **Log calibrazioni** - Storico CALIBRA ONLY generati

---

**INSTALLAZIONE COMPLETATA! 🎉**
