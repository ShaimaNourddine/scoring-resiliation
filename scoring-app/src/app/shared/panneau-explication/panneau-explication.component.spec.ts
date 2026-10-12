import '@angular/compiler';
import { PanneauExplicationComponent } from './panneau-explication.component';
import { FacteurExplicatif, MoyennesPortefeuille } from '../../models/explicabilite.model';

/**
 * Unit tests for PanneauExplicationComponent
 *
 * Tests the component logic (mapping, indicators, bar widths, state handling)
 * without requiring Angular TestBed DOM rendering (Vitest environment).
 *
 * Validates: Requirements 3.1, 3.7
 */
describe('PanneauExplicationComponent', () => {
  let component: PanneauExplicationComponent;

  beforeEach(() => {
    component = new PanneauExplicationComponent();
  });

  // =========================================================================
  // 1. Component creation
  // =========================================================================
  it('should create the component instance', () => {
    expect(component).toBeTruthy();
    expect(component.facteurs).toEqual([]);
    expect(component.facteursAffiches).toEqual([]);
    expect(component.chargement).toBe(false);
    expect(component.erreur).toBeNull();
    expect(component.explicationDisponible).toBe(true);
  });

  // =========================================================================
  // 2. Loading state (Requirement 3.1, 6.3)
  // =========================================================================
  describe('Loading state', () => {
    it('should expose chargement=true for spinner display', () => {
      component.chargement = true;
      expect(component.chargement).toBe(true);
    });

    it('should not process facteurs when chargement is active (no facteursAffiches)', () => {
      component.chargement = true;
      component.facteurs = [];
      component.ngOnChanges();
      expect(component.facteursAffiches).toEqual([]);
    });
  });

  // =========================================================================
  // 3. Error state (Requirement 3.7, 7.2)
  // =========================================================================
  describe('Error state', () => {
    it('should expose the error message for display', () => {
      component.erreur = 'Impossible de charger l\'explication';
      expect(component.erreur).toBe('Impossible de charger l\'explication');
    });

    it('should emit reessayer event when onReessayer is called', () => {
      spyOn(component.reessayer, 'emit');
      component.onReessayer();
      expect(component.reessayer.emit).toHaveBeenCalledTimes(1);
    });
  });

  // =========================================================================
  // 4. Unavailable state (Requirement 3.7)
  // =========================================================================
  describe('Unavailable state', () => {
    it('should expose explicationDisponible=false for "non disponible" message', () => {
      component.explicationDisponible = false;
      expect(component.explicationDisponible).toBe(false);
    });

    it('should not generate facteursAffiches when facteurs is empty and not available', () => {
      component.explicationDisponible = false;
      component.facteurs = [];
      component.ngOnChanges();
      expect(component.facteursAffiches).toEqual([]);
    });
  });

  // =========================================================================
  // 5. Bar rendering: couleurs and directions (Requirement 3.1, 3.2, 3.3)
  // =========================================================================
  describe('Bar rendering - couleurs and directions', () => {
    const mockFacteurs: FacteurExplicatif[] = [
      { nom_variable: 'ratio_rachats_primes', shap_value: 0.5, valeur_contrat: 0.8, moyenne_portefeuille: 0.3 },
      { nom_variable: 'nb_avt_risque_eleve', shap_value: -0.3, valeur_contrat: 1, moyenne_portefeuille: 2.5 },
      { nom_variable: 'total_rachats', shap_value: 0.2, valeur_contrat: 20000, moyenne_portefeuille: 15000 }
    ];

    beforeEach(() => {
      component.facteurs = mockFacteurs;
      component.ngOnChanges();
    });

    it('should generate facteursAffiches for each input facteur', () => {
      expect(component.facteursAffiches.length).toBe(3);
    });

    it('should assign couleurBarre=rouge and directionBarre=droite for positive shap_value', () => {
      const positiveFacteur = component.facteursAffiches[0]; // shap_value = 0.5
      expect(positiveFacteur.couleurBarre).toBe('rouge');
      expect(positiveFacteur.directionBarre).toBe('droite');
    });

    it('should assign couleurBarre=vert and directionBarre=gauche for negative shap_value', () => {
      const negativeFacteur = component.facteursAffiches[1]; // shap_value = -0.3
      expect(negativeFacteur.couleurBarre).toBe('vert');
      expect(negativeFacteur.directionBarre).toBe('gauche');
    });

    it('should apply barre-rouge/direction-droite for all positive values', () => {
      const positiveFacteurs = component.facteursAffiches.filter(f => f.couleurBarre === 'rouge');
      positiveFacteurs.forEach(f => {
        expect(f.directionBarre).toBe('droite');
      });
    });

    it('should assign correct libellés from dictionnaire', () => {
      expect(component.facteursAffiches[0].libelle).toBe('Ratio rachats/primes');
      expect(component.facteursAffiches[1].libelle).toBe('Nb avenants risque élevé');
      expect(component.facteursAffiches[2].libelle).toBe('Total rachats');
    });
  });

  // =========================================================================
  // 6. Proportional widths (Requirement 3.1)
  // =========================================================================
  describe('Proportional widths', () => {
    it('should set bar widths proportional to |shap_value| relative to the max', () => {
      component.facteurs = [
        { nom_variable: 'var_a', shap_value: 1.0, valeur_contrat: 10, moyenne_portefeuille: 5 },
        { nom_variable: 'var_b', shap_value: -0.5, valeur_contrat: 3, moyenne_portefeuille: 4 },
        { nom_variable: 'var_c', shap_value: 0.25, valeur_contrat: 7, moyenne_portefeuille: 6 }
      ];
      component.ngOnChanges();

      // Max |shap_value| = 1.0
      // var_a: |1.0| / 1.0 * 100 = 100%
      // var_b: |0.5| / 1.0 * 100 = 50%
      // var_c: |0.25| / 1.0 * 100 = 25%
      expect(component.facteursAffiches[0].largeurBarre).toBe(100);
      expect(component.facteursAffiches[1].largeurBarre).toBe(50);
      expect(component.facteursAffiches[2].largeurBarre).toBe(25);
    });

    it('should handle all zero shap_values gracefully (width=0)', () => {
      component.facteurs = [
        { nom_variable: 'var_a', shap_value: 0, valeur_contrat: 10, moyenne_portefeuille: 5 }
      ];
      component.ngOnChanges();

      expect(component.facteursAffiches[0].largeurBarre).toBe(0);
    });

    it('should handle single facteur (width=100%)', () => {
      component.facteurs = [
        { nom_variable: 'var_a', shap_value: 0.3, valeur_contrat: 10, moyenne_portefeuille: 5 }
      ];
      component.ngOnChanges();

      expect(component.facteursAffiches[0].largeurBarre).toBe(100);
    });

    it('should produce widths between 0 and 100 inclusive', () => {
      component.facteurs = [
        { nom_variable: 'var_a', shap_value: 0.8, valeur_contrat: 10, moyenne_portefeuille: 5 },
        { nom_variable: 'var_b', shap_value: -0.4, valeur_contrat: 3, moyenne_portefeuille: 4 },
        { nom_variable: 'var_c', shap_value: 0.1, valeur_contrat: 7, moyenne_portefeuille: 6 }
      ];
      component.ngOnChanges();

      component.facteursAffiches.forEach(f => {
        expect(f.largeurBarre).toBeGreaterThanOrEqual(0);
        expect(f.largeurBarre).toBeLessThanOrEqual(100);
      });
    });
  });

  // =========================================================================
  // 7. Comparative table data (Requirement 3.4)
  // =========================================================================
  describe('Comparative table', () => {
    it('should include variable name (libelle), contract value, and portfolio average in facteursAffiches', () => {
      component.facteurs = [
        { nom_variable: 'ratio_rachats_primes', shap_value: 0.5, valeur_contrat: 0.8, moyenne_portefeuille: 0.3 },
        { nom_variable: 'duree_annees', shap_value: -0.2, valeur_contrat: 3, moyenne_portefeuille: 8.2 }
      ];
      component.moyennes = {
        moyennes: { ratio_rachats_primes: 0.3, duree_annees: 8.2 },
        nombre_contrats: 1000,
        date_calcul: '2024-01-01',
        cache_valide_jusqu_a: '2024-01-02'
      };
      component.ngOnChanges();

      expect(component.facteursAffiches[0].libelle).toBe('Ratio rachats/primes');
      expect(component.facteursAffiches[0].valeur_contrat).toBe(0.8);
      expect(component.facteursAffiches[0].moyenne_portefeuille).toBe(0.3);

      expect(component.facteursAffiches[1].libelle).toBe('Durée (années)');
      expect(component.facteursAffiches[1].valeur_contrat).toBe(3);
      expect(component.facteursAffiches[1].moyenne_portefeuille).toBe(8.2);
    });

    it('should expose moyennes=null for "Comparaison non disponible" display', () => {
      component.moyennes = null;
      expect(component.moyennes).toBeNull();
    });
  });

  // =========================================================================
  // 8. Retry button emits reessayer event (Requirement 7.2)
  // =========================================================================
  describe('Retry button (reessayer event)', () => {
    it('should emit reessayer event via onReessayer()', () => {
      spyOn(component.reessayer, 'emit');
      component.onReessayer();
      expect(component.reessayer.emit).toHaveBeenCalledTimes(1);
    });

    it('should not emit any value (void event)', () => {
      spyOn(component.reessayer, 'emit');
      component.onReessayer();
      expect(component.reessayer.emit).toHaveBeenCalledWith();
    });
  });

  // =========================================================================
  // 9. Indicators (Requirement 3.5, 3.6)
  // =========================================================================
  describe('Indicators', () => {
    it('should return fleche-rouge-haut when shap > 0 and valeur > moyenne', () => {
      const facteur: FacteurExplicatif = {
        nom_variable: 'ratio_rachats_primes',
        shap_value: 0.5,
        valeur_contrat: 0.8,
        moyenne_portefeuille: 0.3
      };
      expect(component.getIndicateur(facteur)).toBe('fleche-rouge-haut');
    });

    it('should return fleche-verte-bas when shap > 0 and valeur < moyenne', () => {
      const facteur: FacteurExplicatif = {
        nom_variable: 'nb_avt_risque_eleve',
        shap_value: 0.4,
        valeur_contrat: 1,
        moyenne_portefeuille: 2.5
      };
      expect(component.getIndicateur(facteur)).toBe('fleche-verte-bas');
    });

    it('should return null when shap <= 0 (no indicator for negative contribution)', () => {
      const facteur: FacteurExplicatif = {
        nom_variable: 'duree_annees',
        shap_value: -0.3,
        valeur_contrat: 12,
        moyenne_portefeuille: 8
      };
      expect(component.getIndicateur(facteur)).toBeNull();
    });

    it('should return null when shap > 0 but valeur equals moyenne', () => {
      const facteur: FacteurExplicatif = {
        nom_variable: 'var_a',
        shap_value: 0.5,
        valeur_contrat: 5.0,
        moyenne_portefeuille: 5.0
      };
      expect(component.getIndicateur(facteur)).toBeNull();
    });

    it('should return null when shap = 0 (zero contribution)', () => {
      const facteur: FacteurExplicatif = {
        nom_variable: 'var_a',
        shap_value: 0,
        valeur_contrat: 10,
        moyenne_portefeuille: 5
      };
      expect(component.getIndicateur(facteur)).toBeNull();
    });

    it('should set correct indicators in facteursAffiches via ngOnChanges', () => {
      component.facteurs = [
        { nom_variable: 'var_a', shap_value: 0.5, valeur_contrat: 10, moyenne_portefeuille: 5 },   // fleche-rouge-haut
        { nom_variable: 'var_b', shap_value: 0.3, valeur_contrat: 2, moyenne_portefeuille: 8 },    // fleche-verte-bas
        { nom_variable: 'var_c', shap_value: -0.4, valeur_contrat: 12, moyenne_portefeuille: 8 },  // null
        { nom_variable: 'var_d', shap_value: 0.2, valeur_contrat: 5, moyenne_portefeuille: 5 }     // null (equal)
      ];
      component.ngOnChanges();

      expect(component.facteursAffiches[0].indicateur).toBe('fleche-rouge-haut');
      expect(component.facteursAffiches[1].indicateur).toBe('fleche-verte-bas');
      expect(component.facteursAffiches[2].indicateur).toBeNull();
      expect(component.facteursAffiches[3].indicateur).toBeNull();
    });
  });

  // =========================================================================
  // Edge cases
  // =========================================================================
  describe('Edge cases', () => {
    it('should clear facteursAffiches when facteurs is empty', () => {
      component.facteurs = [
        { nom_variable: 'var_a', shap_value: 0.5, valeur_contrat: 10, moyenne_portefeuille: 5 }
      ];
      component.ngOnChanges();
      expect(component.facteursAffiches.length).toBe(1);

      // Now set to empty
      component.facteurs = [];
      component.ngOnChanges();
      expect(component.facteursAffiches).toEqual([]);
    });

    it('should use fallback libelle for unknown variable names', () => {
      component.facteurs = [
        { nom_variable: 'some_unknown_var', shap_value: 0.3, valeur_contrat: 5, moyenne_portefeuille: 3 }
      ];
      component.ngOnChanges();

      // Fallback: replace _ with spaces, capitalize first letter
      expect(component.facteursAffiches[0].libelle).toBe('Some unknown var');
    });
  });
});
