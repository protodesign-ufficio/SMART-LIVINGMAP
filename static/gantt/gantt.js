// Costanti & Configurazione
const API_ROOT = 'http://87.26.178.190:25080/';

const ENDPOINTS = {
    VASCELLO_LISTA: API_ROOT + 'vascello/lista',
    CORSA_GIORNO: API_ROOT + 'corsa/giorno', // ?giorno=YYYY-MM-DD
    PERCORSO_CORSA: (id) => API_ROOT + `percorso/by_corsa/${id}`,
    PIANO_LISTA: API_ROOT + 'piano/lista',   // ?data_riferimento=YYYY-MM-DD
    PIANO_DETTAGLIO: (id) => API_ROOT + `piano/${id}`,
    ASSEGNAZIONE_PIANO: (id) => API_ROOT + `assegnazione/by_piano/${id}`,
    ASSEGNAZIONE_CREA: API_ROOT + 'assegnazione/crea',
    PIANIFICAZIONE_COMPATIBILI: API_ROOT + 'pianificazione/compatibili',
    PIANO_VALIDA: API_ROOT + 'piano/valida'
};

// Color Scheme per stati assegnazione
const colorScheme = {
    assignedLocal: '#22c55e',   // green-500
    assignedServer: '#3b82f6',  // blue-500
    unassigned: '#ef4444'       // red-500
};

// Global State
    let state = {
    today: new Date().toISOString().split('T')[0], // YYYY-MM-DD
    corse: [], // Tutte le corse del giorno
    vascelli: {}, // Mappa id -> nome
    piani: [],
    selectedPianoId: null,
    assegnazioni: {}, // Mappa corsa_id -> { ...assegnazione, isLocal: bool }
    activeModalCorsaId: null,
    pendingDeleteCorsaId: null, // Per modale conferma
};

// Configurazione Gantt
const GANTT_CONFIG = {
    hourWidth: 100, // px per ora
    startHour: 0,
    endHour: 24
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    // Event Listeners
    document.getElementById('piano-select').addEventListener('change', handlePianoChange);
    document.getElementById('btn-save').addEventListener('click', savePiano);
    const btnValidate = document.getElementById('btn-validate');
    if (btnValidate) btnValidate.addEventListener('click', validatePiano);
    document.getElementById('date-select').addEventListener('change', handleDateChange);

    // Check URL params for date
    const params = new URLSearchParams(window.location.search);
    const queryGiorno = params.get('giorno');
    if (queryGiorno) {
        // Simple regex validation YYYY-MM-DD
        if (/^\d{4}-\d{2}-\d{2}$/.test(queryGiorno)) {
            state.today = queryGiorno;
        }
    }

    initDateDisplay();
    setupGanttGrid();
    
    // 1. Carica Cache Vascelli
    await loadVascelli();
    
    // 2. Carica Corse del Giorno
    await loadCorseDelGiorno();

    // 3. Carica Piani Disponibili
    await loadPiani();
    
    const queryPiano = params.get('piano');
    if (queryPiano) {
        const pianoSelect = document.getElementById('piano-select');
        if (pianoSelect) {
            pianoSelect.value = queryPiano;
            // Se il valore è stato impostato correttamente (esiste nella lista)
            if (pianoSelect.value === queryPiano) {
                pianoSelect.dispatchEvent(new Event('change'));
            }
        }
    }

    // Zoom Slider
    const zoomSlider = document.getElementById('zoom-slider');
    if (zoomSlider) {
        zoomSlider.value = GANTT_CONFIG.hourWidth; // Set initial value
        zoomSlider.addEventListener('input', handleZoomChange);
    }

    // Initial Render
    renderGantt();
});

function handleZoomChange(e) {
    const newVal = parseInt(e.target.value, 10);
    GANTT_CONFIG.hourWidth = newVal;
    
    // Update CSS variable for grid background
    document.documentElement.style.setProperty('--hour-width', `${newVal}px`);
    
    // Re-setup grid (header width) and re-render gantt (bars)
    setupGanttGrid();
    renderGantt();
}

function initDateDisplay() {
    // Set input value
    const dateInput = document.getElementById('date-select');
    if (dateInput) {
        dateInput.value = state.today;
    }
    
    // Imposta variabile CSS (Initial)
    document.documentElement.style.setProperty('--hour-width', `${GANTT_CONFIG.hourWidth}px`);
}

async function handleDateChange(e) {
    const newDate = e.target.value;
    if (!newDate) return;
    
    state.today = newDate;
    
    // Update URL query param without reloading
    const url = new URL(window.location);
    url.searchParams.set('giorno', newDate);
    window.history.pushState({}, '', url);

    // Reset State
    state.corse = [];
    state.piani = [];
    state.selectedPianoId = null;
    state.assegnazioni = {};
    
    // Clear UI
    const pianoSelect = document.getElementById('piano-select');
    pianoSelect.innerHTML = '<option value="">Seleziona un piano...</option>';
    pianoSelect.value = "";
    updatePianoStatus(null);
    
    renderGantt();

    // Reload Data
    // loadVascelli is static cache, no need to reload
    await loadCorseDelGiorno();
    await loadPiani();
    renderGantt();
}

async function handlePianoChange(e) {
    const pianoId = e.target.value;
    state.selectedPianoId = pianoId;
    state.assegnazioni = {}; // Reset visualizzazione assegnazioni
    
    if (!pianoId) {
        updatePianoStatus(null);
        renderGantt();
        return;
    }

    // Aggiorna stato piano
    updatePianoStatus(pianoId);

    try {
        const url = ENDPOINTS.ASSEGNAZIONE_PIANO(pianoId);
        const res = await fetch(url);
        const data = await res.json();
        
        // Mappa assegnazioni server (solo PIANIFICATA)
        data.forEach(ass => {
            if (ass.stato_esecuzione === 'PIANIFICATA') {
                state.assegnazioni[ass.id_corsa] = { ...ass, isLocal: false };
            }
        });
        
        console.log('Assegnazioni piano loaded:', data.length);
        renderGantt();

        // Background: Arricchisci assegnazioni con dettagli percorso (per durata corretta)
        enrichAssignmentsWithDetails(data);

    } catch (e) {
        console.error('Errore caricamento assegnazioni', e);
    }
}

// --- Data Loading ---

async function loadVascelli() {
    try {
        const res = await fetch(ENDPOINTS.VASCELLO_LISTA);
        const data = await res.json();
        state.vascelli = data.reduce((acc, v) => {
            acc[v.id] = v;
            return acc;
        }, {});
        console.log('Vascelli loaded:', Object.keys(state.vascelli).length);
    } catch (e) {
        console.error('Errore caricamento vascelli', e);
    }
}

async function loadCorseDelGiorno() {
    try {
        const url = `${ENDPOINTS.CORSA_GIORNO}?giorno=${state.today}`;
        const res = await fetch(url);
        state.corse = await res.json();
        
        // Ordina corse per orario (opzionale per visualizzazione migliore)
        // state.corse.sort((a, b) => a.orario.localeCompare(b.orario));
        
        console.log('Corse loaded:', state.corse.length);
    } catch (e) {
        console.error('Errore caricamento corse', e);
        CustomAlert('Impossibile caricare le corse per la data odierna.', 'Error');
    }
}

async function loadPiani() {
    try {
        const url = `${ENDPOINTS.PIANO_LISTA}?data_riferimento=${state.today}`;
        const res = await fetch(url);
        state.piani = await res.json();
        
        const select = document.getElementById('piano-select');
        select.innerHTML = '<option value="">Seleziona un piano...</option>';
        state.piani.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            // Mostra ID o Versione o stato
            opt.text = `Piano ${p.versione || p.id.substring(0,8)} (Profitto: €${p.kpi_profitto_stimato || 0}, ${Object.keys(p.assegnazioni || {}).length} ass.)`; 
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Errore caricamento piani', e);
    }
}

// --- Background Data Enrichment ---

async function enrichAssignmentsWithDetails(assegnazioniList) {
    // Per ogni assegnazione, se non abbiamo i dettagli, cerchiamo di recuperarli
    // Questo è pesante (N chiamate), ma necessario se il backend non fornisce i dettagli nell'assegnazione
    
    let updated = false;
    
    // Raggruppa per corsa per ottimizzare se necessario, ma qui facciamo semplice ciclo
    // Promise.all per parallelizzare potrebbe essere troppo aggressivo per il server? 
    // Andiamo a batch o sequenziale veloce. Proviamo un pool limitato o sequenziale.
    
    for (const ass of assegnazioniList) {
        try {
            // Se abbiamo già _percorsoDetails saltiamo (caching futuro?)
            if (state.assegnazioni[ass.id_corsa]._percorsoDetails) continue;

            const res = await fetch(ENDPOINTS.PERCORSO_CORSA(ass.id_corsa));
            const data = await res.json();
            const percorsi = data.percorsi || [];
            
            const targetPercorso = percorsi.find(p => p.id === ass.percorso_id);
            
            if (targetPercorso) {
                // Arricchisci con logica orari
                const corsa = state.corse.find(c => c.id === ass.id_corsa);
                const enriched = enrichPercorsoData(targetPercorso, corsa);
                
                // Aggiorna stato
                if (state.assegnazioni[ass.id_corsa]) {
                    state.assegnazioni[ass.id_corsa]._percorsoDetails = enriched;
                    updated = true;
                }
            }
        } catch (e) {
            console.warn('Failed to enrich assignment', ass.id, e);
        }
    }

    if (updated) {
        console.log('Assegnazioni arricchite con dettagli orari');
        renderGantt();
    }
}

function enrichPercorsoData(percorsoRaw, corsaObj) {
    // Logica centralizzata per calcolo orari
    const startTimeStr = corsaObj ? corsaObj.orario : "00:00";
    const durationMins = parseFloat(percorsoRaw.tempo_percorrenza || "0");
    
    const startObj = parseTime(startTimeStr);
    const startTotalMins = (startObj.h * 60) + startObj.m;
    const endTotalMins = startTotalMins + durationMins;
    const endTimeStr = formatMinutesToTime(endTotalMins);

    // Clona per sicurezza
    const p = { ...percorsoRaw };
    p.orario_partenza_schedulato = startTimeStr;
    p.orario_arrivo_previsto = endTimeStr;
    p._derivedDuration = durationMins;
    
    return p;
}

// --- Gantt Rendering ---

function setupGanttGrid() {
    const timelineContainer = document.getElementById('timeline-hours');
    const timelineContent = document.getElementById('timeline-scroll-content');
    
    timelineContent.innerHTML = '';
    
    // Genera header orario 00-24
    for (let h = GANTT_CONFIG.startHour; h < GANTT_CONFIG.endHour; h++) {
        const div = document.createElement('div');
        div.className = 'hour-marker';
        div.innerText = `${h.toString().padStart(2, '0')}:00`;
        timelineContent.appendChild(div);
    }
    // Aggiungi un marker finale finto per chiudere la griglia visivamente se serve
    const divEnd = document.createElement('div');
    divEnd.className = 'hour-marker';
    divEnd.innerText = '24:00';
    timelineContent.appendChild(divEnd);
    
    // Aggiungi spacer finale per evitare cut-off
    const spacer = document.createElement('div');
    spacer.style.width = '4rem'; // ~64px extra space
    spacer.className = 'shrink-0';
    timelineContent.appendChild(spacer);
    
    // Total width set on valid grid content wrapper not the container itself
    const totalWidth = (GANTT_CONFIG.endHour - GANTT_CONFIG.startHour) * GANTT_CONFIG.hourWidth;
    
    // Sync Scroll Setup
    const ganttBody = document.getElementById('gantt-body');
    if (ganttBody) {
        ganttBody.addEventListener('scroll', (e) => {
            timelineContainer.scrollLeft = e.target.scrollLeft;
        });
    }
}

function renderGantt() {
    const container = document.getElementById('gantt-body');
    container.innerHTML = '';

    if (state.corse.length === 0) {
        container.innerHTML = '<div class="p-4 text-slate-500">Nessuna corsa pianificata per oggi.</div>';
        return;
    }

    state.corse.forEach(corsa => {
        const row = document.createElement('div');
        row.className = 'flex h-16 border-b border-slate-800/50 hover:bg-slate-900/50 transition-colors group relative min-w-max';
        
        // Colonna Nome Corsa (Sticky)
        const label = document.createElement('div');
        label.className = 'w-64 shrink-0 border-r border-slate-800 flex flex-col justify-center px-4 truncate bg-slate-950 z-20 sticky left-0 border-b border-slate-900 shadow-[2px_0_5px_rgba(0,0,0,0.3)]';
        const previsione = corsa.previsione || {};
        const confMin = previsione.confidenza_min !== undefined && previsione.confidenza_min !== null ? previsione.confidenza_min : 'N/A';
        const confMax = previsione.confidenza_max !== undefined && previsione.confidenza_max !== null ? previsione.confidenza_max : 'N/A';
        label.innerHTML = `
            <div class="text-lg font-medium text-slate-300 truncate">${corsa.tratta || 'N/A'} - ${corsa.orario || 'N/A'} ➜ ${corsa.orario_arrivo_max || 'N/A'}</div>
            <!-- <div class="text-xs text-slate-500">${corsa.nome || corsa.tratta_nome || 'N/A'}</div> -->
            <div class="text-s text-slate-400 truncate">Passeggeri stimati: ${confMin} - ${confMax}</div>
        `;
        row.appendChild(label);

        // Area Gantt per la riga
        const track = document.createElement('div');
        track.className = 'relative shrink-0 h-full'; 
        // Imposta larghezza esplicita per matchare l'header (+60 per 24:00 + 64 spacer)
        const totalWidth = (GANTT_CONFIG.endHour - GANTT_CONFIG.startHour) * GANTT_CONFIG.hourWidth;
        track.style.width = `${totalWidth + 60 + 64}px`;

        // Verifica assegnazione
        const assigned = state.assegnazioni[corsa.id];
        
        // Track: contenitore righe. I click sono gestiti dalle barre specifiche.
        track.style.cursor = 'default';

        if (assigned) {
            // Render Barra Assegnata
            // Abbiamo bisogno di orario partenza e durata dal percorso assegnato...
            // ATTENZIONE: l'endpoint assegnazione non ritorna i dettagli temporali.
            // Se li abbiamo, bene, altrimenti dobbiamo mostrare un placeholder o fare un fetch extra?
            // Per ora assumiamo di dover renderizzare *qualcosa*.
            // Nel prompt dice: "per quanto riguarda la durate e la lunghezza della barra bisogna utilizzare 'orario_partenza_schedulato' e 'orario_arrivo_previsto'"
            // Questi dati sono nel PERCORSO. Se ho solo l'assegnazione (che ha percorso_id), 
            // potrei non avere i tempi se non ho caricato i dettagli del percorso. 
            // TEMPORANEO: se ho i metadati nell'assegnazione locale li uso, se vengono dal server potrei non averli.
            // Soluzione: Recuperare i dettagli è costoso per N corse. 
            // Faccio una supposizione: renderizzo una barra placeholder sull'orario della Corsa schedulato se non ho i dettagli precisi, 
            // ma se è un "assegnamento locale" ho l'oggetto percorso intero.
            
            let startParams = null;
            let durationMinutes = 60; // Default

            // Usa i dettagli percorso se disponibili (sia per locali che server arricchiti)
            if (assigned._percorsoDetails) {
                // Ho dettagli completi
                startParams = parseTime(assigned._percorsoDetails.orario_partenza_schedulato);
                // Utilizza durationMins calcolata se disponibile, o ricalcola differenza
                if (assigned._percorsoDetails._derivedDuration) {
                    durationMinutes = assigned._percorsoDetails._derivedDuration;
                } else {
                    const endParams = parseTime(assigned._percorsoDetails.orario_arrivo_previsto);
                    durationMinutes = diffMinutes(startParams, endParams);
                }
            } else {
                // E' dal server e non ho ancora i dettagli: uso orario corsa di base e default duration
                // La "corsa" ha un campo "orario" es "08:00"
                startParams = parseTime(corsa.orario);
            }

            if (startParams) {
                const bar = document.createElement('div');
                
                // Determina classi stile base
                let baseClasses = `absolute h-10 top-3 rounded px-2 flex items-center shadow-lg text-s font-bold whitespace-nowrap overflow-hidden task-bar`;
                
                // Gestione stile Virtuale vs Reale
                const isVirtual = assigned.virtuale === true;
                const statusClass = assigned.isLocal ? 'status-assigned-local' : 'status-assigned-server';
                
                if (isVirtual) {
                    // Stile Virtuale: Trasparente con Bordo
                    bar.className = `${baseClasses} bg-transparent border-2`;
                    // Applico colori inline per semplicità non avendo classi CSS specifiche per i bordi nel file
                    if (assigned.isLocal) {
                        bar.style.borderColor = colorScheme.assignedLocal; // green-500
                        bar.style.color = colorScheme.assignedLocal;
                    } else {
                        bar.style.borderColor = colorScheme.assignedServer; // blue-500
                        bar.style.color = colorScheme.assignedServer;
                    }
                } else {
                    // Stile Reale: Pieno
                    bar.className = `${baseClasses} text-white ${statusClass}`;
                }
                
                // Posizionamento
                const leftPx = timeToPixels(startParams);
                const widthPx = minutesToPixels(durationMinutes);
                
                bar.style.left = `${leftPx}px`;
                bar.style.width = `${widthPx}px`;
                
                // Content
                const vascelloName = state.vascelli[assigned.vascello_id] ? state.vascelli[assigned.vascello_id].nome : 'Vascello ' + assigned.vascello_id;
                bar.innerText = isVirtual ? `${vascelloName}` : vascelloName;

                // Click Event: Confirm Delete
                bar.addEventListener('click', (e) => {
                    e.stopPropagation(); // Evita che il click raggiunga la track (che aprirebbe la modal inserimento)
                    openDeleteModal(corsa.id);
                });

                // Tooltip Events
                bar.addEventListener('mouseenter', (e) => {
                    const tooltip = createTooltip();
                    const details = assigned._percorsoDetails || {};
                    // Se non abbiamo dettagli ma solo l'assegnazione server base, usiamo placeholder
                    
                    // Orari: Preferiamo quelli del percorso, fallback su quelli della corsa (partenza)
                    const startStrRaw = details.orario_partenza_schedulato || corsa.orario;
                    const endStrRaw = details.orario_arrivo_previsto;
                    
                    const startDisplay = formatTimeStr(startStrRaw);
                    const endDisplay = endStrRaw ? formatTimeStr(endStrRaw) : '--:--';
                    
                    const duration = Math.round(details._derivedDuration || durationMinutes);
                    const consumo = details.consumo !== undefined ? details.consumo : 'N/A';
                    const comfort = details.comfort !== undefined ? details.comfort : 'N/A';

                    tooltip.innerHTML = `
                        <div class="font-bold text-white mb-2 border-b border-slate-600 pb-1 flex items-center justify-between gap-2">
                            <span>${vascelloName}</span>
                            ${assigned.virtuale ? '<span class="text-[10px] bg-blue-900/80 text-blue-200 px-1.5 py-0.5 rounded border border-blue-700/50 uppercase tracking-widest font-semibold flex-shrink-0">Simulazione</span>' : ''}
                        </div>
                        <div class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                            <span class="text-slate-400">Orario:</span>
                            <span class="font-mono text-slate-200">${startDisplay} ➜ ${endDisplay}</span>
                            
                            <span class="text-slate-400">Durata:</span>
                            <span class="text-slate-200">${duration} min</span>
                            
                            <span class="text-slate-400">Consumo:</span>
                            <span class="text-slate-200">${consumo} L</span>
                            
                            <span class="text-slate-400">Comfort:</span>
                            <span class="text-slate-200">${comfort}</span>
                            
                        </div>
                    `;
                    
                    // Initial Position
                    const x = e.clientX + 15;
                    const y = e.clientY + 15;
                    tooltip.style.left = `${x}px`;
                    tooltip.style.top = `${y}px`;
                    
                    tooltip.classList.remove('invisible');
                });

                bar.addEventListener('mousemove', (e) => {
                    const tooltip = document.getElementById('gantt-tooltip');
                    if(tooltip) {
                        const x = e.clientX + 15;
                        const y = e.clientY + 15;
                        tooltip.style.left = `${x}px`;
                        tooltip.style.top = `${y}px`;
                    }
                });

                bar.addEventListener('mouseleave', () => {
                    const tooltip = document.getElementById('gantt-tooltip');
                    if (tooltip) tooltip.classList.add('invisible');
                });

                track.appendChild(bar);
            }

        } else {
            // Non assegnato: Barra Rossa (Placeholder sullo slot orario schedulato della corsa)
            // Corsa.orario è tipo "08:00" string
            const timeParts = parseTime(corsa.orario);
            if (timeParts) {
                const bar = document.createElement('div');
                bar.className = 'absolute h-10 top-3 rounded px-2 flex items-center border border-red-500 bg-red-500/20 text-red-400 text-s font-bold whitespace-nowrap overflow-hidden task-bar status-unassigned';
                // Default 1h duration visual hint or calc based on orario_arrivo_max
                let duration = 60;
                if (corsa.orario_arrivo_max) {
                    const startMins = (timeParts.h * 60) + timeParts.m;
                    const endMins = isoToMinutes(corsa.orario_arrivo_max);
                    if (endMins > startMins) {
                        duration = endMins - startMins;
                    }
                }

                const leftPx = timeToPixels(timeParts);
                const widthPx = minutesToPixels(duration);

                bar.style.left = `${leftPx}px`;
                bar.style.width = `${widthPx}px`;
                bar.innerText = 'Da Assegnare';
                
                // Click Event: Open Assign Modal
                bar.style.cursor = 'pointer';
                bar.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openCorsaModal(corsa.id);
                });
                
                track.appendChild(bar);
            }
        }

        row.appendChild(track);
        container.appendChild(row);
    });
}

function formatPercent(value) {
    if (value === undefined || value === null || value === '') return 'N/A';
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return 'N/A';
    return `${Math.round(numericValue * 100)}%`;
}

// --- Modal & Interaction ---

async function openCorsaModal(corsaId) {
    state.activeModalCorsaId = corsaId;
    const modal = document.getElementById('modal-percorso');
    const modalTitle = document.getElementById('modal-percorso-title');
    const modalSubtitle = document.getElementById('modal-percorso-subtitle');
    const tbody = document.getElementById('modal-percorsi-list');
    tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center"><div class="animate-spin h-6 w-6 border-b-2 border-blue-500 rounded-full mx-auto"></div></td></tr>';

    const currentCorsa = state.corse.find(c => c.id === corsaId);
    const corsaName = currentCorsa ? `${currentCorsa.tratta || 'N/A'} - ${currentCorsa.orario || 'N/A'}` : 'Corsa selezionata';
    const previsione = currentCorsa && currentCorsa.previsione ? currentCorsa.previsione : null;
    const paxMin = previsione && previsione.confidenza_min !== undefined && previsione.confidenza_min !== null ? previsione.confidenza_min : 'N/A';
    const paxMax = previsione && previsione.confidenza_max !== undefined && previsione.confidenza_max !== null ? previsione.confidenza_max : 'N/A';

    if (modalTitle) modalTitle.textContent = `Seleziona Percorso: ${corsaName} · Passeggeri stimati: ${paxMin} - ${paxMax}`;
    
    modal.classList.remove('hidden');

    try {
        // Prepare payload for compatibility check
        // Raccogliamo tutti i percorsi attualmente assegnati (DB + Locali), escludendo l'eventuale assegnazione della corsa corrente che stiamo modificando
        const assignedPercorsiIds = Object.values(state.assegnazioni)
            .filter(a => a.id_corsa !== corsaId) 
            .map(a => a.percorso_id)
            .filter(id => !!id);

        const payload = {
            corsa_id: corsaId,
            percorsi_id: assignedPercorsiIds
        };

        // Fetch in parallelo: Tutti i percorsi possibili + Check compatibilità
        const [resAll, resCompat] = await Promise.all([
            fetch(ENDPOINTS.PERCORSO_CORSA(corsaId)),
            fetch(ENDPOINTS.PIANIFICAZIONE_COMPATIBILI, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
        ]);

        const dataAll = await resAll.json(); // { computer_id, percorsi: [] }
        const dataCompat = await resCompat.json(); // { corsa_id, percorsi_compatibili: [...] }

        const percorsi = dataAll.percorsi || [];
        const percorsiCompatibili = dataCompat.percorsi_compatibili || [];
        const compatibiliIds = new Set((dataCompat.percorsi_compatibili || []).map(p => p.percorso_id));
        const compatibiliByPercorsoId = new Map(
            percorsiCompatibili.map(p => [p.percorso_id, p])
        );

        tbody.innerHTML = '';
        
        percorsi.forEach(p => {
             // CALCOLO ORARI MANCANTE NEL PAYLOAD v2
            // 1. Prendi Orario Partenza da Corsa (es. "08:00")
            // 2. Prendi Durata da Percorso
            // 3. Calcola Arrivo
            // 4. Inietta (Usa Helper Centralizzato)
            
            enrichPercorsoData(p, currentCorsa); // Modifica p in place o ritorna nuovo? La func ritorna nuovo.
            
            // Attenzione: enrichPercorsoData ritorna una copia "p" arricchita. 
            // Qui dobbiamo aggiornare "p" nel loop o usare l'oggetto ritornato.
            // Poiché forEach itera, meglio riassegnare o estendere
            const enrichedP = enrichPercorsoData(p, currentCorsa);
            
            // Sovrascriviamo le proprietà nell'oggetto originale p per comodità del loop corrente che usa "p"
            Object.assign(p, enrichedP);


            // Validazione Conflitti (con i valori calcolati)
            // const conflict = checkConflict(p.vascello_id, p.orario_partenza_schedulato, p.orario_arrivo_previsto, corsaId);
            const conflict = !compatibiliIds.has(p.id);
            
            const tr = document.createElement('tr');
            tr.className = `border-b border-slate-800 hover:bg-white/5 transition-colors ${conflict ? 'opacity-50 grayscale' : ''}`;
            
            const vascello = state.vascelli[p.vascello_id];
            const nomeVascello = vascello ? vascello.nome : p.vascello_id;
            const rischioOperativo = formatPercent(
                p.rischio_operativo !== undefined && p.rischio_operativo !== null
                    ? p.rischio_operativo
                    : compatibiliByPercorsoId.get(p.id)?.rischio_operativo
            );

            tr.innerHTML = `
                <td class="px-4 py-3 font-medium text-white">${nomeVascello}</td>
                <td class="px-4 py-3 text-xs">
                    ${formatTimeStr(p.orario_partenza_schedulato)} <span class="text-slate-500">➜</span> ${formatTimeStr(p.orario_arrivo_previsto)}
                </td>
                <td class="px-4 py-3">${Math.round(p._derivedDuration || 0)} min</td>
                <td class="px-4 py-3">${rischioOperativo}</td>
                <td class="px-4 py-3">${p.consumo || '-'} L</td>
                <td class="px-4 py-3">${p.comfort || '-'}</td>
                <td class="px-4 py-3 space-x-2">
                    ${!conflict ? `
                        <button 
                            class="px-3 py-1 rounded text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white"
                            onclick="window.selectPercorsoById('${p.id}', false)" 
                        >
                            Assegna
                        </button>
                        <button 
                            class="px-3 py-1 rounded text-xs font-bold bg-transparent border border-blue-500 hover:bg-blue-500/10 text-blue-400"
                            onclick="window.selectPercorsoById('${p.id}', true)" 
                        >
                            Simulazione
                        </button>
                    ` : `
                        <button disabled class="px-3 py-1 rounded text-xs font-bold bg-slate-700 text-slate-500 cursor-not-allowed">
                            Non Disponibile
                        </button>
                    `}
                </td>
            `;

            // Nota: Ho rimosso il trick del data-percorso-obj perché ora passiamo l'ID e recuperiamo l'oggetto dalla lista locale se necessario,
            // oppure (meglio) passiamo l'oggetto intero se la funzione lo supporta ancora, ma selectPercorso prendeva un Obj prima.
            // Aggiorno selectPercorso per prendere ID e flag, o gestisco qui il passaggio
            
            // FIX: selectPercorso si aspetta un OGGETTO intero (usato poi per _percorsoDetails).
            // Dobbiamo mantenere la signature o cambiare l'approccio. 
            // Dato che siamo in una stringa HTML onclick, passare un oggetto complesso è rischioso (escaping JSON).
            // Soluzione migliore: salvare i percorsi in una mappa temporanea per ID e fare lookup.
            state._tempPercorsiMap = state._tempPercorsiMap || {};
            state._tempPercorsiMap[p.id] = p;
            
            // Ridefiniamo l'onclick per chiamare un helper che recupera l'oggetto
            // Modifico la stringa HTML sopra per chiamare selectPercorsoById
            
            tbody.appendChild(tr);
        });

    } catch (e) {
        console.error('Error fetching percorsi', e);
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-4 text-center text-red-400">Errore caricamento percorsi</td></tr>';
    }
}

function formatMinutesToTime(totalMins) {
    let h = Math.floor(totalMins / 60);
    const m = Math.floor(totalMins % 60);
    h = h % 24; // Wrap around 24h
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

// Helper bridge per chiamare selectPercorso dalla stringa HTML onclick
window.selectPercorsoById = function(percorsoId, isSimulation) {
    const p = state._tempPercorsiMap[percorsoId];
    if (p) {
        selectPercorso(p, isSimulation);
    } else {
        console.error('Percorso not found in temp map', percorsoId);
    }
};

function selectPercorso(percorsoObj, isSimulation = false) {
    if (!state.activeModalCorsaId) return;

    // Check for existing server assignment to cancel later
    const existing = state.assegnazioni[state.activeModalCorsaId];
    let prevId = null;
    if (existing) {
        if (!existing.isLocal) prevId = existing.id; // It's from server
        else if (existing._previousServerAssignmentId) prevId = existing._previousServerAssignmentId; // Already local edit of server item
    }

    // Aggiorna stato locale
    state.assegnazioni[state.activeModalCorsaId] = {
        id_corsa: state.activeModalCorsaId,
        percorso_id: percorsoObj.id,
        vascello_id: percorsoObj.vascello_id,
        piano_id: state.selectedPianoId,
        stato_esecuzione: "PIANIFICATA",
        virtuale: isSimulation, // Usa il flag passato dal bottone
        isLocal: true,
        _percorsoDetails: percorsoObj, // Salviamo i dettagli per il render corretto
        _previousServerAssignmentId: prevId
    };

    closeModal();
    renderGantt();
}

function closeModal() {
    document.getElementById('modal-percorso').classList.add('hidden');
    state.activeModalCorsaId = null;
}

// --- Delete Confirmation Logic ---

function openDeleteModal(corsaId) {
    state.pendingDeleteCorsaId = corsaId;
    const assignment = state.assegnazioni[corsaId];
    if (!assignment) return; // Should not happen

    const modal = document.getElementById('modal-confirm-delete');
    const warningText = document.getElementById('delete-warning-server');
    
    // Mostra warning specifico se è salvata sul server
    if (!assignment.isLocal) {
        warningText.classList.remove('hidden');
    } else {
        warningText.classList.add('hidden');
    }

    modal.classList.remove('hidden');
}

function closeDeleteModal() {
    document.getElementById('modal-confirm-delete').classList.add('hidden');
    state.pendingDeleteCorsaId = null;
}

async function confirmDelete() {
    const corsaId = state.pendingDeleteCorsaId;
    if (!corsaId) return;

    const assignment = state.assegnazioni[corsaId];
    if (!assignment) {
        closeDeleteModal();
        return;
    }

    // Se è assegnazione SERVER -> Chiamata API per CANCELLATA
    if (!assignment.isLocal) {
        try {
            const patchUrl = API_ROOT + `assegnazione/${assignment.id}/stato`;
            const res = await fetch(patchUrl, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stato_esecuzione: 'CANCELLATA' })
            });

            if (!res.ok) {
                const err = await res.text();
                throw new Error(err || 'Errore durante la cancellazione');
            }
            
            // Rimozione da stato locale -> Diventa Rossa (Da Assegnare)
            delete state.assegnazioni[corsaId];
            renderGantt();
            updatePianoStatus(state.selectedPianoId);
            CustomAlert('Assegnazione cancellata sul server.', 'Success');
            // alert('Assegnazione cancellata sul server.');

        } catch (e) {
            console.error('Errore delete', e);
            CustomAlert('Errore durante la cancellazione: ' + e.message, 'Error');
            // alert('Errore durante la cancellazione: ' + e.message);
        }
    } else {
        // Se è assegnazione LOCALE -> Rimuovi solo da stato, nessuna chiamata API
        // Nota: Se questa locale sovrascriveva una server, eliminando la locale
        // tornerebbe visibile quella server se ricaricassimo i dati. 
        // Ma qui rimuoviamo 'l'oggetto' visualizzato.
        delete state.assegnazioni[corsaId];
        renderGantt();
    }

    closeDeleteModal();
}

// --- Conflict Logic ---
// --- DEPRECATED : la logica di conflitto è demandata al backend ---
function checkConflict(vascelloId, startIso, endIso, currentCorsaId) {
    // startIso e endIso sono stringhe complete o parti? L'API dice "string"
    // Assumiamo siano timestamp completi o orari. Se sono orari HH:MM, li normalizziamo a minuti
    
    const startMins = isoToMinutes(startIso);
    const endMins = isoToMinutes(endIso);

    // Itera tutte le assegnazioni correnti (Locali E Server)
    for (const [cId, ass] of Object.entries(state.assegnazioni)) {
        if (cId === currentCorsaId) continue; // Salta se stessa (caso edit)
        if (ass.vascello_id !== vascelloId) continue; // Altro vascello, ok

        let otherStart = 0;
        let otherEnd = 0;

        // Se abbiamo i dettagli del percorso (O da local o da enrichment background)
        if (ass._percorsoDetails) {
            otherStart = isoToMinutes(ass._percorsoDetails.orario_partenza_schedulato);
            otherEnd = isoToMinutes(ass._percorsoDetails.orario_arrivo_previsto);
        } else {
            // Fallback: Assegnazione esistente su server ma dettagli non ancora caricati
            // Recuperiamo almeno l'orario di partenza dalla corsa associata in memoria state.corse
            const existingCorsa = state.corse.find(c => c.id === ass.id_corsa);
            if (existingCorsa && existingCorsa.orario) {
                otherStart = isoToMinutes(existingCorsa.orario);
                // Stima durata difensiva (es. 60 min) per non ignorare completamente il conflitto
                // Se possibile, è meglio che l'enrichment sia veloce.
                otherEnd = otherStart + 60; 
            } else {
                // Se non abbiamo dati temporali è impossibile verificare, saltiamo (o logghiamo warning)
                continue;
            }
        }

        // Overlap logic: (StartA < EndB) && (EndA > StartB)
        if (startMins < otherEnd && endMins > otherStart) {
            return true; // Conflict
        }
    }
    return false;
}

// --- Saving ---
async function savePiano() {
    if (!state.selectedPianoId) {
        CustomAlert('Seleziona un piano prima di salvare.', 'Warning');
        // alert('Seleziona un piano prima di salvare.');
        return;
    }

    const localAssignments = Object.values(state.assegnazioni).filter(a => a.isLocal);
    if (localAssignments.length === 0) {
        CustomAlert('Nessuna nuova modifica da salvare.', 'Warning');
        // alert('Nessuna nuova modifica da salvare.');
        return;
    }

    const btn = document.getElementById('btn-save');
    const originalText = btn.innerText;
    btn.disabled = true;
    // btn.innerText = 'Salvataggio...';

    let successCount = 0;
    let errors = 0;

    // L'endpoint crea una assegnazione alla volta secondo la specifica
    // ENDPOINT_ASSEGNAZIONE/CREA
    for (const ass of localAssignments) {
        try {
            // 1. Se c'era una assegnazione precedente sul server (PIANIFICATA), la annulliamo
            if (ass._previousServerAssignmentId) {
                const patchUrl = API_ROOT + `assegnazione/${ass._previousServerAssignmentId}/stato`;
                await fetch(patchUrl, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ stato_esecuzione: 'CANCELLATA' })
                });
            }

            // 2. Creiamo la nuova assegnazione
            const payload = {
                piano_id: state.selectedPianoId,
                percorso_id: ass.percorso_id,
                stato_esecuzione: "PIANIFICATA",
                virtuale: ass.virtuale // Usa il valore salvato (true/false) invece di hardcoded true
            };

            const res = await fetch(ENDPOINTS.ASSEGNAZIONE_CREA, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) throw new Error('API Error');
            
            // Mark as saved (server)
            const jsonRes = await res.json(); 
            // Aggiorna ID reale e pulisci stato locale
            state.assegnazioni[ass.id_corsa].isLocal = false;
            state.assegnazioni[ass.id_corsa].id = jsonRes.id;
            delete state.assegnazioni[ass.id_corsa]._previousServerAssignmentId;

            successCount++;

        } catch (e) {
            console.error('Save failed for', ass, e);
            errors++;
        }
    }

    btn.disabled = false;
    btn.innerText = originalText;

    if (errors > 0) {
        CustomAlert(`Salvato con errori. Successi: ${successCount}, Errori: ${errors}`, 'Error');
        // alert(`Salvato con errori. Successi: ${successCount}, Errori: ${errors}`);
    } else {
        // Rerender aggiorna colori a blu (server) e stato locale
        renderGantt(); 

        // Ricarica la lista dei piani per aggiornare il conteggio assegnazioni nella select
        const currentPianoId = state.selectedPianoId;
        await loadPiani();
        const select = document.getElementById('piano-select');
        if (select && currentPianoId) {
            select.value = currentPianoId;
        }

        // Aggiorna stato piano
        updatePianoStatus(state.selectedPianoId);
        
        CustomAlert('Piano aggiornato con successo!', 'Success');
        // alert('Piano aggiornato con successo!');
    }
}

// --- Validate Piano ---
async function validatePiano() {
    if (!state.selectedPianoId) {
        CustomAlert('Seleziona un piano prima di validarlo.', 'Warning');
        // alert('Seleziona un piano prima di validarlo.');
        return;
    }

    const btn = document.getElementById('btn-validate');
    const originalText = btn ? btn.innerText : '';
    if (btn) {
        btn.disabled = true;
        // btn.innerText = 'Validazione...';
    }

    try {
        const payload = { piano_id: state.selectedPianoId };
        const res = await fetch(ENDPOINTS.PIANO_VALIDA, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            throw new Error('API Error');
        }

        const data = await res.json();

        // Expecting { validato: bool, messaggio?: string, dettagli?: {...} }
        if (data.validato === true) {
            CustomAlert(data.messaggio || 'Piano validato con successo.', 'Success');
            // alert(data.messaggio || 'Piano validato con successo.');
            // Update status immediately if successful
            updatePianoStatus(state.selectedPianoId);
        } else {
            const msg = data.messaggio || 'Validazione fallita.';
            // If server returns details (e.g., list of problemi) include brief info
            if (data.dettagli) {
                CustomAlert(`${msg}\nDettagli: ${JSON.stringify(data.dettagli)}`, 'Error');
                // alert(`${msg}\nDettagli: ${JSON.stringify(data.dettagli)}`);
            } else {
                CustomAlert(msg, 'Error');
                // alert(msg);
            }
        }

    } catch (e) {
        console.error('Validate failed', e);
        CustomAlert('Errore durante la validazione del piano: ' + e.message, 'Error');
        // alert('Errore durante la validazione del piano.');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = originalText;
        }
    }
}

async function updatePianoStatus(pianoId) {
    const container = document.getElementById('piano-status-container');
    const textEl = document.getElementById('piano-status-text');

    textEl.classList.remove('text-green-400', 'text-yellow-400', 'text-blue-400', 'text-red-400', 'text-white');

    if (!pianoId) {
        if (textEl) {
            textEl.innerText = 'non definito';
            textEl.classList.add('text-red-400');
        }
        return;
    }

    try {
        const res = await fetch(ENDPOINTS.PIANO_DETTAGLIO(pianoId));
        if (res.ok) {
            const data = await res.json();
            // data.stato
            if (textEl) {
                textEl.innerText = data.stato || 'N/D';
            
                // Colora in base allo stato
                switch (data.stato) {
                    case 'CREATO':
                        textEl.classList.add('text-white');
                        break;
                    case 'VALIDATO':
                        textEl.classList.add('text-green-400');
                        break;
                    case 'IN_OTTIMIZZAZIONE':
                        textEl.innerText = 'IN OTTIMIZZAZIONE';
                        textEl.classList.add('text-yellow-400');
                        break;
                    case 'PRONTO':
                        textEl.classList.add('text-blue-400');
                        break;
                    default:
                        textEl.classList.add('text-red-400');
                }
            }
            if (container) container.classList.remove('hidden');
        } else {
            console.warn("Impossibile recuperare stato piano", res.status);
            if (container) container.classList.add('hidden');
        }
    } catch (e) {
        console.error("Errore fetch stato piano", e);
        if (container) container.classList.add('hidden');
    }
}

// --- Utilities ---

function parseTime(timeStr) {
    // Gestisce "HH:MM", "HH:MM:SS" o ISO "YYYY-MM-DDTHH:MM..."
    if (!timeStr) return null;
    try {
        if (timeStr.includes('T')) {
            const date = new Date(timeStr);
            return { h: date.getHours(), m: date.getMinutes() };
        }
        const parts = timeStr.split(':');
        return { h: parseInt(parts[0]), m: parseInt(parts[1]) };
    } catch {
        return null;
    }
}

function timeToPixels(timeObj) {
    if (!timeObj) return 0;
    // Calcola pixel dall'inizio (00:00)
    const minutes = (timeObj.h * 60) + timeObj.m;
    return (minutes / 60) * GANTT_CONFIG.hourWidth;
}

function minutesToPixels(minutes) {
    return (minutes / 60) * GANTT_CONFIG.hourWidth;
}

function diffMinutes(start, end) {
    if (!start || !end) return 60;
    const startMins = start.h * 60 + start.m;
    const endMins = end.h * 60 + end.m;
    return endMins - startMins;
}

function isoToMinutes(isoStr) {
    const t = parseTime(isoStr);
    if (!t) return 0;
    return t.h * 60 + t.m;
}

function formatTimeStr(isoStr) {
    const t = parseTime(isoStr);
    if (!t) return '--:--';
    return `${t.h.toString().padStart(2,'0')}:${t.m.toString().padStart(2,'0')}`;
}

function createTooltip() {
    let tooltip = document.getElementById('gantt-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'gantt-tooltip';
        tooltip.className = 'fixed z-50 invisible bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg shadow-2xl p-3 min-w-[200px] pointer-events-none backdrop-blur-sm bg-opacity-95';
        document.body.appendChild(tooltip);
    }
    return tooltip;
}

// --- Custom Alert System ---

function CustomAlert(message, type = 'Success') {
    const modal = document.getElementById('modal-alert');
    const title = document.getElementById('modal-alert-title');
    const msg = document.getElementById('modal-alert-message');
    const btn = document.getElementById('modal-alert-btn');
    const iconContainer = document.getElementById('modal-alert-icon');
    const iconSuccess = document.getElementById('icon-success');
    const iconWarning = document.getElementById('icon-warning');
    
    if (!modal) return;

    // Reset icons
    iconSuccess.classList.add('hidden');
    iconWarning.classList.add('hidden');
    iconContainer.classList.remove('bg-green-900/20', 'bg-red-900/20', 'bg-yellow-900/20');
    
    // Rimuovi tutte le classi colore possibili dal bottone e titolo
    btn.classList.remove(
        'bg-green-600', 'hover:bg-green-700', 'focus:ring-green-500',
        'bg-red-600', 'hover:bg-red-700', 'focus:ring-red-500',
        'bg-yellow-600', 'hover:bg-yellow-700', 'focus:ring-yellow-500'
    );
    title.classList.remove('text-green-500', 'text-red-500', 'text-yellow-500');

    if (type === 'Success') {
        title.innerText = "Fatto!";
        title.classList.add('text-green-500');
        
        iconSuccess.classList.remove('hidden');
        iconContainer.classList.add('bg-green-900/20');
        
        btn.classList.add('bg-green-600', 'hover:bg-green-700', 'focus:ring-green-500');

    } else if (type === 'Warning') {
        title.innerText = "Attenzione!";
        title.classList.add('text-yellow-500');
        
        // Uso iconWarning anche per warning (è un triangolo) ma lo coloro di giallo via CSS parent o classe diretta?
        // L'svg ha text-red-500 hardcoded nell'HTML che ho inserito prima?
        // Controllo gantt.html (dalla memoria precedente): 
        // <svg id="icon-warning" class="h-6 w-6 text-red-500 hidden" ...>
        // Devo cambiare il colore dell'icona via JS
        
        iconWarning.classList.remove('hidden', 'text-red-500');
        iconWarning.classList.add('text-yellow-500');

        iconContainer.classList.add('bg-yellow-900/20');
        
        btn.classList.add('bg-yellow-600', 'hover:bg-yellow-700', 'focus:ring-yellow-500');

    } else if (type === 'Error') {
        title.innerText = "Errore!";
        title.classList.add('text-red-500');
        
        iconWarning.classList.remove('hidden', 'text-yellow-500');
        iconWarning.classList.add('text-red-500');

        iconContainer.classList.add('bg-red-900/20');
        
        btn.classList.add('bg-red-600', 'hover:bg-red-700', 'focus:ring-red-500');
    }


    msg.innerText = message;
    modal.classList.remove('hidden');
}

function closeAlertModal() {
    const modal = document.getElementById('modal-alert');
    if (modal) {
        modal.classList.add('hidden');
    }
}
