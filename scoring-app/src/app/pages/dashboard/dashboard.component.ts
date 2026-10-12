import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';

import { environment } from '../../../environments/environment';
import { ScoringService } from '../../services/scoring.service';
import { ExplicabiliteService } from '../../services/explicabilite.service';
import { StatistiquesDashboard, FacteurExplicatif, MoyennesPortefeuille } from '../../models';
import { PanneauExplicationComponent } from '../../shared/panneau-explication/panneau-explication.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatTabsModule,
    PanneauExplicationComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  // Power BI
  powerBiUrl: SafeResourceUrl | null = null;
  powerBiConfigure = !!environment.powerBiEmbedUrl;
  statistiques: StatistiquesDashboard | null = null;
  chargement = false;
  erreur: string | null = null;

  // Accordion state
  panneauOuvertId: string | null = null;
  facteursAccordion: FacteurExplicatif[] = [];
  chargementAccordion = false;
  erreurAccordion: string | null = null;
  explicationAccordionDisponible = true;
  moyennesAccordion: MoyennesPortefeuille | null = null;

  // Filtres
  filtreNiveau: string = '';
  recherche: string = '';
  contratsFiltres: any[] = [];

  constructor(
    private scoringService: ScoringService,
    private explicabiliteService: ExplicabiliteService,
    private router: Router,
    private sanitizer: DomSanitizer
  ) {}

  ngOnInit(): void {
    // Ne pas charger automatiquement les statistiques - uniquement au clic "Rafraîchir"

    // Prépare l'URL d'intégration Power BI (si configurée). bypassSecurityTrustResourceUrl
    // est nécessaire car Angular bloque par défaut les URLs d'iframe non reconnues ;
    // l'URL provient d'une constante de configuration (environment), pas d'une saisie
    // utilisateur, donc pas de risque d'injection ici.
    if (environment.powerBiEmbedUrl) {
      this.powerBiUrl = this.sanitizer.bypassSecurityTrustResourceUrl(environment.powerBiEmbedUrl);
    }
  }

  chargerStatistiques(): void {
    this.chargement = true;
    this.erreur = null;

    this.scoringService.getStatistiques().subscribe({
      next: (stats) => {
        this.statistiques = stats;
        this.contratsFiltres = (stats as any).top10 || [];
        this.chargement = false;
      },
      error: (err) => {
        this.erreur = err.message || 'Erreur lors du chargement des statistiques';
        this.chargement = false;
      }
    });
  }

  allerAuScoring(): void {
    this.router.navigate(['/scoring']);
  }

  filtrerContrats(): void {
    if (!this.statistiques) return;
    
    let contrats = (this.statistiques as any).top10 ? [...(this.statistiques as any).top10] : [];
    
    if (this.filtreNiveau) {
      contrats = contrats.filter((c: any) => c.niveau_risque === this.filtreNiveau);
    }
    
    if (this.recherche.trim()) {
      contrats = contrats.filter((c: any) => 
        c.contrat_id.toString().includes(this.recherche.trim())
      );
    }
    
    this.contratsFiltres = contrats;
  }

  /**
   * Toggle le panneau déroulant pour un contrat du top 10.
   * Mécanisme accordion : un seul panneau ouvert à la fois.
   */
  togglePanneau(contratId: string): void {
    if (this.panneauOuvertId === contratId) {
      // Fermer le panneau si on clique sur le même contrat
      this.panneauOuvertId = null;
      return;
    }

    // Ouvrir le nouveau panneau (ferme automatiquement l'ancien)
    this.panneauOuvertId = contratId;
    this.chargementAccordion = true;
    this.erreurAccordion = null;
    this.facteursAccordion = [];
    this.explicationAccordionDisponible = true;

    // Charger les facteurs explicatifs
    this.explicabiliteService.getExplicationContrat(contratId).subscribe({
      next: (explication) => {
        this.facteursAccordion = explication.facteurs_explicatifs;
        this.explicationAccordionDisponible = explication.explication_disponible;
        this.chargementAccordion = false;
      },
      error: (err) => {
        this.erreurAccordion = err.message || 'Impossible de charger l\'explication';
        this.chargementAccordion = false;
      }
    });

    // Charger les moyennes en parallèle
    this.explicabiliteService.getMoyennesPortefeuille().subscribe({
      next: (m) => this.moyennesAccordion = m,
      error: () => this.moyennesAccordion = null
    });
  }

  /**
   * Réessayer le chargement de l'explication pour le panneau actuellement ouvert.
   */
  rechargerAccordion(): void {
    if (this.panneauOuvertId) {
      const contratId = this.panneauOuvertId;
      this.panneauOuvertId = null;
      this.togglePanneau(contratId);
    }
  }
}
