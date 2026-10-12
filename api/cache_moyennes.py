# cache_moyennes.py
"""Cache TTL pour les moyennes du portefeuille."""

from datetime import datetime, timedelta
from typing import Dict, Optional
import threading


class CacheMoyennes:
    """Cache TTL pour les moyennes du portefeuille.

    Fournit un mécanisme de cache thread-safe avec une durée de validité
    de 24 heures pour éviter des recalculs coûteux des moyennes du portefeuille.

    Le cache est protégé par un verrou (threading.Lock) pour garantir
    la cohérence en environnement multi-thread (FastAPI avec workers).
    """

    TTL_HEURES = 24

    def __init__(self):
        self._moyennes: Optional[Dict[str, float]] = None
        self._timestamp: Optional[datetime] = None
        self._lock = threading.Lock()

    def get(self) -> Optional[Dict[str, float]]:
        """Retourne les moyennes si le cache est valide, None sinon.

        Returns:
            Une copie du dictionnaire des moyennes si le cache est valide,
            None si le cache est vide ou expiré.
        """
        with self._lock:
            if self._moyennes is None or self._est_expire():
                return None
            return self._moyennes.copy()

    def set(self, moyennes: Dict[str, float]) -> None:
        """Met à jour le cache avec les nouvelles moyennes.

        Args:
            moyennes: Dictionnaire des moyennes {nom_variable: valeur_moyenne}.
        """
        with self._lock:
            self._moyennes = moyennes.copy()
            self._timestamp = datetime.now()

    def _est_expire(self) -> bool:
        """Vérifie si le cache a dépassé le TTL de 24 heures.

        Returns:
            True si le cache est expiré ou n'a jamais été initialisé.
        """
        if self._timestamp is None:
            return True
        return datetime.now() - self._timestamp > timedelta(hours=self.TTL_HEURES)

    def invalidate(self) -> None:
        """Force l'invalidation du cache.

        Remet le cache à son état initial (vide). Le prochain appel à get()
        retournera None, forçant un recalcul des moyennes.
        """
        with self._lock:
            self._moyennes = None
            self._timestamp = None
