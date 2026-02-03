# Istruzioni per l'installazione e l'esecuzione del progetto

Queste istruzioni sono destinate a un ambiente Microsoft Windows. Si raccomanda
di utilizzare il Prompt dei comandi (cmd.exe). Non usare PowerShell a meno che
non si conoscano le differenze di attivazione degli ambienti virtuali.

Requisiti preliminari
- Git installato e disponibile nel PATH.
- Python 3.8 - 3.11 installato e disponibile nel PATH (verificare con `python --version`).
- Connessione internet per clonare il repository e scaricare le dipendenze.

Passaggi dettagliati

1) Aprire il Prompt dei comandi

- Premi `Win` → digita "cmd" → premi `Invio`.

2) Creare e posizionarsi nella cartella di lavoro

Eseguire i comandi seguenti per creare una cartella chiamata `SMART` sul
Desktop e spostarvisi:

```cmd
cd %USERPROFILE%\Desktop
mkdir SMART
cd SMART
```

3) Clonare il repository

Clonare il progetto remoto nella cartella corrente:

```cmd
git clone https://github.com/SGRoboticsTeams/ProjectSMART.git
```

Questo creerà la cartella `ProjectSMART` all'interno di `SMART`.

4) Creare un ambiente virtuale Python

Creare un environment isolato per installare le dipendenze:

```cmd
python -m venv VENV_SMART
```

Nota: se il comando `python` non è riconosciuto, provare `py -3 -m venv VENV_SMART`.

5) Attivare l'ambiente virtuale (Prompt dei comandi)

Eseguire:

```cmd
VENV_SMART\Scripts\activate
```

Dopo l'attivazione, il prompt dovrebbe mostrare il prefisso `(VENV_SMART)`.

6) Aggiornare pip e installare le dipendenze

È buona pratica aggiornare `pip` prima dell'installazione:

```cmd
pip install -r smart-livingmap\requirements.txt
```

Se l'installazione dovesse fallire per pacchetti nativi, verificare di avere
le build tools necessari (ad esempio Microsoft Build Tools) o usare ruoli
precompilati (wheels) quando disponibili.

7) Avviare l'applicazione

Per eseguire l'applicazione principale:

```cmd
python smart-livingmap\main.py
```

Se tutto è configurato correttamente, l'applicazione dovrebbe avviarsi e
mostrare l'interfaccia o i log previsti.

Sezione di risoluzione problemi (breve)
- "'python' non è riconosciuto": aggiungere Python al PATH o usare il launcher `py`.
- Problemi con l'attivazione dell'ambiente su PowerShell: usare `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` (solo se si comprende la modifica della policy) oppure eseguire i comandi dal Prompt dei comandi.
- Errori durante `pip install`: leggere l'errore, installare eventuali librerie native richieste, o cercare una wheel compatibile per Windows.

Contatti e riferimenti
Per ulteriori dettagli sul progetto, consultare il repository originale su GitHub:

https://github.com/SGRoboticsTeams/ProjectSMART

---
File aggiornato per fornire istruzioni formali e passaggi dettagliati per
l'installazione e l'esecuzione su Windows.
