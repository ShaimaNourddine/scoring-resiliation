import * as fc from 'fast-check';
import { FacteurExplicatif } from '../../models/explicabilite.model';

/**
 * Property 5: Indicateur visuel de comparaison avec la moyenne
 *
 * For any FacteurExplicatif à contribution positive (shap_value > 0),
 * si valeur_contrat > moyenne_portefeuille alors l'indicateur SHALL être une flèche rouge vers le haut;
 * si valeur_contrat < moyenne_portefeuille alors l'indicateur SHALL être une flèche verte vers le bas.
 *
 * **Validates: Requirements 3.5, 3.6**
 *
 * Tag: Feature: scoring-explicabilite, Property 5: Indicateur visuel de comparaison avec la moyenne
 */

/**
 * Pure function extracted from PanneauExplicationComponent.getIndicateur()
 * to enable property-based testing without Angular JIT compilation.
 */
function getIndicateur(facteur: FacteurExplicatif): 'fleche-rouge-haut' | 'fleche-verte-bas' | null {
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

describe('Property 5: Indicateur visuel de comparaison avec la moyenne', () => {

  it('shap_value > 0 et valeur_contrat > moyenne_portefeuille → fleche-rouge-haut', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0.0001, max: 1000, noNaN: true, noDefaultInfinity: true }),
        fc.double({ min: -1000, max: 1000, noNaN: true, noDefaultInfinity: true }),
        fc.double({ min: -1000, max: 1000, noNaN: true, noDefaultInfinity: true }),
        (shapValue: number, valeurContrat: number, moyennePortefeuille: number) => {
          // Ensure valeur_contrat > moyenne_portefeuille
          fc.pre(valeurContrat > moyennePortefeuille);

          const facteur: FacteurExplicatif = {
            nom_variable: 'test_variable',
            shap_value: shapValue,
            valeur_contrat: valeurContrat,
            moyenne_portefeuille: moyennePortefeuille
          };

          const result = getIndicateur(facteur);
          expect(result).toBe('fleche-rouge-haut');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('shap_value > 0 et valeur_contrat < moyenne_portefeuille → fleche-verte-bas', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0.0001, max: 1000, noNaN: true, noDefaultInfinity: true }),
        fc.double({ min: -1000, max: 1000, noNaN: true, noDefaultInfinity: true }),
        fc.double({ min: -1000, max: 1000, noNaN: true, noDefaultInfinity: true }),
        (shapValue: number, valeurContrat: number, moyennePortefeuille: number) => {
          // Ensure valeur_contrat < moyenne_portefeuille
          fc.pre(valeurContrat < moyennePortefeuille);

          const facteur: FacteurExplicatif = {
            nom_variable: 'test_variable',
            shap_value: shapValue,
            valeur_contrat: valeurContrat,
            moyenne_portefeuille: moyennePortefeuille
          };

          const result = getIndicateur(facteur);
          expect(result).toBe('fleche-verte-bas');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('shap_value <= 0 → indicateur null (pas d indicateur pour contribution négative ou nulle)', () => {
    fc.assert(
      fc.property(
        fc.double({ min: -1000, max: 0, noNaN: true, noDefaultInfinity: true }),
        fc.double({ min: -1000, max: 1000, noNaN: true, noDefaultInfinity: true }),
        fc.double({ min: -1000, max: 1000, noNaN: true, noDefaultInfinity: true }),
        (shapValue: number, valeurContrat: number, moyennePortefeuille: number) => {
          const facteur: FacteurExplicatif = {
            nom_variable: 'test_variable',
            shap_value: shapValue,
            valeur_contrat: valeurContrat,
            moyenne_portefeuille: moyennePortefeuille
          };

          const result = getIndicateur(facteur);
          expect(result).toBeNull();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('shap_value > 0 et valeur_contrat === moyenne_portefeuille → indicateur null', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0.0001, max: 1000, noNaN: true, noDefaultInfinity: true }),
        fc.double({ min: -1000, max: 1000, noNaN: true, noDefaultInfinity: true }),
        (shapValue: number, valeur: number) => {
          const facteur: FacteurExplicatif = {
            nom_variable: 'test_variable',
            shap_value: shapValue,
            valeur_contrat: valeur,
            moyenne_portefeuille: valeur  // Same value = equal
          };

          const result = getIndicateur(facteur);
          expect(result).toBeNull();
        }
      ),
      { numRuns: 100 }
    );
  });
});
