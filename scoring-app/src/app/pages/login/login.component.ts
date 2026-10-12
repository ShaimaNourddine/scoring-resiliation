import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { finalize } from 'rxjs/operators';

import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss'
})
export class LoginComponent {
  email = '';
  password = '';
  afficherMotDePasse = false;
  chargement = false;
  erreur: string | null = null;

  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  seConnecter(): void {
    if (!this.email.trim() || !this.password.trim() || this.chargement) {
      return;
    }

    this.chargement = true;
    this.erreur = null;

    this.authService.login(this.email.trim(), this.password)
      .pipe(finalize(() => this.chargement = false))
      .subscribe({
        next: () => {
          this.router.navigate(['/scoring']);
        },
        error: (err) => {
          this.erreur = err.message || 'Erreur de connexion';
        }
      });
  }
}
