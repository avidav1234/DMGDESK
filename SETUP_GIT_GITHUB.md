# 🚀 GUIDA SETUP GIT + GITHUB — Tool Manager V14
**Per chi parte da zero su Windows, senza Git installato**

---

## PARTE 1 — Installazione Git su Windows

### Passo 1 — Scarica Git for Windows

Apri il browser e vai su:
```
https://git-scm.com/download/win
```

Clicca **"Click here to download"** — scarica il file `.exe` (circa 50 MB).

### Passo 2 — Installa Git

Esegui il file scaricato. Durante l'installazione:

| Schermata | Scelta consigliata |
|-----------|-------------------|
| Select Components | Lascia tutto spuntato |
| Default editor | **Notepad** (o quello che preferisci) |
| Initial branch name | `main` (seleziona "Override") |
| PATH environment | **"Git from the command line and also from 3rd-party"** ← importante |
| Line endings | **"Checkout as-is, commit Unix-style"** |
| Terminal | **Windows' default console window** |
| Tutto il resto | Default |

### Passo 3 — Verifica installazione

Apri **PowerShell** (tasto Windows → digita `powershell`) e digita:

```powershell
git --version
```

Deve rispondere qualcosa come `git version 2.47.0.windows.1`.

---

## PARTE 2 — Configurazione Git (da fare una sola volta)

Sempre in PowerShell, inserisci il tuo nome e la tua email:

```powershell
git config --global user.name "Il Tuo Nome"
git config --global user.email "tua@email.com"
```

> 💡 Questi dati appariranno nei commit — non devono essere necessariamente quelli di GitHub.

---

## PARTE 3 — Crea account GitHub

Se non hai già un account:

1. Vai su **https://github.com**
2. Clicca **"Sign up"**
3. Scegli un username (es. `toolmanager-officina`) e una password
4. Verifica l'email

---

## PARTE 4 — Crea il repository su GitHub

1. Una volta loggato su GitHub, clicca il **"+"** in alto a destra → **"New repository"**
2. Compila così:

| Campo | Valore |
|-------|--------|
| Repository name | `tool-manager` |
| Description | `Gestore Utensili CNC — DMG 160U` |
| Visibility | **Private** ← il codice resta solo tuo |
| Initialize with README | ❌ NO (ne abbiamo già uno) |
| Add .gitignore | ❌ NO (ne abbiamo già uno) |

3. Clicca **"Create repository"**
4. GitHub mostrerà una pagina con l'URL del repo — **copia quell'URL**, servirà tra poco. Sarà simile a:
```
https://github.com/tuo-username/tool-manager.git
```

---

## PARTE 5 — Autentica Git con GitHub (token)

GitHub non accetta più la password normale. Devi creare un **Personal Access Token**.

### Crea il token

1. Su GitHub: icona profilo (in alto a destra) → **Settings**
2. Scorri fino a **Developer settings** (in fondo al menu laterale)
3. **Personal access tokens** → **Tokens (classic)**
4. Clicca **"Generate new token (classic)"**
5. Compila:
   - **Note:** `Tool Manager PC Officina`
   - **Expiration:** `No expiration` (o 1 anno se preferisci)
   - **Scopes:** spunta solo `repo` ← basta questo
6. Clicca **"Generate token"**
7. **COPIA IL TOKEN ORA** — GitHub non te lo mostrerà più!
   Sarà una stringa tipo: `ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456`

### Salva le credenziali su Windows

In PowerShell:

```powershell
git config --global credential.helper manager
```

La prima volta che farai un `git push`, Windows chiederà le credenziali:
- **Username:** il tuo username GitHub
- **Password:** incolla il **token** (NON la password GitHub)

Windows le salverà nel Credential Manager e non le chiederà più.

---

## PARTE 6 — Pubblica il progetto su GitHub

### Apri PowerShell nella cartella del progetto

```powershell
# Sostituisci con il percorso reale del tuo progetto
cd C:\Tool_App\tool_manager_v14
```

### Inizializza Git

```powershell
git init
git branch -M main
```

### Collega al repository GitHub

```powershell
# Sostituisci con l'URL che hai copiato al Passo 4
git remote add origin https://github.com/tuo-username/tool-manager.git
```

### Primo commit e push

```powershell
git add .
git commit -m "feat: Tool Manager V14.0 - architettura modulare, logging, test 88/88"
git push -u origin main
```

Windows chiederà le credenziali → inserisci username e **token** (non la password!).

Se tutto va bene vedrai qualcosa come:
```
Enumerating objects: 45, done.
...
Branch 'main' set up to track remote branch 'main' from 'origin'.
```

Vai su `https://github.com/tuo-username/tool-manager` — vedrai tutto il codice online. ✅

---

## PARTE 7 — Workflow quotidiano (dopo il setup)

Da questo momento, ogni volta che fai modifiche:

```powershell
cd C:\Tool_App\tool_manager_v14

# 1. Controlla cosa è cambiato
git status

# 2. Aggiungi i file modificati
git add .

# 3. Salva le modifiche con un messaggio
git commit -m "fix: corretto bug validazione diametro decimale"

# 4. Carica su GitHub
git push
```

**GitHub Actions parte automaticamente** dopo ogni `git push` e ti avvisa se i test falliscono.

---

## PARTE 8 — Pubblicare una Release (versione ufficiale)

Quando vuoi marcare una versione stabile (es. dopo aver aggiunto una feature):

```powershell
# Crea un tag di versione
git tag v14.1

# Carica il tag su GitHub → scatta la pipeline di release
git push origin v14.1
```

GitHub Actions:
1. Esegue tutti gli 88 test
2. Crea un file `ToolManager_v14.1.zip` con il codice pulito
3. Pubblica la release nella sezione **Releases** del tuo repository

Puoi scaricare e distribuire quel `.zip` su altri PC in officina.

---

## PARTE 9 — Vedere i risultati CI/CD

Dopo ogni `git push`, vai su:
```
https://github.com/tuo-username/tool-manager/actions
```

Vedrai la lista dei workflow eseguiti. Clicca su uno per vedere:
- ✅ Test passati (verde)
- ❌ Test falliti (rosso, con dettaglio dell'errore)
- 📊 Report copertura codice

---

## 🆘 Risoluzione problemi comuni

### "git" non riconosciuto come comando
→ Riapri PowerShell dopo aver installato Git. Se persiste: Pannello di Controllo → Sistema → Variabili d'ambiente → controlla che `C:\Program Files\Git\cmd` sia nel PATH.

### "Authentication failed"
→ Stai usando la password GitHub invece del token. Cancella le credenziali salvate:
Pannello di Controllo → Credential Manager → Windows Credentials → cerca `github.com` → rimuovi → riprova `git push`.

### "remote origin already exists"
```powershell
git remote set-url origin https://github.com/tuo-username/tool-manager.git
```

### I test falliscono in CI ma passano in locale
→ Guarda l'errore nella tab Actions. Spesso è un import mancante in `requirements.txt`. Aggiungi la dipendenza e fai un nuovo `git push`.

---

## 📋 Riepilogo comandi essenziali

| Comando | Quando usarlo |
|---------|---------------|
| `git status` | Vedere cosa è cambiato |
| `git add .` | Preparare tutti i file modificati |
| `git commit -m "messaggio"` | Salvare una versione |
| `git push` | Caricare su GitHub |
| `git pull` | Scaricare aggiornamenti da GitHub |
| `git log --oneline` | Vedere la storia dei commit |
| `git tag v14.X && git push origin v14.X` | Creare una release |
