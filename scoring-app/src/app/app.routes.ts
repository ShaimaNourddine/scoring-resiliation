import { Routes } from '@angular/router';
import { ScoringContratComponent } from './pages/scoring-contrat/scoring-contrat.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { ListeContratsComponent } from './pages/liste-contrats/liste-contrats.component';
import { BatchComponent } from './pages/batch/batch.component';
import { LoginComponent } from './pages/login/login.component';
import { AdminUsersComponent } from './pages/admin-users/admin-users.component';
import { authGuard, adminGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: '/scoring', pathMatch: 'full' },
  { path: 'login', component: LoginComponent },
  { path: 'scoring', component: ScoringContratComponent, canActivate: [authGuard] },
  { path: 'dashboard', component: DashboardComponent, canActivate: [authGuard] },
  { path: 'contrats', component: ListeContratsComponent, canActivate: [authGuard] },
  { path: 'batch', component: BatchComponent, canActivate: [authGuard] },
  { path: 'admin/users', component: AdminUsersComponent, canActivate: [adminGuard] },
];
