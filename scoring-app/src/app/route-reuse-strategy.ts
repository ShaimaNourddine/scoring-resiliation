import { ActivatedRouteSnapshot, DetachedRouteHandle, RouteReuseStrategy } from '@angular/router';

/**
 * Stratégie de réutilisation des routes : garde en mémoire les composants
 * déjà visités (Dashboard, Batch, etc.) au lieu de les détruire à chaque
 * navigation. Résultat : si on quitte /batch après avoir lancé un scoring,
 * puis qu'on y revient, les résultats affichés sont toujours là — pas de
 * rechargement, pas de perte d'état. Un rafraîchissement manuel de la page
 * (F5) reste le seul moyen de repartir à zéro, puisque le cache vit en
 * mémoire JS et ne survit pas à un rechargement complet du navigateur.
 *
 * Routes avec un segment variable (ex: /scoring/contrat/:id) sont exclues
 * du cache par défaut via shouldReuseRoute pour éviter de mélanger l'état
 * de deux contrats différents sous la même route.
 */
export class CustomRouteReuseStrategy implements RouteReuseStrategy {
  private cacheHandles = new Map<string, DetachedRouteHandle>();

  /** Clé stable identifiant une route (chemin complet, sans les paramètres). */
  private getRouteKey(route: ActivatedRouteSnapshot): string {
    return route.pathFromRoot
      .map((segment) => segment.routeConfig?.path ?? '')
      .join('/');
  }

  /** Toujours autoriser la détection de réutilisation (même route = même composant). */
  shouldReuseRoute(future: ActivatedRouteSnapshot, curr: ActivatedRouteSnapshot): boolean {
    return future.routeConfig === curr.routeConfig;
  }

  /**
   * Décide si on doit détacher (mettre en cache) la route qu'on quitte.
   * La page de login est exclue : on ne veut jamais réafficher un ancien
   * formulaire (email/mot de passe saisis) après une déconnexion.
   */
  shouldDetach(route: ActivatedRouteSnapshot): boolean {
    return this.getRouteKey(route) !== 'login';
  }

  /** Stocke le handle détaché en mémoire sous la clé de la route. */
  store(route: ActivatedRouteSnapshot, handle: DetachedRouteHandle | null): void {
    if (handle) {
      this.cacheHandles.set(this.getRouteKey(route), handle);
    }
  }

  /** Indique si une version en cache existe pour la route qu'on va activer. */
  shouldAttach(route: ActivatedRouteSnapshot): boolean {
    return this.getRouteKey(route) !== 'login' && this.cacheHandles.has(this.getRouteKey(route));
  }

  /** Vide tout le cache (ex: à utiliser lors de la déconnexion). */
  clearCache(): void {
    this.cacheHandles.clear();
  }

  /** Restitue le composant mis en cache plutôt que d'en créer un nouveau. */
  retrieve(route: ActivatedRouteSnapshot): DetachedRouteHandle | null {
    return this.cacheHandles.get(this.getRouteKey(route)) ?? null;
  }
}
