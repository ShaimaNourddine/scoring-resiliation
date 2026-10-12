import { Component, Input } from '@angular/core';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-jauge-score',
  standalone: true,
  imports: [CommonModule, MatProgressBarModule],
  template: `
    <div class="jauge-container">
      <mat-progress-bar
        mode="determinate"
        [value]="score * 100"
        [class]="getBarClass()">
      </mat-progress-bar>
      <span class="score-label">{{ (score * 100).toFixed(1) }}%</span>
    </div>
  `,
  styles: [`
    .jauge-container {
      display: flex;
      align-items: center;
      gap: 12px;
      width: 100%;
    }

    mat-progress-bar {
      flex: 1;
      height: 8px;
      border-radius: 4px;
    }

    .score-label {
      font-weight: 500;
      font-size: 14px;
      min-width: 50px;
      text-align: right;
    }

    .bar-critique ::ng-deep .mdc-linear-progress__bar-inner {
      border-color: #f44336;
    }

    .bar-eleve ::ng-deep .mdc-linear-progress__bar-inner {
      border-color: #ff9800;
    }

    .bar-moyen ::ng-deep .mdc-linear-progress__bar-inner {
      border-color: #ffeb3b;
    }

    .bar-faible ::ng-deep .mdc-linear-progress__bar-inner {
      border-color: #4caf50;
    }
  `]
})
export class JaugeScoreComponent {
  @Input() score: number = 0;

  getBarClass(): string {
    if (this.score >= 0.75) return 'bar-critique';
    if (this.score >= 0.50) return 'bar-eleve';
    if (this.score >= 0.25) return 'bar-moyen';
    return 'bar-faible';
  }
}
