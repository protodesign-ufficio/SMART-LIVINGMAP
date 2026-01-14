# To Do List Living Map

### 1. DONE - Simulatore navi reali e simulate

Il simulatore deve essere in grado di generare due tipologie distinte di simulazioni:
•	navi reali
•	navi simulate
Di conseguenza, i dati AIS raw dovranno essere pubblicati su due topic Kafka separati.
La Living Map non dovrà più occuparsi della decodifica AIS. È invece necessario introdurre un servizio Kafka dedicato che si occupi di decodificare i messaggi e ripubblicarli su appositi topic contenenti i dati già decodificati.
La Living Map dovrà quindi interfacciarsi direttamente a questi topic in qualità di subscriber.

#### TOPIC KAFKA PRESENTI
| Topic | Formato | Descrizione |
|---|---|---|
| ais_decoded.raw |             JSON (decoded AIS) |         Dati AIS reali decodificati per Living Map |      
| ais_decoded_simulation.raw |  JSON (decoded AIS) |         Dati AIS di simulazione decodificati |            
| ais.raw |                     NMEA/AIS raw string |        Dati AIS reali raw |                              
| ais_simulation.raw |          NMEA/AIS raw string |        Dati AIS di simulazione raw |                     
| ais_ghost.raw |               NMEA/AIS raw string |        Dati navi fantasma (ghost) |                      
| analytics_ais.raw |           JSON (aggregati/metrics) |   Dati a bassa frequenza/calcolati dagli analytics |

### 2. Accesso dashboard imbarcazioni dalla mappa

Attualmente le imbarcazioni risultano cliccabili sulla mappa, ma non è possibile accedere alla dashboard associata. È fondamentale che:
•	sia presente un pulsante che consenta di aprire la dashboard direttamente dal click sul vascello;
•	ogni nave sia già associata a un percorso, in modo che, aprendo la dashboard dal vascello, sia possibile visualizzare le informazioni relative al percorso attualmente in corso.

### 3. DONE - Riorganizzazione tab Servizi

È necessario eliminare il tab Servizi e introdurre due pulsanti distinti:
•	Ottimizzazione
•	Previsione della domanda
Entrambi i pulsanti dovranno attivarsi esclusivamente in seguito alla selezione di un elemento (ad esempio una nave o un percorso).

### 4. Miglioramento visualizzazione marker navi
Attualmente i marker delle navi sulla mappa non sono ottimizzati per una visualizzazione chiara e immediata. È necessario:
•	Fixare l'orientamento delle icone in base alla rotta della nave e quello mostrato nel popup informativo;
•   Permettere la scelta del colore delle icone
•   Mettere in una tabella i percorsi già mostrati sulla mappa, permettere di selezionare/deselezionare i percorsi da visualizzare

