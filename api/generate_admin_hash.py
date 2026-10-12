"""
Génère le hash bcrypt du mot de passe admin initial, à coller dans
SQL/create_table_users.sql (colonne PASSWORD_HASH).

Usage:
    python generate_admin_hash.py
    python generate_admin_hash.py "MonMotDePasse123!"

Prérequis:
    pip install bcrypt

NB : utilise directement le package bcrypt plutôt que passlib. passlib
1.7.4 (dernière version publiée) n'est pas compatible avec bcrypt >= 4.1
(API interne renommée, cf. AttributeError module 'bcrypt' has no
attribute '__about__') et le projet n'est plus maintenu activement.
"""

import sys

import bcrypt

password = sys.argv[1] if len(sys.argv) > 1 else "ChangeMoi123!"

if len(password.encode('utf-8')) > 72:
    raise ValueError("Le mot de passe ne doit pas dépasser 72 octets (limite bcrypt).")

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

print(f"Mot de passe : {password}")
print(f"Hash bcrypt  : {hashed}")
print()
print("Colle ce hash dans SQL/create_table_users.sql, colonne PASSWORD_HASH.")
