import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NiveauRisque } from '../../models';

@Component({
  selector: 'app-niveau-badge',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span class="badge" [ngClass]="getBadgeClass()">
      {{ niveau }}
    </span>
  `,
  styles: [`
    .badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 16px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }

    .badge-critique {
      background-color: #f44336;
      color: white;
    }

    .badge-eleve {
      background-color: #ff9800;
      color: white;
    }

    .badge-moyen {
      background-color: #ffeb3b;
      color: rgba(0, 0, 0, 0.87);
    }

    .badge-faible {
      background-color: #4caf50;
      color: white;
    }
  `]
})
export class NiveauBadgeComponent {
  @Input() niveau: NiveauRisque = 'FAIBLE';

  getBadgeClass(): string {
    switch (this.niveau) {
      case 'CRITIQUE': return 'badge-critique';
      case 'ÉLEVÉ': return 'badge-eleve';
      case 'MOYEN': return 'badge-moyen';
      case 'FAIBLE': return 'badge-faible';
      default: return 'badge-faible';
    }
  }
}
