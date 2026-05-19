from PyQt5.QtWidgets import QLabel


DESCRIPTION_STYLE = (
    'padding: 8px 10px; '
    'margin-bottom: 6px; '
    'background: #f4f6f8; '
    'border: 1px solid #d9dee5; '
    'border-radius: 4px; '
    'color: #333; '
    'font-family: "Segoe UI"; '
    'font-size: 16px;'
)


DESCRIPTION_TEXTS = {
    'porti': 'Gestione dei porti registrati: consulta l\'elenco, seleziona una riga per modificare i dati o aprire la dashboard, e usa Aggiorna per ricaricare le informazioni dal backend.',
    'vascelli': 'Gestione dei vascelli registrati: consulta l\'elenco, seleziona una riga per modificare i dati o aprire la dashboard, e usa Aggiorna per ricaricare le informazioni dal backend.',
    'componenti': 'Gestione dei componenti associati ai vascelli: seleziona un vascello dal menu a tendina per visualizzare i componenti registrati. Puoi aggiungere, modificare o eliminare componenti usando i pulsanti dedicati.',
    'tratte': 'Gestione delle tratte: visualizza l\'elenco delle tratte registrate, con i porti di partenza, arrivo e eventuali intermedi. Usa il pulsante "Aggiorna" per ricaricare i dati dal backend, e "Aggiungi" per creare una nuova tratta.',
    'corse': 'Visualizza le corse programmate. Seleziona una corsa per vedere i dettagli dei percorsi, ottimizzare o visualizzarla nel dashboard.',
    'corse_ottimizza_percorso': "Avvia l'ottimizzazione dei percorsi per la corsa selezionata. Scegli un vascello, imposta le opzioni e clicca 'Avvia' per eseguire l'ottimizzazione. Puoi anche scegliere di ottimizzare per tutti i vascelli disponibili.",
    'corse_ottimizza_giorno': 'Ottimizzazione giornaliera: seleziona i vascelli e imposta le opzioni per ottimizzare le rotte per il giorno specificato.',
    'corse_previsione_biglietti': "Previsione biglietti venduti per le corse programmate in un giorno a tua scelta. Seleziona le corse da includere nella previsione e clicca 'Previsione Biglietti' per avviare il processo.",
    'percorsi': 'Visualizza i percorsi associati a una corsa selezionata. Puoi filtrare i percorsi per vascello e vedere i dettagli di ciascun percorso.',
    'piani_operativi': 'Gestione dei piani operativi: visualizza i piani operativi registrati, con i dettagli dei vascelli coinvolti e le tratte programmate. Usa il pulsante "Aggiorna" per ricaricare i dati dal backend, e "Aggiungi" per creare un nuovo piano operativo.',
}


def make_description_label(key: str, parent=None) -> QLabel:
    label = QLabel(DESCRIPTION_TEXTS.get(key, ''), parent)
    label.setWordWrap(True)
    label.setStyleSheet(DESCRIPTION_STYLE)
    return label