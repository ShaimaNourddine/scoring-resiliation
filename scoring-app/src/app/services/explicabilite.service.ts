import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, shareReplay } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { ExplicationContrat, MoyennesPortefeuille } from '../models/explicabilite.model';

@Injectable({
  providedIn: 'root'
})
export class ExplicabiliteService {
  private readonly apiUrl = environment.apiUrl;
  private moyennesCache$: Observable<MoyennesPortefeuille> | null = null;

  constructor(private http: HttpClient) {}

  /**
   * Récupère les facteurs explicatifs SHAP pour un contrat donné.
   * En cas d'erreur, propage l'erreur pour que le composant affiche
   * "Impossible de charger l'explication" avec un bouton Réessayer.
   */
  getExplicationContrat(contratId: string): Observable<ExplicationContrat> {
    return this.http.get<ExplicationContrat>(
      `${this.apiUrl}/scoring/contrat/${contratId}/explication`
    ).pipe(
      catchError(this.gererErreur)
    );
  }

  /**
   * Récupère les moyennes du portefeuille avec mise en cache RxJS.
   * Le shareReplay(1) garantit qu'un seul appel HTTP est effectué
   * et que le résultat est partagé entre tous les abonnés.
   * En cas d'erreur, propage l'erreur pour que le composant affiche
   * les facteurs sans la colonne Moyenne_Portefeuille.
   */
  getMoyennesPortefeuille(): Observable<MoyennesPortefeuille> {
    if (!this.moyennesCache$) {
      this.moyennesCache$ = this.http.get<MoyennesPortefeuille>(
        `${this.apiUrl}/portefeuille/moyennes`
      ).pipe(
        shareReplay(1),
        catchError((error) => {
          // Vider le cache en cas d'erreur pour permettre une nouvelle tentative
          // au prochain appel (évite de mémoriser l'échec indéfiniment)
          this.moyennesCache$ = null;
          return this.gererErreur(error);
        })
      );
    }
    return this.moyennesCache$;
  }

  private gererErreur(error: HttpErrorResponse): Observable<never> {
    let message: string;

    if (error.status === 0) {
      message = 'Service indisponible. Vérifiez que le serveur est démarré.';
    } else if (error.status === 404) {
      message = 'Contrat non trouvé ou non scoré';
    } else if (error.status === 503) {
      message = 'Le service d\'explicabilité n\'est pas disponible.';
    } else {
      message = 'Une erreur est survenue lors du chargement de l\'explication';
    }

    return throwError(() => ({ message, status: error.status }));
  }
}
