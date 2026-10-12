import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCardModule } from '@angular/material/card';
import { ScoringService } from '../../services/scoring.service';
import { finalize } from 'rxjs/operators';

@Component({
  selector: 'app-batch',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule, MatCardModule],
  templateUrl: './batch.component.html',
  styleUrl: './batch.component.scss'
})
export class BatchComponent {
  chargement = false;
  resultat: any = null;
  erreur: string | null = null;

  constructor(private scoringService: ScoringService) {}

  lancerBatch(): void {
    this.chargement = true;
    this.erreur = null;
    this.resultat = null;

    this.scoringService.lancerBatch()
      .pipe(finalize(() => this.chargement = false))
      .subscribe({
        next: (res) => this.resultat = res,
        error: (err) => this.erreur = err.message || 'Erreur lors du scoring batch'
      });
  }
}
