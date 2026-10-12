import * as fc from 'fast-check';
import { DICTIONNAIRE_VARIABLES, getLibelleVariable } from './dictionnaire-variables';

/**
 * Property 8: Formatage fallback des noms inconnus
 *
 * For any nom de variable technique absent du dictionnaire, la fonction
 * getLibelleVariable SHALL retourner une chaîne où les underscores sont
 * remplacés par des espaces et le premier caractère est en majuscule.
 *
 * **Validates: Requirements 5.3**
 */
describe('Property 8: Formatage fallback des noms inconnus', () => {
  const chars = 'abcdefghijklmnopqrstuvwxyz_'.split('');

  // Strategy: Generate random snake_case strings NOT in the dictionary
  // Uses fc.array of characters from [a-z_], joined into a string
  const snakeCaseArbitrary = fc
    .array(fc.constantFrom(...chars), { minLength: 1, maxLength: 30 })
    .map((arr: string[]) => arr.join(''))
    .filter((s: string) => {
      // Must not be a key in the dictionary
      return !(s in DICTIONNAIRE_VARIABLES);
    })
    .filter((s: string) => {
      // Must have at least one alphabetic character
      return /[a-z]/.test(s);
    });

  it('should replace all underscores with spaces', () => {
    fc.assert(
      fc.property(snakeCaseArbitrary, (input: string) => {
        const result = getLibelleVariable(input);
        expect(result).not.toContain('_');
      }),
      { numRuns: 100 }
    );
  });

  it('should capitalize the first character', () => {
    fc.assert(
      fc.property(snakeCaseArbitrary, (input: string) => {
        const result = getLibelleVariable(input);
        if (result.length > 0) {
          expect(result[0]).toBe(result[0].toUpperCase());
        }
      }),
      { numRuns: 100 }
    );
  });

  it('should equal the expected fallback transformation', () => {
    fc.assert(
      fc.property(snakeCaseArbitrary, (input: string) => {
        const result = getLibelleVariable(input);
        const expected = input
          .replace(/_/g, ' ')
          .replace(/^./, (c: string) => c.toUpperCase());
        expect(result).toBe(expected);
      }),
      { numRuns: 100 }
    );
  });
});
