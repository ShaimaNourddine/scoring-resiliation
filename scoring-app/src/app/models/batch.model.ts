import { ResultatScoring } from './resultat-scoring.model';

export interface ResultatBatch {
  predictions: ResultatScoring[];
  summary: {
    total_contrats: number;
    score_moyen: number;
    contrats_critiques: number;
    contrats_eleves: number;
    contrats_moderes: number;
    contrats_faibles: number;
  };
}
