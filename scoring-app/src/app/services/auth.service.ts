import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { BehaviorSubject, Observable, tap, catchError, throwError, of } from 'rxjs';

import { environment } from '../../environments/environment';
import { TokenResponse, User } from '../models';

const TOKEN_KEY = 'scoring_auth_token';
const USER_KEY = 'scoring_auth_user';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly apiUrl = environment.apiUrl;

  private currentUserSubject = new BehaviorSubject<User | null>(this.lireUtilisateurStocke());
  readonly currentUser$ = this.currentUserSubject.asObservable();

  constructor(private http: HttpClient) {}

  login(email: string, password: string): Observable<TokenResponse> {
    // L'API attend un formulaire OAuth2 standard (username/password), pas du JSON.
    const body = new URLSearchParams();
    body.set('username', email);
    body.set('password', password);

    return this.http.post<TokenResponse>(
      `${this.apiUrl}/auth/login`,
      body.toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    ).pipe(
      tap((reponse) => this.stockerSession(reponse)),
      catchError(this.gererErreur)
    );
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    this.currentUserSubject.next(null);
  }

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  getCurrentUser(): User | null {
    return this.currentUserSubject.value;
  }

  isLoggedIn(): boolean {
    return !!this.getToken() && !!this.getCurrentUser();
  }

  isAdmin(): boolean {
    return this.getCurrentUser()?.role === 'ADMIN';
  }

  /** Revalide la session auprès de l'API (utile après un rechargement de page). */
  verifierSession(): Observable<User | null> {
    if (!this.getToken()) {
      return of(null);
    }
    return this.http.get<User>(`${this.apiUrl}/auth/me`).pipe(
      tap((user) => {
        this.currentUserSubject.next(user);
        localStorage.setItem(USER_KEY, JSON.stringify(user));
      }),
      catchError(() => {
        this.logout();
        return of(null);
      })
    );
  }

  private stockerSession(reponse: TokenResponse): void {
    localStorage.setItem(TOKEN_KEY, reponse.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(reponse.user));
    this.currentUserSubject.next(reponse.user);
  }

  private lireUtilisateurStocke(): User | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as User;
    } catch {
      return null;
    }
  }

  private gererErreur(error: HttpErrorResponse): Observable<never> {
    let message: string;

    if (error.status === 0) {
      message = 'Service indisponible. Vérifiez que le serveur est démarré.';
    } else if (error.status === 401) {
      message = 'Email ou mot de passe incorrect';
    } else {
      message = 'Une erreur est survenue lors de la connexion';
    }

    return throwError(() => ({ message, status: error.status }));
  }
}
