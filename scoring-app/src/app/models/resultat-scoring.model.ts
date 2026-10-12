export type NiveauRisque = 'CRITIQUE' | 'ÉLEVÉ' | 'MOYEN' | 'FAIBLE';

export interface TopFacteur {
  feature: string;
  contribution: number;
}

export interface ResultatScoring {
  contrat_id: string;
  score_risque: number;
  classe_predite: number;
  niveau_risque: NiveauRisque;
  top_facteurs: TopFacteur[];
  timestamp: string;
}
