export type Role = 'ADMIN' | 'GESTIONNAIRE';

export interface User {
  user_id: number;
  email: string;
  nom: string;
  role: Role;
  actif: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface UserCreate {
  email: string;
  password: string;
  nom: string;
  role: Role;
}

export interface UserUpdate {
  nom?: string;
  role?: Role;
  actif?: boolean;
  password?: string;
}
