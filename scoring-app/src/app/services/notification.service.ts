import { Injectable } from '@angular/core';
import { MatSnackBar, MatSnackBarConfig } from '@angular/material/snack-bar';

@Injectable({
  providedIn: 'root'
})
export class NotificationService {
  private readonly dureeDefaut = 5000;
  private readonly dureeErreur = 8000;

  constructor(private snackBar: MatSnackBar) {}

  afficherErreur(message: string, duree?: number): void {
    const config: MatSnackBarConfig = {
      duration: duree ?? this.dureeErreur,
      horizontalPosition: 'center',
      verticalPosition: 'bottom',
      panelClass: ['snackbar-erreur']
    };
    this.snackBar.open(message, 'Fermer', config);
  }

  afficherSucces(message: string, duree?: number): void {
    const config: MatSnackBarConfig = {
      duration: duree ?? this.dureeDefaut,
      horizontalPosition: 'center',
      verticalPosition: 'bottom',
      panelClass: ['snackbar-succes']
    };
    this.snackBar.open(message, 'Fermer', config);
  }

  afficherInfo(message: string, duree?: number): void {
    const config: MatSnackBarConfig = {
      duration: duree ?? this.dureeDefaut,
      horizontalPosition: 'center',
      verticalPosition: 'bottom',
      panelClass: ['snackbar-info']
    };
    this.snackBar.open(message, 'OK', config);
  }
}
