"""Semplice client API per chiamate GET al base URL fornito.

Fornisce la funzione `get_json(endpoint, params=None, timeout=5)` che
effettua una GET a `http://87.26.178.190:15080/<endpoint>` e ritorna
il JSON decodificato come dict. Usa `requests` se presente, altrimenti
usa un fallback con `urllib`.
"""
from typing import Any, Dict, Optional

BASE_URL = "http://87.26.178.190:15080/"

import os
import webbrowser

# keep references to open dashboard dialogs so they aren't garbage-collected
_open_dashboards: list = []


def open_dashboard(page_relative: str, query: Optional[Dict[str, str]] = None, title: Optional[str] = None, size=(1000, 700)) -> None:
    """Open a local HTML dashboard page.

    Tries to open the page embedded using QWebEngineView if PyQt5 is available,
    otherwise falls back to opening the page in the system default browser.

    Args:
        page_relative: path relative to the project folder (e.g. 'static/porto.html').
        query: optional dict of query parameters to append.
        title: optional window title used when embedding.
        size: tuple (width, height) for the embedded dialog.
    """
    # resolve absolute path relative to this file (project folder)
    base = os.path.join(os.path.dirname(__file__), page_relative)
    base = os.path.abspath(base)

    # build query string
    qstr = None
    if query:
        from urllib.parse import urlencode

        qstr = urlencode({k: str(v) for k, v in query.items()})

    # try embedded viewer
    try:
        from PyQt5.QtWidgets import QDialog, QVBoxLayout
        from PyQt5.QtCore import QUrl, Qt
        try:
            from PyQt5.QtWebEngineWidgets import QWebEngineView
        except Exception:
            QWebEngineView = None

        if QWebEngineView is not None:
            dlg = QDialog()
            dlg.setWindowTitle(title or 'Dashboard')
            # make the embedded dialog a top-level window so minimizing it
            # does not minimize the main application
            dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
            dlg.resize(size[0], size[1])
            layout = QVBoxLayout(dlg)
            view = QWebEngineView()
            url = QUrl.fromLocalFile(base)
            if qstr:
                url.setQuery(qstr)
            view.load(url)
            layout.addWidget(view)
            # Show modeless (non-blocking) dialog so user can continue using app
            dlg.setModal(False)
            try:
                dlg.setWindowModality(Qt.NonModal)
            except Exception:
                pass
            dlg.show()
            # retain reference to avoid garbage collection
            _open_dashboards.append(dlg)

            def _cleanup(obj, dlg=dlg):
                try:
                    _open_dashboards.remove(dlg)
                except ValueError:
                    pass

            dlg.destroyed.connect(_cleanup)
            return
    except Exception:
        # if embedding fails, fallback to browser
        pass

    # fallback: open in default browser
    try:
        from PyQt5.QtCore import QUrl
        url = QUrl.fromLocalFile(base)
        url_str = url.toString()
    except Exception:
        url_str = 'file://' + base
    if qstr:
        url_str = url_str + ('?' if '?' not in url_str else '&') + qstr
    webbrowser.open(url_str)


def get_json(endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: int = 5) -> Dict[str, Any]:
    """Esegue una GET e restituisce il JSON parsato.

    Args:
        endpoint: path relativo o assoluto (es. 'status' o '/api/status').
        params: mappa di query params opzionale.
        timeout: timeout in secondi per la richiesta.

    Returns:
        Dizionario ottenuto dal JSON di risposta.

    Raises:
        RuntimeError: in caso di errore di rete o parsing.
    """
    url = BASE_URL.rstrip('/') + '/' + endpoint.lstrip('/')
    # Prima prova con requests se disponibile
    try:
        import requests

        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        # Fallback a urllib
        try:
            from urllib.request import urlopen, Request
            from urllib.parse import urlencode
            import json as _json

            if params:
                url_with_q = url + '?' + urlencode(params)
            else:
                url_with_q = url
            req = Request(url_with_q, headers={'Accept': 'application/json'})
            with urlopen(req, timeout=timeout) as r:
                data = r.read()
                return _json.loads(data.decode('utf-8'))
        except Exception as e:
            raise RuntimeError(f'GET {url} failed: {e}')


def post_json(endpoint: str, payload: Any, timeout: int = 10) -> Dict[str, Any]:
    """Esegue una POST JSON verso l'endpoint specificato e ritorna il JSON di risposta.

    Args:
        endpoint: path relativo o assoluto (es. 'corsa/create' o '/api/corsa').
        payload: oggetto serializzabile in JSON da inviare nel body.
        timeout: timeout in secondi per la richiesta.

    Returns:
        Dizionario ottenuto dal JSON di risposta oppure `{}` se la risposta è vuota.

    Raises:
        RuntimeError: in caso di errore di rete o parsing.
    """
    url = BASE_URL.rstrip('/') + '/' + endpoint.lstrip('/')
    # Preferisci requests quando disponibile
    try:
        import requests

        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {}
    except Exception:
        # Fallback a urllib
        try:
            from urllib.request import Request, urlopen
            import json as _json

            data = _json.dumps(payload).encode('utf-8')
            req = Request(url, data=data, headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
            with urlopen(req, timeout=timeout) as r:
                data = r.read()
                if not data:
                    return {}
                return _json.loads(data.decode('utf-8'))
        except Exception as e:
            raise RuntimeError(f'POST {url} failed: {e}')


__all__ = ['get_json', 'post_json']
