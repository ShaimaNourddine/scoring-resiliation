import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '../services/auth.service';

/**
 * Protège une route : redirige vers /login si l'utilisateur n'est pas
 * authentifié. Utilisé sur toutes les routes existantes (scoring,
 * dashboard, contrats, batch) via app.routes.ts.
 */
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isLoggedIn()) {
    return true;
  }

  router.navigate(['/login'], { queryParams: { returnUrl: state.url } });
  return false;
};

/**
 * Protège une route réservée aux administrateurs (ex: /admin/users).
 * Redirige vers /scoring (page par défaut) si l'utilisateur est connecté
 * mais n'a pas le rôle ADMIN, ou vers /login s'il n'est pas connecté.
 */
export const adminGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (!authService.isLoggedIn()) {
    router.navigate(['/login'], { queryParams: { returnUrl: state.url } });
    return false;
  }

  if (!authService.isAdmin()) {
    router.navigate(['/scoring']);
    return false;
  }

  return true;
};
