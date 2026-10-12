/**
 * Dictionnaire de correspondance nom technique → libellé français
 * pour les variables du modèle de scoring de résiliation.
 */
export const DICTIONNAIRE_VARIABLES: Record<string, string> = {
  'ratio_rachats_primes': 'Ratio rachats/primes',
  'nb_avt_risque_eleve': 'Nb avenants risque élevé',
  'total_rachats': 'Total rachats',
  'total_primes': 'Total primes',
  'nb_mouvements': 'Nb mouvements',
  'nb_mouvements_annules': 'Nb mouvements annulés',
  'duree_annees': 'Durée (années)',
  'duree_mois': 'Durée (mois)',
  'versement_initial': 'Versement initial',
  'age_souscripteur': 'Âge souscripteur',
  'nb_avt_arret_annulation': 'Nb avenants arrêt/annulation',
  'nb_avt_arbitrage': 'Nb avenants arbitrage',
  'nb_avt_versement': 'Nb avenants versement',
  'nb_avt_modif_admin_motif': 'Nb modifications administratives',
  'flag_rachat_programme': 'Rachat programmé',
  'flag_renonciation': 'Renonciation',
  'flag_deces': 'Décès signalé',
  'produit': 'Type de produit',
  'tarif': 'Tarif',
  'cadre_fiscal': 'Cadre fiscal',
  'periodicite': 'Périodicité',
  'mode_reglement': 'Mode de règlement',
  'sexe': 'Sexe',
  'csp': 'CSP',
  'situation_famille': 'Situation familiale'
};

/**
 * Retourne le libellé français d'une variable.
 * Si la variable n'est pas dans le dictionnaire, formate le nom technique :
 * - Remplace les underscores par des espaces
 * - Met une majuscule initiale
 */
export function getLibelleVariable(nomTechnique: string): string {
  if (DICTIONNAIRE_VARIABLES[nomTechnique]) {
    return DICTIONNAIRE_VARIABLES[nomTechnique];
  }
  // Fallback : formatage du nom technique
  return nomTechnique
    .replace(/_/g, ' ')
    .replace(/^./, c => c.toUpperCase());
}
