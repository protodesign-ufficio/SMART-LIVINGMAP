(function () {
  const DASHBOARD_META = {
    porto: {
      description: 'Monitora i porti, le banchine e i flussi in arrivo per avere una vista immediata del traffico.',
    },
    vascello: {
      description: 'Controlla lo stato dei vascelli, i dettagli operativi e la rotta attiva in tempo reale.',
    },
    previsione_domanda: {
      description: 'Stima la domanda passeggeri di una corsa e confronta i risultati previsionali.',
    },
    modello_consumo: {
      description: 'Analizza consumi, prestazioni e assetti operativi della nave con indicatori e curve tecniche.',
    },
    impostazioni_avanzate: {
      description: 'Configura cache, Kafka e parametri di replanning da un unico pannello amministrativo.',
    },
  };

  const STYLE_ID = 'dashboard-shared-meta-style';

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .dashboard-page-desc {
        margin-top: 0.35rem;
        font-size: 0.95rem;
        line-height: 1.45;
        color: #94a3b8;
        max-width: 100%;
        margin-bottom: 0.5rem;
      }

      .dashboard-title-stack {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
      }

      .dashboard-title-stack .dashboard-page-title {
        font-weight: 700;
        line-height: 1.15;
        color: #e2e8f0;
        font-size: 26px; /* Uniform title size across dashboards */
      }

      .dashboard-title-stack .dashboard-page-desc {
        margin-top: 0;
      }
    `;
    document.head.appendChild(style);
  }

  function applyDescriptions() {
    document.querySelectorAll('[data-dashboard-desc]').forEach(el => {
      const key = el.dataset.dashboardDesc;
      const meta = DASHBOARD_META[key];
      if (!meta) return;
      el.textContent = meta.description;
    });
  }

  function init() {
    injectStyles();
    applyDescriptions();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

  window.DASHBOARD_META = DASHBOARD_META;
})();