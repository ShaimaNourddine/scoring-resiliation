import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { finalize } from 'rxjs/operators';

import { MATERIAL_IMPORTS } from '../../shared/material.imports';
import { AdminUsersService } from '../../services/admin-users.service';
import { AuthService } from '../../services/auth.service';
import { User, Role } from '../../models';

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [CommonModule, FormsModule, ...MATERIAL_IMPORTS],
  templateUrl: './admin-users.component.html',
  styleUrl: './admin-users.component.scss'
})
export class AdminUsersComponent implements OnInit {
  utilisateurs: User[] = [];
  colonnes: string[] = ['nom', 'email', 'role', 'actif', 'actions'];
  chargement = false;
  erreur: string | null = null;

  // Formulaire de création/édition (affiché en ligne, pas de dialog séparé)
  formulaireOuvert = false;
  modeEdition = false;
  utilisateurEnEdition: User | null = null;

  formNom = '';
  formEmail = '';
  formPassword = '';
  formRole: Role = 'GESTIONNAIRE';
  erreurFormulaire: string | null = null;
  enregistrementEnCours = false;

  constructor(
    private adminUsersService: AdminUsersService,
    private authService: AuthService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.chargerUtilisateurs();
  }

  get monPropreId(): number | undefined {
    return this.authService.getCurrentUser()?.user_id;
  }

  chargerUtilisateurs(): void {
    this.chargement = true;
    this.erreur = null;

    this.adminUsersService.lister()
      .pipe(finalize(() => this.chargement = false))
      .subscribe({
        next: (utilisateurs) => this.utilisateurs = utilisateurs,
        error: (err) => this.erreur = err.message || 'Erreur de chargement'
      });
  }

  ouvrirFormulaireCreation(): void {
    this.modeEdition = false;
    this.utilisateurEnEdition = null;
    this.formNom = '';
    this.formEmail = '';
    this.formPassword = '';
    this.formRole = 'GESTIONNAIRE';
    this.erreurFormulaire = null;
    this.formulaireOuvert = true;
  }

  ouvrirFormulaireEdition(utilisateur: User): void {
    this.modeEdition = true;
    this.utilisateurEnEdition = utilisateur;
    this.formNom = utilisateur.nom;
    this.formEmail = utilisateur.email;
    this.formPassword = '';
    this.formRole = utilisateur.role;
    this.erreurFormulaire = null;
    this.formulaireOuvert = true;
  }

  fermerFormulaire(): void {
    this.formulaireOuvert = false;
    this.utilisateurEnEdition = null;
  }

  enregistrer(): void {
    if (this.enregistrementEnCours) {
      return;
    }
    this.erreurFormulaire = null;

    if (this.modeEdition && this.utilisateurEnEdition) {
      this.enregistrerModification();
    } else {
      this.enregistrerCreation();
    }
  }

  private enregistrerCreation(): void {
    if (!this.formNom.trim() || !this.formEmail.trim() || !this.formPassword.trim()) {
      this.erreurFormulaire = 'Tous les champs sont obligatoires.';
      return;
    }

    this.enregistrementEnCours = true;
    this.adminUsersService.creer({
      nom: this.formNom.trim(),
      email: this.formEmail.trim(),
      password: this.formPassword,
      role: this.formRole,
    })
      .pipe(finalize(() => this.enregistrementEnCours = false))
      .subscribe({
        next: () => {
          this.snackBar.open('Utilisateur créé', 'Fermer', { duration: 3000 });
          this.fermerFormulaire();
          this.chargerUtilisateurs();
        },
        error: (err) => this.erreurFormulaire = err.message || 'Erreur lors de la création'
      });
  }

  private enregistrerModification(): void {
    if (!this.utilisateurEnEdition) {
      return;
    }
    if (!this.formNom.trim() || !this.formEmail.trim()) {
      this.erreurFormulaire = 'Le nom et l\'email sont obligatoires.';
      return;
    }

    this.enregistrementEnCours = true;
    const changements: { nom: string; role: Role; password?: string } = {
      nom: this.formNom.trim(),
      role: this.formRole,
    };
    if (this.formPassword.trim()) {
      changements.password = this.formPassword;
    }

    this.adminUsersService.modifier(this.utilisateurEnEdition.user_id, changements)
      .pipe(finalize(() => this.enregistrementEnCours = false))
      .subscribe({
        next: () => {
          this.snackBar.open('Utilisateur modifié', 'Fermer', { duration: 3000 });
          this.fermerFormulaire();
          this.chargerUtilisateurs();
        },
        error: (err) => this.erreurFormulaire = err.message || 'Erreur lors de la modification'
      });
  }

  basculerActivation(utilisateur: User): void {
    if (utilisateur.actif) {
      // Désactivation via l'endpoint DELETE (soft delete)
      this.adminUsersService.desactiver(utilisateur.user_id).subscribe({
        next: () => {
          this.snackBar.open(`${utilisateur.nom} désactivé`, 'Fermer', { duration: 3000 });
          this.chargerUtilisateurs();
        },
        error: (err) => this.afficherErreurGlobale(err.message)
      });
    } else {
      // Réactivation via l'endpoint PUT
      this.adminUsersService.modifier(utilisateur.user_id, { actif: true }).subscribe({
        next: () => {
          this.snackBar.open(`${utilisateur.nom} réactivé`, 'Fermer', { duration: 3000 });
          this.chargerUtilisateurs();
        },
        error: (err) => this.afficherErreurGlobale(err.message)
      });
    }
  }

  private afficherErreurGlobale(message: string): void {
    this.snackBar.open(message || 'Une erreur est survenue', 'Fermer', { duration: 4000 });
  }
}
