import { Component, OnDestroy, OnInit } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router, RouteReuseStrategy } from '@angular/router';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBarModule } from '@angular/material/snack-bar';
import { Subscription } from 'rxjs';

import { HealthCheckService } from './services/health-check.service';
import { ErrorHandlerService, ErreurGlobale } from './services/error-handler.service';
import { AuthService } from './services/auth.service';
import { User } from './models';
import { CustomRouteReuseStrategy } from './route-reuse-strategy';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatToolbarModule,
    MatSidenavModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
    MatSnackBarModule,
  ],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit, OnDestroy {
  sidenavOpened = true;

  modeleIndisponible = false;
  serviceIndisponible = false;
  derniereErreur: ErreurGlobale | null = null;
  utilisateurConnecte: User | null = null;

  private subscriptions: Subscription[] = [];

  constructor(
    private healthCheckService: HealthCheckService,
    private errorHandlerService: ErrorHandlerService,
    private authService: AuthService,
    private router: Router,
    private routeReuseStrategy: RouteReuseStrategy
  ) {}

  ngOnInit(): void {
    this.subscriptions.push(
      this.healthCheckService.modeleIndisponible$.subscribe(
        (indisponible) => this.modeleIndisponible = indisponible
      )
    );

    this.subscriptions.push(
      this.healthCheckService.serviceIndisponible$.subscribe(
        (indisponible) => this.serviceIndisponible = indisponible
      )
    );

    this.subscriptions.push(
      this.errorHandlerService.derniereErreur$.subscribe(
        (erreur) => this.derniereErreur = erreur
      )
    );

    this.subscriptions.push(
      this.authService.currentUser$.subscribe(
        (user) => this.utilisateurConnecte = user
      )
    );
  }

  get estAdmin(): boolean {
    return this.utilisateurConnecte?.role === 'ADMIN';
  }

  /** Indique si une bannière d'erreur est affichée (pour ajuster la mise en page) */
  get banniereVisible(): boolean {
    return this.modeleIndisponible || this.serviceIndisponible;
  }

  reessayer(): void {
    this.errorHandlerService.reessayer();
  }

  seDeconnecter(): void {
    this.authService.logout();
    // Vide le cache des pages (Dashboard, Batch, ...) pour éviter qu'un
    // prochain utilisateur ne voie les données laissées par le précédent.
    if (this.routeReuseStrategy instanceof CustomRouteReuseStrategy) {
      this.routeReuseStrategy.clearCache();
    }
    this.router.navigate(['/login']);
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }
}
