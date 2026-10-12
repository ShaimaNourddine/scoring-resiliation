import { Component, Input, OnChanges, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { FacteurExplicatif, FacteurAffiche, MoyennesPortefeuille } from '../../models/explicabilite.model';
import { getLibelleVariable } from '../dictionnaire-variables';

@Component({
  selector: 'app-panneau-explication',
  standalone: true,
  imports: [CommonModule, MatProgressSpinnerModule, MatIconModule, MatButtonModule],
  templateUrl: './panneau-explication.component.html',
  styleUrl: './panneau-explication.component.scss'
})
export class PanneauExplicationComponent implements OnChanges {
  @Input() facteurs: FacteurExplicatif[] = [];
  @Input() moyennes: MoyennesPortefeuille | null = null;
  @Input() chargement = false;
  @Input() erreur: string | null = null;
  @Input() explicationDisponible = true;

  @Output() reessayer = new EventEmitter<void>();

  facteursAffiches: FacteurAffiche[] = [];

  ngOnChanges(): void {
    if (this.facteurs.length > 0) {
      this.facteursAffiches = this.facteurs.map(f => ({
        ...f,
        libelle: this.getLibelle(f.nom_variable),
        couleurBarre: f.shap_value > 0 ? 'rouge' as const : 'vert' as const,
        directionBarre: f.shap_value > 0 ? 'droite' as const : 'gauche' as const,
        indicateur: this.getIndicateur(f),
        largeurBarre: this.calculerLargeurBarre(f)
      }));
    } else {
      this.facteursAffiches = [];
    }
  }

  getLibelle(nomVariable: string): string {
    return getLibelleVariable(nomVariable);
  }

  getIndicateur(facteur: FacteurExplicatif): 'fleche-rouge-haut' | 'fleche-verte-bas' | null {
    if (facteur.shap_value <= 0) {
      return null;
    }
    if (facteur.valeur_contrat > facteur.moyenne_portefeuille) {
      return 'fleche-rouge-haut';
    }
    if (facteur.valeur_contrat < facteur.moyenne_portefeuille) {
      return 'fleche-verte-bas';
    }
    return null;
  }

  calculerLargeurBarre(facteur: FacteurExplicatif): number {
    if (this.facteurs.length === 0) {
      return 0;
    }
    const maxAbsShap = Math.max(...this.facteurs.map(f => Math.abs(f.shap_value)));
    if (maxAbsShap === 0) {
      return 0;
    }
    return (Math.abs(facteur.shap_value) / maxAbsShap) * 100;
  }

  onReessayer(): void {
    this.reessayer.emit();
  }
}
