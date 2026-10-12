import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { User, UserCreate, UserUpdate } from '../models';

@Injectable({
  providedIn: 'root'
})
export class AdminUsersService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  lister(): Observable<User[]> {
    return this.http.get<User[]>(`${this.apiUrl}/admin/users`).pipe(
      catchError(this.gererErreur)
    );
  }

  creer(user: UserCreate): Observable<User> {
    return this.http.post<User>(`${this.apiUrl}/admin/users`, user).pipe(
      catchError(this.gererErreur)
    );
  }

  modifier(userId: number, changements: UserUpdate): Observable<User> {
    return this.http.put<User>(`${this.apiUrl}/admin/users/${userId}`, changements).pipe(
      catchError(this.gererErreur)
    );
  }

  desactiver(userId: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/admin/users/${userId}`).pipe(
      catchError(this.gererErreur)
    );
  }

  private gererErreur(error: HttpErrorResponse): Observable<never> {
    let message: string;

    if (error.status === 0) {
      message = 'Service indisponible. Vérifiez que le serveur est démarré.';
    } else if (error.status === 400) {
      message = error.error?.detail || 'Requête invalide';
    } else if (error.status === 403) {
      message = 'Accès réservé aux administrateurs';
    } else if (error.status === 404) {
      message = 'Utilisateur non trouvé';
    } else {
      message = 'Une erreur est survenue';
    }

    return throwError(() => ({ message, status: error.status }));
  }
}
