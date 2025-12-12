# NavalViewer

App semplice per visualizzare carte nautiche e ricevere dati AIS via UDP.

Requisiti
- Python 3.8+
- Installare dipendenze:

```powershell
python -m pip install -r requirements.txt
```

Esecuzione

```powershell
python project\main.py
```

Uso
- Inserire `host` e `port` UDP (es. `0.0.0.0` e `10110`) e premere `Start Listener`.
- I messaggi NMEA e AIS ricevuti appariranno in basso; quando viene riconosciuta una posizione valida il marker si muove sulla mappa.

Note
- Il parsing AIS è "best-effort": installare `pyais` per una migliore decodifica.
- Se non si ha PyQtWebEngine disponibile, installare `PyQtWebEngine` come indicato in `requirements.txt`.
