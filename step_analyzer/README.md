# STEP Analyzer — microservizio geometrico

Servizio separato da DMGDesk, porta 8001.
Estrae features geometriche da file STEP e calcola similarità tra commesse.

## Installazione (una volta sola)
```
pip install cadquery uvicorn fastapi httpx
```

## Avvio
Doppio click su `start.bat` oppure:
```
cd C:\Tool_App\step_analyzer
uvicorn main:app --host 0.0.0.0 --port 8001
```

## Endpoints
- GET  http://localhost:8001/stato
- POST http://localhost:8001/analizza
- GET  http://localhost:8001/simili/{commessa}
- GET  http://localhost:8001/storico
