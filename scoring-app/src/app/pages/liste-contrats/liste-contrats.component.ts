import { Component } from '@angular/core';

@Component({
  selector: 'app-liste-contrats',
  standalone: true,
  template: '<div class="page-container"><h2>Liste des Contrats</h2><p>Liste filtrable et paginee des contrats scores.</p></div>',
  styles: ['.page-container { padding: 24px; }']
})
export class ListeContratsComponent {}
