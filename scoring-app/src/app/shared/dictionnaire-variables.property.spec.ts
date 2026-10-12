import * as fc from 'fast-check';
import { DICTIONNAIRE_VARIABLES, getLibelleVariable } from './dictionnaire-variables';

/**
 * Property 7: Correspondance dictionnaire des noms de variables
 *
 * For any nom de variable technique présent dans le dictionnaire de correspondance,
 * la fonction getLibelleVariable SHALL retourner le libellé français correspondant
 * défini dans le dictionnaire.
 *
 * **Validates: Requirements 5.1, 5.2**
 *
 * Tag: Feature: scoring-explicabilite, Property 7: Correspondance dictionnaire des noms de variables
 */
describe('Property 7: Correspondance dictionnaire des noms de variables', () => {
  const dictionaryKeys = Object.keys(DICTIONNAIRE_VARIABLES);

  it('getLibelleVariable retourne le libellé français correspondant pour toute clé du dictionnaire', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...dictionaryKeys),
        (nomTechnique: string) => {
          const result = getLibelleVariable(nomTechnique);
          expect(result).toBe(DICTIONNAIRE_VARIABLES[nomTechnique]);
        }
      ),
      { numRuns: 100 }
    );
  });
});
