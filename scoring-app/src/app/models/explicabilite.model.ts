import { ResultatScoring } from './resultat-scoring.model';

export interface FacteurExplicatif {
  nom_variable: string;
  shap_value: number;
  valeur_contrat: number;
  moyenne_portefeuille: number;
}

export interface ExplicationContrat {
  contrat_id: string;
  facteurs_explicatifs: FacteurExplicatif[];
  explication_disponible: boolean;
  timestamp: string;
}

export interface MoyennesPortefeuille {
  moyennes: Record<string, number>;
  nombre_contrats: number;
  date_calcul: string;
  cache_valide_jusqu_a: string;
}

export interface ResultatScoringAvecExplication extends ResultatScoring {
  facteurs_explicatifs: FacteurExplicatif[];
  explication_disponible: boolean;
}

export interface FacteurAffiche extends FacteurExplicatif {
  libelle: string;
  couleurBarre: 'rouge' | 'vert';
  directionBarre: 'droite' | 'gauche';
  indicateur: 'fleche-rouge-haut' | 'fleche-verte-bas' | null;
  largeurBarre: number;
}
