import { inject } from '@angular/core';
import { HttpInterceptorFn } from '@angular/common/http';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { AuthService } from '../services/auth.service';

/**
 * Ajoute automatiquement le header Authorization: Bearer <token> sur
 * chaque requête HTTP sortante (sauf /auth/login, qui n'en a pas besoin).
 * En cas de 401 (token expiré/invalide), déconnecte l'utilisateur et
 * redirige vers /login.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const token = authService.getToken();
  const estRequeteLogin = req.url.includes('/auth/login');

  const requeteAvecToken = (token && !estRequeteLogin)
    ? req.clone({ headers: req.headers.set('Authorization', `Bearer ${token}`) })
    : req;

  return next(requeteAvecToken).pipe(
    catchError((error) => {
      if (error.status === 401 && !estRequeteLogin) {
        authService.logout();
        router.navigate(['/login']);
      }
      return throwError(() => error);
    })
  );
};
