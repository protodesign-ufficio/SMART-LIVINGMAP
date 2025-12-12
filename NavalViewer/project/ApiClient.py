"""Semplice client API per chiamate GET al base URL fornito.

Fornisce la funzione `get_json(endpoint, params=None, timeout=5)` che
effettua una GET a `http://87.26.178.190:15080/<endpoint>` e ritorna
il JSON decodificato come dict. Usa `requests` se presente, altrimenti
usa un fallback con `urllib`.
"""
from typing import Any, Dict, Optional

BASE_URL = "http://87.26.178.190:15080/"


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


def post_json(endpoint: str, payload: Any, timeout: int = 5) -> Dict[str, Any]:
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
