import '@angular/compiler';
import { DashboardComponent } from './dashboard.component';
import { of, throwError, Subject } from 'rxjs';
import { FacteurExplicatif, ExplicationContrat, MoyennesPortefeuille } from '../../models/explicabilite.model';

/**
 * Unit tests for DashboardComponent - Accordion behavior
 *
 * Tests the accordion panel logic for the top 10 table:
 * - Only one panel open at a time
 * - Toggle open/close on click
 * - Loading state and data clearing on panel switch
 *
 * Validates: Requirements 4.4, 4.5
 */
describe('DashboardComponent - Accordion behavior', () => {
  let component: DashboardComponent;
  let mockExplicabiliteService: any;
  let mockScoringService: any;
  let mockRouter: any;

  const mockExplication: ExplicationContrat = {
    contrat_id: 'CTR-001',
    facteurs_explicatifs: [
      { nom_variable: 'ratio_rachats_primes', shap_value: 0.5, valeur_contrat: 0.8, moyenne_portefeuille: 0.3 }
    ],
    explication_disponible: true,
    timestamp: '2024-01-01T00:00:00Z'
  };

  const mockMoyennes: MoyennesPortefeuille = {
    moyennes: { ratio_rachats_primes: 0.3 },
    nombre_contrats: 1000,
    date_calcul: '2024-01-01',
    cache_valide_jusqu_a: '2024-01-02'
  };

  beforeEach(() => {
    mockExplicabiliteService = {
      getExplicationContrat: jasmine.createSpy('getExplicationContrat').and.returnValue(of(mockExplication)),
      getMoyennesPortefeuille: jasmine.createSpy('getMoyennesPortefeuille').and.returnValue(of(mockMoyennes))
    };

    mockScoringService = {
      getStatistiques: jasmine.createSpy('getStatistiques').and.returnValue(of(null))
    };

    mockRouter = {
      navigate: jasmine.createSpy('navigate')
    };

    component = new DashboardComponent(
      mockScoringService as any,
      mockExplicabiliteService as any,
      mockRouter as any
    );
  });

  // =========================================================================
  // 1. Initial state: panneauOuvertId should be null
  // =========================================================================
  describe('Initial state', () => {
    it('should have panneauOuvertId = null (no panel open)', () => {
      expect(component.panneauOuvertId).toBeNull();
    });

    it('should have chargementAccordion = false initially', () => {
      expect(component.chargementAccordion).toBe(false);
    });

    it('should have facteursAccordion as empty array initially', () => {
      expect(component.facteursAccordion).toEqual([]);
    });

    it('should have erreurAccordion = null initially', () => {
      expect(component.erreurAccordion).toBeNull();
    });
  });

  // =========================================================================
  // 2. Open a panel: togglePanneau('CTR-001') opens it
  // =========================================================================
  describe('Open a panel', () => {
    it('should set panneauOuvertId to the clicked contrat ID', () => {
      component.togglePanneau('CTR-001');
      expect(component.panneauOuvertId).toBe('CTR-001');
    });

    it('should set chargementAccordion = true before the service response arrives', () => {
      // Use a Subject to delay the response and observe intermediate state
      const subject = new Subject<ExplicationContrat>();
      mockExplicabiliteService.getExplicationContrat.and.returnValue(subject.asObservable());

      component.togglePanneau('CTR-001');
      // Before the observable emits, chargementAccordion should be true
      expect(component.chargementAccordion).toBe(true);

      // After the response arrives, it becomes false
      subject.next(mockExplication);
      expect(component.chargementAccordion).toBe(false);
    });

    it('should call explicabiliteService.getExplicationContrat with the contrat ID', () => {
      component.togglePanneau('CTR-001');
      expect(mockExplicabiliteService.getExplicationContrat).toHaveBeenCalledWith('CTR-001');
    });

    it('should call explicabiliteService.getMoyennesPortefeuille when opening', () => {
      component.togglePanneau('CTR-001');
      expect(mockExplicabiliteService.getMoyennesPortefeuille).toHaveBeenCalled();
    });

    it('should populate facteursAccordion after data loads', () => {
      component.togglePanneau('CTR-001');
      expect(component.facteursAccordion).toEqual(mockExplication.facteurs_explicatifs);
    });
  });

  // =========================================================================
  // 3. Close by clicking same: togglePanneau('CTR-001') again closes it
  // =========================================================================
  describe('Close by clicking same panel', () => {
    it('should set panneauOuvertId = null when clicking the same contrat', () => {
      component.togglePanneau('CTR-001');
      expect(component.panneauOuvertId).toBe('CTR-001');

      component.togglePanneau('CTR-001');
      expect(component.panneauOuvertId).toBeNull();
    });

    it('should not call explicabiliteService when closing a panel', () => {
      component.togglePanneau('CTR-001');
      // Reset call counts after opening
      mockExplicabiliteService.getExplicationContrat.calls.reset();
      mockExplicabiliteService.getMoyennesPortefeuille.calls.reset();

      component.togglePanneau('CTR-001');
      expect(mockExplicabiliteService.getExplicationContrat).not.toHaveBeenCalled();
      expect(mockExplicabiliteService.getMoyennesPortefeuille).not.toHaveBeenCalled();
    });
  });

  // =========================================================================
  // 4. Only one open at a time: opening another closes the first
  // =========================================================================
  describe('Only one panel open at a time (Requirement 4.4)', () => {
    it('should switch panneauOuvertId to the new contrat when clicking another', () => {
      component.togglePanneau('CTR-001');
      expect(component.panneauOuvertId).toBe('CTR-001');

      component.togglePanneau('CTR-002');
      expect(component.panneauOuvertId).toBe('CTR-002');
    });

    it('should clear facteursAccordion when switching to a new panel (before response)', () => {
      // Use a Subject to observe the intermediate cleared state
      const subject = new Subject<ExplicationContrat>();

      // Open first panel with synchronous response
      mockExplicabiliteService.getExplicationContrat.and.returnValue(of(mockExplication));
      component.togglePanneau('CTR-001');
      expect(component.facteursAccordion.length).toBeGreaterThan(0);

      // Now open another panel with delayed response
      mockExplicabiliteService.getExplicationContrat.and.returnValue(subject.asObservable());
      component.togglePanneau('CTR-002');
      // Before the new response arrives, facteursAccordion should be cleared
      expect(component.facteursAccordion).toEqual([]);
    });

    it('should set chargementAccordion = true when switching panels (before response)', () => {
      // Use a Subject for the second call to see intermediate state
      const subject = new Subject<ExplicationContrat>();

      component.togglePanneau('CTR-001'); // completes synchronously
      expect(component.chargementAccordion).toBe(false); // already completed

      mockExplicabiliteService.getExplicationContrat.and.returnValue(subject.asObservable());
      component.togglePanneau('CTR-002');
      expect(component.chargementAccordion).toBe(true);
    });

    it('should call getExplicationContrat with the new contrat ID', () => {
      component.togglePanneau('CTR-001');
      component.togglePanneau('CTR-002');
      expect(mockExplicabiliteService.getExplicationContrat).toHaveBeenCalledWith('CTR-002');
    });
  });

  // =========================================================================
  // 5. Open, open another, close: full sequence
  // =========================================================================
  describe('Full interaction sequence (Requirement 4.5)', () => {
    it('CTR-001 → CTR-002 → CTR-002 → panneauOuvertId = null', () => {
      component.togglePanneau('CTR-001');
      expect(component.panneauOuvertId).toBe('CTR-001');

      component.togglePanneau('CTR-002');
      expect(component.panneauOuvertId).toBe('CTR-002');

      component.togglePanneau('CTR-002');
      expect(component.panneauOuvertId).toBeNull();
    });

    it('should handle rapid toggling of multiple panels correctly', () => {
      component.togglePanneau('CTR-001');
      component.togglePanneau('CTR-002');
      component.togglePanneau('CTR-003');
      expect(component.panneauOuvertId).toBe('CTR-003');

      component.togglePanneau('CTR-003');
      expect(component.panneauOuvertId).toBeNull();
    });

    it('should handle re-opening a previously closed panel', () => {
      component.togglePanneau('CTR-001');
      component.togglePanneau('CTR-001'); // close
      expect(component.panneauOuvertId).toBeNull();

      component.togglePanneau('CTR-001'); // re-open
      expect(component.panneauOuvertId).toBe('CTR-001');
    });
  });

  // =========================================================================
  // 6. Loading and data state transitions
  // =========================================================================
  describe('Loading and data state transitions', () => {
    it('should set chargementAccordion to true before response arrives', () => {
      const subject = new Subject<ExplicationContrat>();
      mockExplicabiliteService.getExplicationContrat.and.returnValue(subject.asObservable());

      component.togglePanneau('CTR-001');
      expect(component.chargementAccordion).toBe(true);
    });

    it('should clear erreurAccordion when opening a new panel', () => {
      component.erreurAccordion = 'Previous error';
      component.togglePanneau('CTR-001');
      expect(component.erreurAccordion).toBeNull();
    });

    it('should set explicationAccordionDisponible to true when opening', () => {
      component.explicationAccordionDisponible = false;
      component.togglePanneau('CTR-001');
      expect(component.explicationAccordionDisponible).toBe(true);
    });

    it('should handle service error gracefully', () => {
      mockExplicabiliteService.getExplicationContrat.and.returnValue(
        throwError(() => ({ message: 'Service error' }))
      );

      component.togglePanneau('CTR-001');
      expect(component.panneauOuvertId).toBe('CTR-001');
      expect(component.erreurAccordion).toBe('Service error');
      expect(component.chargementAccordion).toBe(false);
    });
  });
});
