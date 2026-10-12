export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
  // URL d'intégration sécurisée Power BI ("Incorporer le rapport" > "Site
  // web ou portail"), conçue pour être chargée en iframe cross-origin.
  // Nécessite que l'utilisateur soit connecté à un compte Microsoft ayant
  // accès au rapport (fenêtre de connexion affichée dans l'iframe au besoin).
  // NB : disponible grâce à l'essai Power BI Pro ; vérifier qu'elle reste
  // valide après son expiration (cf. date affichée dans Power BI Service).
  powerBiEmbedUrl: 'https://app.powerbi.com/reportEmbed?reportId=d9f8295d-c249-4922-884c-46a8f547bc74&autoAuth=true&ctid=d826664f-15b5-465e-b789-65c3c61e69ee'
};
