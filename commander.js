// api/commander.js
const crypto = require('crypto');

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).send('Method Not Allowed');

  const { initData, panier, botToken } = req.body;

  // 1. Validation de la signature Telegram
  const urlParams = new URLSearchParams(initData);
  const hash = urlParams.get('hash');
  urlParams.delete('hash');

  const dataCheckString = Array.from(urlParams.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${key}=${value}`)
    .join('\n');

  const secretKey = crypto.createHmac('sha256', 'WebAppData').update(botToken).digest();
  const hmac = crypto.createHmac('sha256', secretKey).update(dataCheckString).digest('hex');

  if (hmac !== hash) {
    return res.status(401).json({ error: "Données invalides" });
  }

  // 2. Récupération de l'ID Client
  const user = JSON.parse(urlParams.get('user'));

  // 3. Réponse (ici tu pourrais enregistrer en DB)
  return res.status(200).json({
    message: "Commande reçue !",
    client: user.first_name,
    totalItems: panier.length
  });
}
