import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { finalize } from 'rxjs/operators';

import { ScoringService } from '../../services/scoring.service';
import { ExplicabiliteService } from '../../services/explicabilite.service';
import { ErrorHandlerService } from '../../services/error-handler.service';
import { ResultatScoring, FacteurExplicatif, MoyennesPortefeuille } from '../../models';
import { JaugeScoreComponent } from '../../shared/jauge-score/jauge-score.component';
import { NiveauBadgeComponent } from '../../shared/niveau-badge/niveau-badge.component';
import { PanneauExplicationComponent } from '../../shared/panneau-explication/panneau-explication.component';

@Component({
  selector: 'app-scoring-contrat',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatCardModule,
    MatIconModule,
    MatListModule,
    JaugeScoreComponent,
    NiveauBadgeComponent,
    PanneauExplicationComponent,
  ],
  templateUrl: './scoring-contrat.component.html',
  styleUrl: './scoring-contrat.component.scss'
})
export class ScoringContratComponent {
  contratId: string = '';
  resultat: ResultatScoring | null = null;
  chargement: boolean = false;
  erreur: string | null = null;

  // Explicabilité
  facteurs: FacteurExplicatif[] = [];
  moyennes: MoyennesPortefeuille | null = null;
  chargementExplication = false;
  erreurExplication: string | null = null;
  explicationDisponible = true;

  constructor(
    private scoringService: ScoringService,
    private explicabiliteService: ExplicabiliteService,
    private errorHandlerService: ErrorHandlerService
  ) {}

  scorerContrat(): void {
    if (!this.contratId.trim()) {
      return;
    }

    this.chargement = true;
    this.erreur = null;
    this.resultat = null;
    this.facteurs = [];
    this.moyennes = null;
    this.chargementExplication = false;
    this.erreurExplication = null;
    this.explicationDisponible = true;
    this.errorHandlerService.effacerErreur();

    this.scoringService.scorerContrat(this.contratId.trim())
      .pipe(
        finalize(() => this.chargement = false)
      )
      .subscribe({
        next: (resultat) => {
          this.resultat = resultat;

          // Extraire les données d'explicabilité de la réponse enrichie
          const enriched = resultat as any;
          if (enriched.facteurs_explicatifs) {
            this.facteurs = enriched.facteurs_explicatifs;
          }
          this.explicationDisponible = enriched.explication_disponible ?? true;

          // Charger les moyennes du portefeuille en parallèle
          this.chargementExplication = true;
          this.explicabiliteService.getMoyennesPortefeuille().subscribe({
            next: (m) => {
              this.moyennes = m;
              this.chargementExplication = false;
            },
            error: () => {
              // Dégradation gracieuse : afficher sans moyennes
              this.moyennes = null;
              this.chargementExplication = false;
            }
          });
        },
        error: (err) => {
          this.erreur = err.message || 'Erreur lors du scoring';
          this.errorHandlerService.gererErreur(err);
        }
      });
  }

  reinitialiser(): void {
    this.contratId = '';
    this.resultat = null;
    this.erreur = null;
    this.chargement = false;
    this.facteurs = [];
    this.moyennes = null;
    this.chargementExplication = false;
    this.erreurExplication = null;
    this.explicationDisponible = true;
  }

  rechargerExplication(): void {
    if (!this.contratId.trim()) {
      return;
    }

    this.chargementExplication = true;
    this.erreurExplication = null;

    this.explicabiliteService.getExplicationContrat(this.contratId.trim()).subscribe({
      next: (explication) => {
        this.facteurs = explication.facteurs_explicatifs;
        this.explicationDisponible = explication.explication_disponible;
        this.chargementExplication = false;
      },
      error: (err) => {
        this.erreurExplication = err.message || 'Impossible de charger l\'explication';
        this.chargementExplication = false;
      }
    });
  }

  getNiveauCouleur(niveau: string): string {
    switch (niveau) {
      case 'CRITIQUE': return '#f44336';
      case 'ÉLEVÉ': return '#ff9800';
      case 'MOYEN': return '#ffeb3b';
      case 'FAIBLE': return '#4caf50';
      default: return '#9e9e9e';
    }
  }

  getFeatureLabel(feature: string): string {
    const labels: Record<string, string> = {
      'TOTAL_PRIMES_SCALED': 'Total primes',
      'TOTAL_RACHATS_SCALED': 'Total rachats',
      'TOTAL_ARBITRE_SCALED': 'Total arbitrages',
      'NB_MOUVEMENTS_SCALED': 'Nb mouvements',
      'AGE_SOUSCRIPTEUR_SCALED': 'Âge souscripteur',
      'RATIO_RACHATS_PRIMES': 'Ratio rachats/primes',
      'RATIO_ARBITRE_PRIMES': 'Ratio arbitrages/primes',
      'NB_PROFILS_ACTIFS': 'Nb profils actifs',
      'CONTRAT_RECENT': 'Contrat récent',
      'SEXE_ENCODED': 'Sexe',
      'MULTI_PROFILS_ENCODED': 'Multi-profils',
      'PRODUIT_TARGET_ENCODED': 'Type de produit',
      'PROFESSION_TARGET_ENCODED': 'Profession',
      'CODE_POSTAL_TARGET_ENCODED': 'Zone géographique',
      'AVENANT_1_MOTIF_TARGET_ENCODED': 'Motif avenant 1',
      'AVENANT_2_MOTIF_TARGET_ENCODED': 'Motif avenant 2',
      'AVENANT_3_MOTIF_TARGET_ENCODED': 'Motif avenant 3',
      'AVENANT_4_MOTIF_TARGET_ENCODED': 'Motif avenant 4',
      'AVENANT_5_MOTIF_TARGET_ENCODED': 'Motif avenant 5',
      'AVENANT_6_MOTIF_TARGET_ENCODED': 'Motif avenant 6',
      'AVENANT_1_MOTIF_FREQ': 'Fréquence avenant 1',
      'AVENANT_2_MOTIF_FREQ': 'Fréquence avenant 2',
      'AVENANT_3_MOTIF_FREQ': 'Fréquence avenant 3',
      'AVENANT_4_MOTIF_FREQ': 'Fréquence avenant 4',
      'AVENANT_5_MOTIF_FREQ': 'Fréquence avenant 5',
      'AVENANT_6_MOTIF_FREQ': 'Fréquence avenant 6',
      'NATURE_PRODUIT_AV': 'Nature produit AV',
      'NATURE_PRODUIT_BC': 'Nature produit BC',
      'PAYS_F': 'Pays France',
    };
    return labels[feature] || feature.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase());
  }

  getBarWidth(contribution: number): number {
    const maxContribution = Math.max(...this.resultat!.top_facteurs.map((f: any) => Math.abs(f.contribution)));
    return maxContribution > 0 ? (Math.abs(contribution) / maxContribution) * 100 : 0;
  }
}
