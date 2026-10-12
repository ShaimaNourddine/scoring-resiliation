import { ResultatScoring } from './resultat-scoring.model';

export interface StatistiquesDashboard {
  total_contrats: number;
  critique: number;
  eleve: number;
  moyen: number;
  faible: number;
  score_moyen: number;
  top10: ResultatScoring[];
}
