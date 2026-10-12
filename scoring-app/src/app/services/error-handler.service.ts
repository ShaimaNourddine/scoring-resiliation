import { Injectable } from '@angular/core';
import { BehaviorSubject, Subject } from 'rxjs';

import { NotificationService } from './notification.service';
import { HealthCheckService } from './health-check.service';

export interface ErreurGlobale {
  message: string;
  status: number;
  timestamp: Date;
  retryable: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class ErrorHandlerService {
  /** Dernière erreur survenue (pour le bouton Réessayer) */
  derniereErreur$ = new BehaviorSubject<ErreurGlobale | null>(null);

  /** Événement émis quand l'utilisateur clique sur Réessayer */
  reessayer$ = new Subject<void>();

  constructor(
    private notificationService: NotificationService,
    private healthCheckService: HealthCheckService
  ) {}

  /**
   * Gère une erreur API de manière centralisée.
   * - Affiche un SnackBar avec le message en français
   * - Démarre le health check si erreur réseau
   * - Affiche la bannière 503 si modèle non disponible
   */
  gererErreur(erreur: { message: string; status: number }): void {
    const erreurGlobale: ErreurGlobale = {
      message: erreur.message,
      status: erreur.status,
      timestamp: new Date(),
      retryable: erreur.status === 0 || erreur.status >= 500
    };

    this.derniereErreur$.next(erreurGlobale);

    // Afficher le SnackBar
    this.notificationService.afficherErreur(erreur.message);

    // Erreur réseau (status 0 = connection refused / timeout)
    if (erreur.status === 0) {
      this.healthCheckService.signalerErreurReseau();
    }

    // Modèle non disponible (503)
    if (erreur.status === 503) {
      this.healthCheckService.signalerModeleIndisponible();
    }
  }

  /**
   * Efface l'erreur en cours (appelé avant un nouvel appel API).
   */
  effacerErreur(): void {
    this.derniereErreur$.next(null);
  }

  /**
   * Émet un événement de réessai.
   */
  reessayer(): void {
    this.effacerErreur();
    this.reessayer$.next();
  }
}
