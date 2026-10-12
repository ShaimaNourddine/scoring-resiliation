import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, timeout } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import {
  ResultatScoring,
  StatistiquesDashboard,
  FiltresContrats,
  Pagination,
  PageContrats,
  ResultatBatch,
  EtatSante
} from '../models';

@Injectable({
  providedIn: 'root'
})
export class ScoringService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  scorerContrat(contratId: string): Observable<ResultatScoring> {
    return this.http.get<ResultatScoring>(
      `${this.apiUrl}/scoring/contrat/${contratId}`
    ).pipe(
      catchError(this.gererErreur)
    );
  }

  getStatistiques(): Observable<StatistiquesDashboard> {
    return this.http.get<StatistiquesDashboard>(
      `${this.apiUrl}/dashboard/stats`
    ).pipe(
      catchError(this.gererErreur)
    );
  }

  getListeContrats(filtres: FiltresContrats, pagination: Pagination): Observable<PageContrats> {
    let params = new HttpParams()
      .set('page', pagination.page.toString())
      .set('taille', pagination.taille.toString());

    if (filtres.produit) {
      params = params.set('produit', filtres.produit);
    }
    if (filtres.niveau) {
      params = params.set('niveau', filtres.niveau);
    }
    if (filtres.recherche) {
      params = params.set('recherche', filtres.recherche);
    }

    return this.http.get<PageContrats>(
      `${this.apiUrl}/contrats`,
      { params }
    ).pipe(
      catchError(this.gererErreur)
    );
  }

  lancerBatch(): Observable<ResultatBatch> {
    return this.http.post<ResultatBatch>(
      `${this.apiUrl}/predict_batch`,
      {}
    ).pipe(
      timeout(300000), // 5 minutes max
      catchError(this.gererErreur)
    );
  }

  verifierSante(): Observable<EtatSante> {
    return this.http.get<EtatSante>(
      `${this.apiUrl}/health`
    ).pipe(
      catchError(this.gererErreur)
    );
  }

  private gererErreur(error: HttpErrorResponse): Observable<never> {
    let message: string;

    if (error.status === 0) {
      message = 'Service indisponible. Vérifiez que le serveur est démarré.';
    } else if (error.status === 404) {
      message = 'Aucun contrat trouvé avec cet identifiant';
    } else if (error.status === 503) {
      message = 'Le modèle de scoring n\'est pas disponible. Contactez l\'administrateur.';
    } else if ((error as any).name === 'TimeoutError') {
      message = 'Le traitement a pris trop de temps.';
    } else {
      message = 'Une erreur est survenue';
    }

    return throwError(() => ({ message, status: error.status }));
  }
}
