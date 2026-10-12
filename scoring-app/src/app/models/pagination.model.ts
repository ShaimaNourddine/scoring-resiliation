import { NiveauRisque, ResultatScoring } from './resultat-scoring.model';

export interface FiltresContrats {
  produit: string;
  niveau: NiveauRisque | '';
  recherche?: string;
}

export interface Pagination {
  page: number;
  taille: number;
  total: number;
}

export interface PageContrats {
  contrats: ResultatScoring[];
  pagination: Pagination;
}
