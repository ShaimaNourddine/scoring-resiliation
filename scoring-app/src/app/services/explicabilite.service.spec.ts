import '@angular/compiler';
import { of, throwError } from 'rxjs';
import { HttpErrorResponse } from '@angular/common/http';

import { ExplicabiliteService } from './explicabilite.service';
import { ExplicationContrat, MoyennesPortefeuille } from '../models/explicabilite.model';
import { environment } from '../../environments/environment';

/**
 * Unit tests for ExplicabiliteService
 *
 * Tests HTTP calls, caching behavior, and error handling
 * without Angular TestBed (Jasmine environment without Zone.js).
 *
 * Validates: Requirements 1.4, 2.1, 7.2, 7.3
 */
describe('ExplicabiliteService', () => {
  let service: ExplicabiliteService;
  let mockHttpClient: any;

  const apiUrl = environment.apiUrl;

  beforeEach(() => {
    mockHttpClient = {
      get: jasmine.createSpy('get')
    };
    // Instantiate service directly with mock HttpClient
    service = new ExplicabiliteService(mockHttpClient);
  });

  // =========================================================================
  // getExplicationContrat()
  // =========================================================================
  describe('getExplicationContrat()', () => {

    const mockExplication: ExplicationContrat = {
      contrat_id: 'CTR-12345',
      facteurs_explicatifs: [
        { nom_variable: 'ratio_rachats_primes', shap_value: 0.35, valeur_contrat: 0.8, moyenne_portefeuille: 0.3 },
        { nom_variable: 'nb_avt_risque_eleve', shap_value: -0.2, valeur_contrat: 1, moyenne_portefeuille: 2.5 }
      ],
      explication_disponible: true,
      timestamp: '2024-01-15T10:30:00Z'
    };

    it('should call the correct URL with the contrat ID', () => {
      const contratId = 'CTR-12345';
      mockHttpClient.get.and.returnValue(of(mockExplication));

      service.getExplicationContrat(contratId).subscribe();

      expect(mockHttpClient.get).toHaveBeenCalledWith(
        `${apiUrl}/scoring/contrat/${contratId}/explication`
      );
    });

    it('should return the explication response correctly', () => {
      const contratId = 'CTR-12345';
      mockHttpClient.get.and.returnValue(of(mockExplication));

      service.getExplicationContrat(contratId).subscribe(result => {
        expect(result).toEqual(mockExplication);
        expect(result.contrat_id).toBe('CTR-12345');
        expect(result.facteurs_explicatifs.length).toBe(2);
        expect(result.explication_disponible).toBe(true);
      });
    });

    it('should propagate errors for retry button UI (Req 7.2)', () => {
      const contratId = 'CTR-99999';
      const errorResponse = new HttpErrorResponse({
        status: 500,
        statusText: 'Internal Server Error'
      });
      mockHttpClient.get.and.returnValue(throwError(() => errorResponse));

      service.getExplicationContrat(contratId).subscribe({
        next: () => { throw new Error('should have failed'); },
        error: (error) => {
          expect(error.message).toBeDefined();
          expect(error.status).toBe(500);
        }
      });
    });
  });

  // =========================================================================
  // getMoyennesPortefeuille()
  // =========================================================================
  describe('getMoyennesPortefeuille()', () => {

    const mockMoyennes: MoyennesPortefeuille = {
      moyennes: {
        ratio_rachats_primes: 0.3,
        nb_avt_risque_eleve: 2.5,
        total_rachats: 15000,
        duree_annees: 8.2
      },
      nombre_contrats: 12500,
      date_calcul: '2024-01-15T00:00:00Z',
      cache_valide_jusqu_a: '2024-01-16T00:00:00Z'
    };

    it('should call the correct URL', () => {
      mockHttpClient.get.and.returnValue(of(mockMoyennes));

      service.getMoyennesPortefeuille().subscribe();

      expect(mockHttpClient.get).toHaveBeenCalledWith(
        `${apiUrl}/portefeuille/moyennes`
      );
    });

    it('should return the moyennes response correctly', () => {
      mockHttpClient.get.and.returnValue(of(mockMoyennes));

      service.getMoyennesPortefeuille().subscribe(result => {
        expect(result).toEqual(mockMoyennes);
        expect(result.nombre_contrats).toBe(12500);
        expect(result.moyennes['ratio_rachats_primes']).toBe(0.3);
      });
    });

    it('should use shareReplay cache - multiple subscriptions trigger only 1 HTTP call', () => {
      mockHttpClient.get.and.returnValue(of(mockMoyennes));

      // First subscription
      service.getMoyennesPortefeuille().subscribe(result => {
        expect(result).toEqual(mockMoyennes);
      });

      // Second subscription (should reuse cached observable)
      service.getMoyennesPortefeuille().subscribe(result => {
        expect(result).toEqual(mockMoyennes);
      });

      // Only one HTTP call should have been made
      expect(mockHttpClient.get).toHaveBeenCalledTimes(1);
    });

    it('should propagate errors for "Comparaison non disponible" (Req 7.3)', () => {
      const errorResponse = new HttpErrorResponse({
        status: 503,
        statusText: 'Service Unavailable'
      });
      mockHttpClient.get.and.returnValue(throwError(() => errorResponse));

      service.getMoyennesPortefeuille().subscribe({
        next: () => { throw new Error('should have failed'); },
        error: (error) => {
          expect(error.message).toBeDefined();
          expect(error.status).toBe(503);
        }
      });
    });
  });

  // =========================================================================
  // Error handling (gererErreur)
  // =========================================================================
  describe('Error handling', () => {

    it('should return proper message for 404 error', () => {
      const errorResponse = new HttpErrorResponse({
        status: 404,
        statusText: 'Not Found'
      });
      mockHttpClient.get.and.returnValue(throwError(() => errorResponse));

      service.getExplicationContrat('UNKNOWN').subscribe({
        next: () => { throw new Error('should have failed'); },
        error: (error) => {
          expect(error.message).toBe('Contrat non trouvé ou non scoré');
          expect(error.status).toBe(404);
        }
      });
    });

    it('should return proper message for 503 error', () => {
      const errorResponse = new HttpErrorResponse({
        status: 503,
        statusText: 'Service Unavailable'
      });
      mockHttpClient.get.and.returnValue(throwError(() => errorResponse));

      service.getExplicationContrat('CTR-001').subscribe({
        next: () => { throw new Error('should have failed'); },
        error: (error) => {
          expect(error.message).toBe("Le service d'explicabilité n'est pas disponible.");
          expect(error.status).toBe(503);
        }
      });
    });

    it('should return proper message for network error (status 0)', () => {
      const errorResponse = new HttpErrorResponse({
        status: 0,
        statusText: '',
        error: new ProgressEvent('error')
      });
      mockHttpClient.get.and.returnValue(throwError(() => errorResponse));

      service.getExplicationContrat('CTR-001').subscribe({
        next: () => { throw new Error('should have failed'); },
        error: (error) => {
          expect(error.message).toBe('Service indisponible. Vérifiez que le serveur est démarré.');
          expect(error.status).toBe(0);
        }
      });
    });
  });
});
