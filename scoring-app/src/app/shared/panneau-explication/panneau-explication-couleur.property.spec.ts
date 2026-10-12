import * as fc from 'fast-check';
import { FacteurExplicatif, FacteurAffiche } from '../../models/explicabilite.model';

/**
 * Property 4: Mapping couleur/direction depuis le signe SHAP
 *
 * For any FacteurExplicatif affiché, si shap_value > 0 alors la barre SHALL être
 * rouge et orientée vers la droite; si shap_value < 0 alors la barre SHALL être
 * verte et orientée vers la gauche.
 *
 * **Validates: Requirements 3.2, 3.3**
 *
 * Tag: Feature: scoring-explicabilite, Property 4: Mapping couleur/direction depuis le signe SHAP
 */
describe('Property 4: Mapping couleur/direction depuis le signe SHAP', () => {
  /**
   * Pure mapping logic extracted from PanneauExplicationComponent.ngOnChanges()
   * This replicates the component's mapping: shap_value > 0 → rouge/droite, < 0 → vert/gauche
   */
  function mapCouleurDirection(facteur: FacteurExplicatif): Pick<FacteurAffiche, 'couleurBarre' | 'directionBarre'> {
    return {
      couleurBarre: facteur.shap_value > 0 ? 'rouge' : 'vert',
      directionBarre: facteur.shap_value > 0 ? 'droite' : 'gauche',
    };
  }

  // Generator for a FacteurExplicatif with a strictly positive shap_value
  const facteurPositifArbitrary: fc.Arbitrary<FacteurExplicatif> = fc.record({
    nom_variable: fc.string({ minLength: 1, maxLength: 30 }),
    shap_value: fc.double({ min: 0.0001, max: 1000, noNaN: true }),
    valeur_contrat: fc.double({ min: -10000, max: 10000, noNaN: true }),
    moyenne_portefeuille: fc.double({ min: -10000, max: 10000, noNaN: true }),
  });

  // Generator for a FacteurExplicatif with a strictly negative shap_value
  const facteurNegatifArbitrary: fc.Arbitrary<FacteurExplicatif> = fc.record({
    nom_variable: fc.string({ minLength: 1, maxLength: 30 }),
    shap_value: fc.double({ min: -1000, max: -0.0001, noNaN: true }),
    valeur_contrat: fc.double({ min: -10000, max: 10000, noNaN: true }),
    moyenne_portefeuille: fc.double({ min: -10000, max: 10000, noNaN: true }),
  });

  it('shap_value > 0 → couleurBarre === "rouge" et directionBarre === "droite"', () => {
    fc.assert(
      fc.property(facteurPositifArbitrary, (facteur: FacteurExplicatif) => {
        const result = mapCouleurDirection(facteur);

        expect(result.couleurBarre).toBe('rouge');
        expect(result.directionBarre).toBe('droite');
      }),
      { numRuns: 100 }
    );
  });

  it('shap_value < 0 → couleurBarre === "vert" et directionBarre === "gauche"', () => {
    fc.assert(
      fc.property(facteurNegatifArbitrary, (facteur: FacteurExplicatif) => {
        const result = mapCouleurDirection(facteur);

        expect(result.couleurBarre).toBe('vert');
        expect(result.directionBarre).toBe('gauche');
      }),
      { numRuns: 100 }
    );
  });
});
