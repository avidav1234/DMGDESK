# 🐳 GUIDA DOCKER — Tool Manager V14
**Installazione Docker Desktop su Windows e avvio della dashboard web**

---

## PARTE 1 — Installa Docker Desktop

### Passo 1 — Verifica requisiti Windows

Docker Desktop richiede Windows 10/11 con **WSL 2** (Windows Subsystem for Linux).

Apri PowerShell come amministratore e digita:

```powershell
wsl --version
```

Se risponde con un numero di versione → vai al Passo 3.
Se dà errore o mostra versione 1 → esegui prima:

```powershell
wsl --install
wsl --set-default-version 2
```

Potrebbe richiedere un riavvio del PC.

### Passo 2 — Scarica Docker Desktop

Vai su:
```
https://www.docker.com/products/docker-desktop/
```

Clicca **"Download for Windows"** (file `.exe`, circa 500 MB).

### Passo 3 — Installa Docker Desktop

Esegui il file scaricato. Durante l'installazione:
- Lascia spuntato **"Use WSL 2 instead of Hyper-V"** ← importante
- Lascia spuntato **"Add shortcut to desktop"**
- Clicca Install

Al termine, **riavvia il PC** quando richiesto.

### Passo 4 — Primo avvio Docker Desktop

Dopo il riavvio, apri **Docker Desktop** dalla scrivania.
Al primo avvio:
- Accetta i termini di licenza
- Salta la creazione account (clicca "Continue without signing in")
- Attendi che l'icona 🐳 nella barra di sistema diventi verde

### Passo 5 — Verifica installazione

Apri PowerShell:

```powershell
docker --version
docker compose version
```

Deve rispondere qualcosa come:
```
Docker version 27.x.x
Docker Compose version v2.x.x
```

---

## PARTE 2 — Preparazione progetto

### Passo 6 — Crea la cartella dati

Il database CSV deve stare fuori dal container, in una cartella `/data`:

```powershell
cd C:\Tool_App\tool_manager_v14\tool_manager
mkdir data
```

Copia i tuoi file CSV nella cartella `data\`:
```
data\
  Database_DMG160U.csv
  Database_DMG160U_utensili_smontati.csv
  Database_DMG160U_holder_smontati.csv
  Database_DMG160U_bussole_idraulico.csv
```

### Passo 7 — Aggiorna config.json

Apri `config.json` con Notepad e modifica il percorso database per puntare alla cartella `/data` **dentro il container** (non il percorso Windows):

```json
{
    "database_path": "/data/Database_DMG160U.csv"
}
```

> ⚠️ Usa sempre `/data/...` con slash forward, non backslash — è il percorso Linux dentro il container.

---

## PARTE 3 — Avvio con Docker

### Passo 8 — Build e avvio (prima volta)

```powershell
cd C:\Tool_App\tool_manager_v14\tool_manager
docker compose up --build -d
```

La prima volta scarica le immagini e costruisce i container — può volerci **3-5 minuti**.
Le volte successive (senza `--build`) parte in **10-15 secondi**.

Vedrai l'output:
```
✔ Container toolmanager-backend   Started
✔ Container toolmanager-frontend  Started
```

### Passo 9 — Verifica che funzioni

```powershell
docker compose ps
```

Entrambi i servizi devono essere **running**:
```
NAME                    STATUS          PORTS
toolmanager-backend     Up (healthy)    8000/tcp
toolmanager-frontend    Up              0.0.0.0:80->80/tcp
```

Apri il browser:
```
http://localhost
```

Dovresti vedere la dashboard Tool Manager. ✅

---

## PARTE 4 — Accesso dalla LAN

### Trova l'IP del PC server

```powershell
ipconfig
```

Cerca **"IPv4 Address"** sotto la scheda di rete attiva, es.: `192.168.1.45`

### Da qualsiasi altro PC in rete

Apri il browser e vai su:
```
http://192.168.1.45
```

sostituendo con l'IP reale del PC in officina.

> 💡 **Firewall Windows**: Se altri PC non riescono ad aprire la pagina, devi aprire la porta 80:
> Pannello di Controllo → Windows Defender Firewall → Regole in entrata → Nuova regola → Porta → TCP 80 → Consenti

---

## PARTE 5 — Comandi quotidiani

```powershell
# Avvia (ogni mattina / dopo riavvio PC)
docker compose up -d

# Ferma (alla fine della giornata)
docker compose down

# Vedi i log in tempo reale
docker compose logs -f

# Solo log del backend
docker compose logs -f backend

# Aggiorna dopo un git pull (rebuild)
git pull
docker compose up --build -d

# Stato dei container
docker compose ps
```

---

## PARTE 6 — Aggiornamento versione

Quando esce una nuova versione del codice:

```powershell
cd C:\Tool_App\tool_manager_v14\tool_manager

# 1. Scarica aggiornamenti da GitHub
git pull

# 2. Ricostruisci e riavvia
docker compose up --build -d
```

I CSV in `data\` rimangono intatti — solo il codice viene aggiornato.

---

## 🆘 Risoluzione problemi comuni

### Docker Desktop non si avvia
→ Verifica che WSL 2 sia installato: `wsl --version` in PowerShell come admin.
→ Riavvia il servizio: Task Manager → cerca "Docker Desktop Service" → Riavvia.

### "port 80 is already in use"
Un altro programma usa la porta 80 (IIS, Apache, etc.).
Cambia la porta nel `docker-compose.yml`:
```yaml
ports:
  - "8080:80"    # usa porta 8080 invece di 80
```
E accedi con `http://localhost:8080`.

### Il frontend si apre ma l'API dà errore
→ Controlla che il `config.json` usi `/data/...` e non `C:\...`.
→ Controlla i log: `docker compose logs backend`.

### I dati CSV non vengono trovati
→ Verifica che la cartella `data\` contenga i CSV con i nomi corretti.
→ Verifica che `config.json` punti a `/data/NomeFile.csv`.

### "Cannot connect to Docker daemon"
→ Docker Desktop non è avviato. Aprilo dalla scrivania e attendi l'icona verde.

---

## 📋 Riepilogo struttura finale

```
tool_manager\
├── api\                  ← Backend FastAPI
├── frontend\             ← Dashboard React
├── logic\                ← Logica (invariata)
├── database\             ← DB handler (invariato)
├── data\                 ← ⭐ CSV qui (NON nel container)
│   ├── Database_DMG160U.csv
│   └── ...
├── config.json           ← Punta a /data/...
├── docker-compose.yml    ← Avvia tutto
├── Dockerfile.backend
├── Dockerfile.frontend
└── nginx.conf
```
