import { Injectable, OnDestroy } from '@angular/core';
import { BehaviorSubject, Subscription, interval } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import { ScoringService } from './scoring.service';
import { NotificationService } from './notification.service';

@Injectable({
  providedIn: 'root'
})
export class HealthCheckService implements OnDestroy {
  private readonly intervalMs = 30000; // 30 secondes
  private pollingSubscription: Subscription | null = null;

  /** Indique si le service est actuellement indisponible */
  serviceIndisponible$ = new BehaviorSubject<boolean>(false);

  /** Indique si le modèle retourne 503 */
  modeleIndisponible$ = new BehaviorSubject<boolean>(false);

  constructor(
    private scoringService: ScoringService,
    private notificationService: NotificationService
  ) {}

  /**
   * Démarre le polling /health toutes les 30 secondes.
   * Appelé automatiquement lorsqu'une erreur réseau se produit.
   */
  demarrerVerification(): void {
    if (this.pollingSubscription) {
      return; // Déjà en cours
    }

    this.serviceIndisponible$.next(true);

    this.pollingSubscription = interval(this.intervalMs).pipe(
      switchMap(() => this.scoringService.verifierSante())
    ).subscribe({
      next: (etat) => {
        // Le service est de nouveau accessible
        this.serviceIndisponible$.next(false);

        if (etat.model_loaded) {
          this.modeleIndisponible$.next(false);
        }

        this.notificationService.afficherSucces('Service rétabli');
        this.arreterVerification();
      },
      error: () => {
        // Le service est toujours indisponible, on continue le polling
        this.serviceIndisponible$.next(true);
      }
    });
  }

  /**
   * Arrête le polling /health.
   */
  arreterVerification(): void {
    if (this.pollingSubscription) {
      this.pollingSubscription.unsubscribe();
      this.pollingSubscription = null;
    }
  }

  /**
   * Signale qu'une erreur réseau a eu lieu.
   * Démarre le health check automatiquement.
   */
  signalerErreurReseau(): void {
    this.serviceIndisponible$.next(true);
    this.demarrerVerification();
  }

  /**
   * Signale que le modèle est indisponible (erreur 503).
   * Démarre le health check automatiquement.
   */
  signalerModeleIndisponible(): void {
    this.modeleIndisponible$.next(true);
    this.demarrerVerification();
  }

  ngOnDestroy(): void {
    this.arreterVerification();
  }
}
