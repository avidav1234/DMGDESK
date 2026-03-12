# 🚀 TOOL MANAGER V13 - CODE GENERATOR INTEGRATO

## ✨ NOVITÀ V13

### **Nuovo Tab: 📝 Generatore**

Generatore codici utensili DMG completamente integrato nell'applicazione.

---

## 📦 FILE MODIFICATI/NUOVI

### **NUOVI (2 file):**
1. `logic/code_generator_logic.py` - Logica generazione codici
2. `ui/tab_generatore.py` - Tab interfaccia integrata

### **MODIFICATO (1 file):**
1. `ui/main_window.py` - Aggiunto tab Generatore

---

## 🎯 FUNZIONALITÀ TAB GENERATORE

### **Genera Codice:**
- Seleziona tipologia utensile
- Inserisci parametri (D, R2/X, L, VD, FP)
- Seleziona porta-utensile + diametro
- Click **[✅ GENERA]**
- Ottieni: Commento CNC pronto

### **Aggiungi a Inventario:**

**[🏠 SCAFFALE]:**
- Codice completo con holder
- ✅ Decrementa holder da smontati
- ✅ Decrementa bussola (se presente)

**[🔧 MACCHINA]:**
- Chiede posizione (1-99)
- Codice completo con holder
- ✅ Decrementa holder da smontati
- ✅ Decrementa bussola (se presente)

**[📦 SMONTATI]:**
- Salva solo utensile BASE (senza holder)
- ❌ NON decrementa holder
- Per assemblaggio futuro

---

## 🔄 LOGICA INVARIANZA HOLDER

```
Holder Totali = Holder Smontati + Holder in Uso

SCAFFALE/MACCHINA → Usa holder → Decrementa da smontati ✅
SMONTATI → NON usa holder → Inventario invariato ✅
```

---

## 📋 ESEMPIO WORKFLOW

```
1. Tab Generatore
   ├─ Genera: "PM10X1.5F60H8"
   └─ Click [MACCHINA] pos 4
       ├─ Holder H8: 10 → 9
       └─ Database: "PM10X1.5F60H8" pos 4

2. Tab Generatore  
   ├─ Genera: "FSHSC10R0.5L50F60G3"
   └─ Click [SMONTATI]
       ├─ Database smontati: "FSHSC10R0.5L50F60" (senza G3!)
       └─ Holder NON decrementato

3. Tab Smontati
   ├─ Seleziona: "FSHSC10R0.5L50F60"
   ├─ Click [MONTA] → Holder G3 → pos 5
   └─ Holder G3: 15 → 14  (decrementato ADESSO)
```

---

## 🚀 INSTALLAZIONE V13

### **Sostituisci file in ToolManager V12.4:**

```
tool_manager_v12_4/
├── logic/
│   └── code_generator_logic.py  ⭐ NUOVO
├── ui/
│   ├── tab_generatore.py        ⭐ NUOVO
│   └── main_window.py           🔧 SOSTITUISCI
```

### **Avvia:**
```bash
python main.py
```

---

## ✅ TEST RAPIDO

1. Apri app
2. Carica database
3. Vai a tab **📝 Generatore**
4. Genera codice (es: Pettine-M, D=10, X=1.5, FP=60, Holder=CB, D10)
5. Click **[SCAFFALE]**
6. Verifica:
   - Tab Scaffale: utensile presente ✅
   - Tab Holder & Bussole: CB qty -1 ✅

---

## 🎨 DESIGN INTEGRATO

- Stile ToolManager (blu header, layout 2 colonne)
- Campi dinamici (come v3.0)
- Pulsanti azione verdi/blu/grigi
- Messaggi con riepilogo modifiche

---

## 🔧 DETTAGLI TECNICI

### **Riuso Codice:**
```python
# Funzioni esistenti riusate:
- smonta_utensile()
- salva_database()
- salva_database_holder_smontati()
- salva_database_bussole_idraulico()
```

### **Zero Duplicazione:**
- Stessa logica decremento holder di tab_scaffale
- Stessa logica smontaggio di db_handler
- Perfetta integrazione con flussi esistenti

---

**V13 = V12.4 + Code Generator Integrato! 🎉**
