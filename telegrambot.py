#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔══════════════════════════════════════════════════════════════════╗
║          BOT TELEGRAM - BOUTIQUE EN LIGNE COMPLÈTE              ║
║  Bibliothèque : pyTelegramBotAPI  |  Base de données : SQLite   ║
╚══════════════════════════════════════════════════════════════════╝

Installation des dépendances :
    pip install pyTelegramBotAPI

Configuration :
    1. Remplacez TOKEN par votre token BotFather
    2. Remplacez ADMIN_IDS par vos identifiants Telegram
    3. Lancez : python telegram_bot.py
"""

import telebot
import sqlite3
import os
import logging
from telebot import types
from datetime import datetime

# ══════════════════════════════════════════════════════════════════
# ██  CONFIGURATION GLOBALE – VARIABLES D'ENVIRONNEMENT
# ══════════════════════════════════════════════════════════════════

# Token Telegram chargé depuis la variable d'environnement TOKEN
# → À définir dans le dashboard Render (jamais dans le code !)
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("❌ Variable d'environnement TOKEN manquante !")

# Identifiants admins chargés depuis ADMIN_IDS (ex: "123456789,987654321")
# → À définir dans le dashboard Render, séparés par des virgules
_raw_admins = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(i.strip()) for i in _raw_admins.split(",") if i.strip().isdigit()]
if not ADMIN_IDS:
    raise ValueError("❌ Variable d'environnement ADMIN_IDS manquante ou invalide !")

# Base de données stockée sur le disque persistant Render (/data)
# En local, elle sera créée dans le dossier courant
DB_NAME = os.environ.get("DB_PATH", "/data/boutique.db")

# Devise utilisée dans le bot
DEVISE = "€"

# Configuration du logging pour le débogage
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialisation de l'instance du bot
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ══════════════════════════════════════════════════════════════════
# ██  GESTION DE LA BASE DE DONNÉES
# ══════════════════════════════════════════════════════════════════

def obtenir_connexion():
    """
    Crée et retourne une connexion à la base de données SQLite.
    Utilise check_same_thread=False pour la compatibilité multi-thread
    avec pyTelegramBotAPI qui traite plusieurs messages en parallèle.
    """
    connexion = sqlite3.connect(DB_NAME, check_same_thread=False)
    connexion.row_factory = sqlite3.Row  # Accès aux colonnes par nom
    return connexion


def initialiser_base_de_donnees():
    """
    Crée toutes les tables nécessaires si elles n'existent pas encore.
    Appelée au démarrage du bot pour s'assurer que la structure est prête.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()

    # ── Table UTILISATEURS ──────────────────────────────────────────
    # Stocke le profil complet de chaque utilisateur Telegram
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS utilisateurs (
            telegram_id     INTEGER PRIMARY KEY,
            username        TEXT,
            nom             TEXT,
            adresse         TEXT,
            code_postal     TEXT,
            ville           TEXT,
            region          TEXT,
            pays            TEXT,
            telephone       TEXT,
            email           TEXT,
            solde           REAL    DEFAULT 0.0,
            profil_complet  INTEGER DEFAULT 0,
            date_inscription TEXT   DEFAULT (datetime('now'))
        )
    """)

    # ── Table PRODUITS ──────────────────────────────────────────────
    # Catalogue des articles disponibles dans la boutique
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS produits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nom         TEXT    NOT NULL,
            description TEXT,
            prix        REAL    NOT NULL,
            stock       INTEGER DEFAULT 0,
            emoji       TEXT    DEFAULT '📦',
            actif       INTEGER DEFAULT 1,
            date_ajout  TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Table PANIER ────────────────────────────────────────────────
    # Articles ajoutés au panier par chaque utilisateur
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS panier (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            produit_id  INTEGER NOT NULL,
            quantite    INTEGER DEFAULT 1,
            FOREIGN KEY (telegram_id) REFERENCES utilisateurs(telegram_id),
            FOREIGN KEY (produit_id)  REFERENCES produits(id),
            UNIQUE(telegram_id, produit_id)
        )
    """)

    # ── Table COMMANDES ─────────────────────────────────────────────
    # Historique de toutes les commandes passées
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS commandes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER NOT NULL,
            total           REAL    NOT NULL,
            statut          TEXT    DEFAULT 'en_attente',
            date_commande   TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (telegram_id) REFERENCES utilisateurs(telegram_id)
        )
    """)

    # ── Table LIGNES DE COMMANDE ────────────────────────────────────
    # Détail de chaque article dans une commande
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS lignes_commande (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            commande_id INTEGER NOT NULL,
            produit_id  INTEGER NOT NULL,
            quantite    INTEGER NOT NULL,
            prix_unitaire REAL  NOT NULL,
            FOREIGN KEY (commande_id) REFERENCES commandes(id),
            FOREIGN KEY (produit_id)  REFERENCES produits(id)
        )
    """)

    # ── Table TRANSACTIONS WALLET ───────────────────────────────────
    # Historique des mouvements de solde (recharges, paiements)
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER NOT NULL,
            montant         REAL    NOT NULL,
            type_transaction TEXT   NOT NULL,
            description     TEXT,
            date_transaction TEXT   DEFAULT (datetime('now')),
            FOREIGN KEY (telegram_id) REFERENCES utilisateurs(telegram_id)
        )
    """)

    # Ajout de quelques produits d'exemple si la table est vide
    curseur.execute("SELECT COUNT(*) FROM produits")
    if curseur.fetchone()[0] == 0:
        produits_demo = [
            ("Casque Audio Premium", "Son cristallin 360° avec réduction de bruit active", 89.99, 15, "🎧"),
            ("Montre Connectée", "Suivi santé, GPS intégré et autonomie 7 jours",      149.99, 8,  "⌚"),
            ("Clavier Mécanique",  "Switch tactiles, rétroéclairage RGB personnalisable", 74.99, 20, "⌨️"),
            ("Souris Gaming",      "16000 DPI, 7 boutons programmables, RGB",             49.99, 25, "🖱️"),
            ("Webcam HD 4K",       "Auto-focus, micro intégré, compatible OBS",           69.99, 12, "📷"),
        ]
        curseur.executemany(
            "INSERT INTO produits (nom, description, prix, stock, emoji) VALUES (?, ?, ?, ?, ?)",
            produits_demo
        )
        logger.info("Produits de démonstration insérés avec succès.")

    conn.commit()
    conn.close()
    logger.info("Base de données initialisée avec succès.")


# ══════════════════════════════════════════════════════════════════
# ██  FONCTIONS UTILITAIRES – UTILISATEURS
# ══════════════════════════════════════════════════════════════════

def obtenir_utilisateur(telegram_id: int) -> sqlite3.Row | None:
    """
    Récupère les données complètes d'un utilisateur depuis la base.
    Retourne None si l'utilisateur n'est pas encore enregistré.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute("SELECT * FROM utilisateurs WHERE telegram_id = ?", (telegram_id,))
    utilisateur = curseur.fetchone()
    conn.close()
    return utilisateur


def creer_ou_mettre_a_jour_utilisateur(telegram_id: int, username: str):
    """
    Insère un nouvel utilisateur ou met à jour son username s'il existe déjà.
    Appelée à chaque interaction pour s'assurer que l'utilisateur est en base.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute("""
        INSERT INTO utilisateurs (telegram_id, username)
        VALUES (?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET username = excluded.username
    """, (telegram_id, username or ""))
    conn.commit()
    conn.close()


def mettre_a_jour_champ_profil(telegram_id: int, champ: str, valeur: str):
    """
    Met à jour un champ spécifique du profil utilisateur.
    Paramètre champ : nom exact de la colonne SQL à modifier.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    # Construction dynamique sécurisée de la requête (champ validé en amont)
    curseur.execute(f"UPDATE utilisateurs SET {champ} = ? WHERE telegram_id = ?", (valeur, telegram_id))
    conn.commit()
    conn.close()


def marquer_profil_complet(telegram_id: int):
    """
    Marque le profil de l'utilisateur comme entièrement rempli.
    Débloque l'accès à la boutique et aux fonctionnalités avancées.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute(
        "UPDATE utilisateurs SET profil_complet = 1 WHERE telegram_id = ?",
        (telegram_id,)
    )
    conn.commit()
    conn.close()


def profil_est_complet(telegram_id: int) -> bool:
    """
    Vérifie si l'utilisateur a complété toutes les étapes de son profil.
    Retourne True si le profil est complet, False sinon.
    """
    utilisateur = obtenir_utilisateur(telegram_id)
    if not utilisateur:
        return False
    return bool(utilisateur["profil_complet"])


# ══════════════════════════════════════════════════════════════════
# ██  FONCTIONS UTILITAIRES – WALLET (PORTEFEUILLE)
# ══════════════════════════════════════════════════════════════════

def obtenir_solde(telegram_id: int) -> float:
    """
    Retourne le solde actuel du wallet de l'utilisateur.
    """
    utilisateur = obtenir_utilisateur(telegram_id)
    if not utilisateur:
        return 0.0
    return float(utilisateur["solde"] or 0.0)


def crediter_wallet(telegram_id: int, montant: float, description: str = "Recharge manuelle"):
    """
    Ajoute un montant au solde de l'utilisateur et enregistre la transaction.
    Utilisée pour les recharges ou les remboursements.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute(
        "UPDATE utilisateurs SET solde = solde + ? WHERE telegram_id = ?",
        (montant, telegram_id)
    )
    curseur.execute("""
        INSERT INTO transactions (telegram_id, montant, type_transaction, description)
        VALUES (?, ?, 'credit', ?)
    """, (telegram_id, montant, description))
    conn.commit()
    conn.close()


def debiter_wallet(telegram_id: int, montant: float, description: str = "Achat") -> bool:
    """
    Déduit un montant du solde si le solde est suffisant.
    Retourne True si le débit a réussi, False si solde insuffisant.
    """
    solde = obtenir_solde(telegram_id)
    if solde < montant:
        return False
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute(
        "UPDATE utilisateurs SET solde = solde - ? WHERE telegram_id = ?",
        (montant, telegram_id)
    )
    curseur.execute("""
        INSERT INTO transactions (telegram_id, montant, type_transaction, description)
        VALUES (?, ?, 'debit', ?)
    """, (telegram_id, montant, description))
    conn.commit()
    conn.close()
    return True


def obtenir_historique_transactions(telegram_id: int, limite: int = 10) -> list:
    """
    Récupère les dernières transactions du wallet de l'utilisateur.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute("""
        SELECT * FROM transactions
        WHERE telegram_id = ?
        ORDER BY date_transaction DESC
        LIMIT ?
    """, (telegram_id, limite))
    transactions = curseur.fetchall()
    conn.close()
    return transactions


# ══════════════════════════════════════════════════════════════════
# ██  FONCTIONS UTILITAIRES – PRODUITS
# ══════════════════════════════════════════════════════════════════

def obtenir_tous_les_produits(inclure_inactifs: bool = False) -> list:
    """
    Récupère la liste de tous les produits du catalogue.
    Par défaut, retourne uniquement les produits actifs (visibles en boutique).
    L'option inclure_inactifs est réservée à l'administration.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    if inclure_inactifs:
        curseur.execute("SELECT * FROM produits ORDER BY id")
    else:
        curseur.execute("SELECT * FROM produits WHERE actif = 1 ORDER BY id")
    produits = curseur.fetchall()
    conn.close()
    return produits


def obtenir_produit(produit_id: int) -> sqlite3.Row | None:
    """
    Récupère les détails complets d'un produit par son identifiant.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute("SELECT * FROM produits WHERE id = ?", (produit_id,))
    produit = curseur.fetchone()
    conn.close()
    return produit


def ajouter_produit(nom: str, description: str, prix: float, stock: int, emoji: str = "📦") -> int:
    """
    Insère un nouveau produit dans le catalogue.
    Retourne l'identifiant du produit créé.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute(
        "INSERT INTO produits (nom, description, prix, stock, emoji) VALUES (?, ?, ?, ?, ?)",
        (nom, description, prix, stock, emoji)
    )
    produit_id = curseur.lastrowid
    conn.commit()
    conn.close()
    return produit_id


def modifier_produit(produit_id: int, champ: str, valeur) -> bool:
    """
    Met à jour un champ spécifique d'un produit existant.
    Retourne True si la modification a réussi.
    """
    champs_autorises = {"nom", "description", "prix", "stock", "emoji", "actif"}
    if champ not in champs_autorises:
        return False
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute(f"UPDATE produits SET {champ} = ? WHERE id = ?", (valeur, produit_id))
    conn.commit()
    conn.close()
    return True


def supprimer_produit(produit_id: int):
    """
    Supprime définitivement un produit de la base de données.
    Attention : préférez désactiver (actif=0) plutôt que supprimer.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute("DELETE FROM produits WHERE id = ?", (produit_id,))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════
# ██  FONCTIONS UTILITAIRES – PANIER
# ══════════════════════════════════════════════════════════════════

def obtenir_panier(telegram_id: int) -> list:
    """
    Récupère tous les articles du panier d'un utilisateur avec les détails produits.
    Jointure avec la table produits pour afficher les informations complètes.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute("""
        SELECT p.id, p.nom, p.prix, p.emoji, pa.quantite,
               (p.prix * pa.quantite) AS sous_total
        FROM panier pa
        JOIN produits p ON pa.produit_id = p.id
        WHERE pa.telegram_id = ?
        ORDER BY p.nom
    """, (telegram_id,))
    articles = curseur.fetchall()
    conn.close()
    return articles


def ajouter_au_panier(telegram_id: int, produit_id: int, quantite: int = 1):
    """
    Ajoute un produit au panier ou incrémente sa quantité s'il est déjà présent.
    Utilise INSERT OR REPLACE avec calcul de la nouvelle quantité.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute("""
        INSERT INTO panier (telegram_id, produit_id, quantite)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id, produit_id)
        DO UPDATE SET quantite = quantite + ?
    """, (telegram_id, produit_id, quantite, quantite))
    conn.commit()
    conn.close()


def retirer_du_panier(telegram_id: int, produit_id: int):
    """
    Décrémente la quantité d'un article ou le supprime si quantité atteint 0.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    # Vérifie la quantité actuelle
    curseur.execute(
        "SELECT quantite FROM panier WHERE telegram_id = ? AND produit_id = ?",
        (telegram_id, produit_id)
    )
    ligne = curseur.fetchone()
    if ligne:
        if ligne["quantite"] > 1:
            curseur.execute(
                "UPDATE panier SET quantite = quantite - 1 WHERE telegram_id = ? AND produit_id = ?",
                (telegram_id, produit_id)
            )
        else:
            curseur.execute(
                "DELETE FROM panier WHERE telegram_id = ? AND produit_id = ?",
                (telegram_id, produit_id)
            )
    conn.commit()
    conn.close()


def vider_panier(telegram_id: int):
    """
    Supprime tous les articles du panier d'un utilisateur.
    Appelée après validation d'une commande ou sur demande explicite.
    """
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute("DELETE FROM panier WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()


def calculer_total_panier(telegram_id: int) -> float:
    """
    Calcule et retourne le montant total du panier de l'utilisateur.
    """
    articles = obtenir_panier(telegram_id)
    return sum(article["sous_total"] for article in articles)


# ══════════════════════════════════════════════════════════════════
# ██  GESTION DES ÉTATS (FSM simplifié)
# ══════════════════════════════════════════════════════════════════

# Dictionnaire stockant l'état conversationnel de chaque utilisateur
# Clé : telegram_id | Valeur : étape en cours (ex: "attente_nom")
etats_utilisateurs = {}

# Dictionnaire pour stocker temporairement les données en cours de saisie
donnees_temporaires = {}

def definir_etat(telegram_id: int, etat: str):
    """
    Enregistre l'état actuel d'un utilisateur dans le gestionnaire d'états.
    L'état détermine comment le bot traite les messages suivants.
    """
    etats_utilisateurs[telegram_id] = etat


def obtenir_etat(telegram_id: int) -> str | None:
    """
    Récupère l'état actuel d'un utilisateur.
    Retourne None si l'utilisateur n'a pas d'état actif.
    """
    return etats_utilisateurs.get(telegram_id)


def effacer_etat(telegram_id: int):
    """
    Supprime l'état d'un utilisateur (fin de workflow).
    """
    etats_utilisateurs.pop(telegram_id, None)
    donnees_temporaires.pop(telegram_id, None)


# ══════════════════════════════════════════════════════════════════
# ██  CLAVIERS (KEYBOARDS)
# ══════════════════════════════════════════════════════════════════

def clavier_menu_principal() -> types.ReplyKeyboardMarkup:
    """
    Génère le menu principal persistant affiché en bas de l'écran Telegram.
    Utilise ReplyKeyboardMarkup pour des boutons toujours visibles.
    """
    clavier = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    clavier.add(
        types.KeyboardButton("🛍️ Boutique"),
        types.KeyboardButton("🛒 Mon Panier"),
        types.KeyboardButton("👤 Mon Profil"),
        types.KeyboardButton("💰 Wallet")
    )
    return clavier


def clavier_admin() -> types.ReplyKeyboardMarkup:
    """
    Génère le menu d'administration réservé aux administrateurs.
    Accessible uniquement si l'ID Telegram est dans ADMIN_IDS.
    """
    clavier = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    clavier.add(
        types.KeyboardButton("➕ Ajouter Produit"),
        types.KeyboardButton("📋 Liste Produits Admin"),
        types.KeyboardButton("👥 Liste Utilisateurs"),
        types.KeyboardButton("💳 Créditer Wallet"),
        types.KeyboardButton("🚪 Quitter Admin")
    )
    return clavier


def clavier_inline_produit(produit_id: int, quantite_panier: int = 0) -> types.InlineKeyboardMarkup:
    """
    Génère les boutons inline pour un produit (ajouter/retirer du panier).
    Affiche la quantité actuelle dans le panier si > 0.
    """
    clavier = types.InlineKeyboardMarkup(row_width=3)

    # Bouton retirer (- quantité)
    btn_moins = types.InlineKeyboardButton(
        "➖",
        callback_data=f"retirer_{produit_id}"
    )
    # Affichage de la quantité au centre
    btn_quantite = types.InlineKeyboardButton(
        f"🛒 {quantite_panier}" if quantite_panier > 0 else "🛒",
        callback_data=f"info_{produit_id}"
    )
    # Bouton ajouter (+ quantité)
    btn_plus = types.InlineKeyboardButton(
        "➕",
        callback_data=f"ajouter_{produit_id}"
    )
    clavier.add(btn_moins, btn_quantite, btn_plus)
    return clavier


def clavier_inline_panier(articles: list) -> types.InlineKeyboardMarkup:
    """
    Génère les boutons inline pour la gestion du panier.
    Permet de valider la commande, vider le panier ou retirer des articles.
    """
    clavier = types.InlineKeyboardMarkup(row_width=2)
    if articles:
        clavier.add(
            types.InlineKeyboardButton("✅ Valider la commande", callback_data="valider_commande"),
            types.InlineKeyboardButton("🗑️ Vider le panier",   callback_data="vider_panier")
        )
    return clavier


def clavier_inline_admin_produit(produit_id: int) -> types.InlineKeyboardMarkup:
    """
    Génère les boutons de gestion admin pour un produit spécifique.
    Permet de modifier le prix, le stock, activer/désactiver ou supprimer.
    """
    clavier = types.InlineKeyboardMarkup(row_width=2)
    clavier.add(
        types.InlineKeyboardButton("✏️ Nom",         callback_data=f"admin_edit_nom_{produit_id}"),
        types.InlineKeyboardButton("💬 Description",  callback_data=f"admin_edit_desc_{produit_id}"),
        types.InlineKeyboardButton("💶 Prix",         callback_data=f"admin_edit_prix_{produit_id}"),
        types.InlineKeyboardButton("📦 Stock",        callback_data=f"admin_edit_stock_{produit_id}"),
        types.InlineKeyboardButton("😀 Emoji",        callback_data=f"admin_edit_emoji_{produit_id}"),
        types.InlineKeyboardButton("🔄 Activer/Désactiver", callback_data=f"admin_toggle_{produit_id}"),
        types.InlineKeyboardButton("🗑️ Supprimer",   callback_data=f"admin_suppr_{produit_id}")
    )
    return clavier


# ══════════════════════════════════════════════════════════════════
# ██  GESTION DU PROFIL UTILISATEUR (COLLECTE SÉQUENTIELLE)
# ══════════════════════════════════════════════════════════════════

# Séquence des étapes de collecte du profil (ordre important)
ETAPES_PROFIL = [
    ("nom",          "👤 Entrez votre <b>nom complet</b> :"),
    ("adresse",      "🏠 Entrez votre <b>adresse postale</b> (numéro et rue) :"),
    ("code_postal",  "📮 Entrez votre <b>code postal</b> :"),
    ("ville",        "🏙️ Entrez votre <b>ville</b> :"),
    ("region",       "🗺️ Entrez votre <b>région / département</b> :"),
    ("pays",         "🌍 Entrez votre <b>pays</b> :"),
    ("telephone",    "📱 Entrez votre <b>numéro de téléphone</b> :"),
    ("email",        "📧 Entrez votre <b>adresse email</b> :"),
]

def demarrer_collecte_profil(message: types.Message):
    """
    Lance le processus de collecte séquentielle du profil.
    Définit l'état sur la première étape et pose la première question.
    """
    telegram_id = message.from_user.id
    definir_etat(telegram_id, "profil_0")  # Étape 0 = collecte du nom

    # Masquage temporaire du clavier principal pour éviter les confusions
    clavier_retrait = types.ReplyKeyboardRemove()
    bot.send_message(
        telegram_id,
        "📋 <b>Création de votre profil</b>\n\n"
        "Veuillez renseigner les informations suivantes.\n"
        "Ces données sont nécessaires pour traiter vos commandes.\n\n"
        + ETAPES_PROFIL[0][1],
        reply_markup=clavier_retrait
    )


def traiter_etape_profil(message: types.Message):
    """
    Traite la réponse de l'utilisateur pour l'étape courante du profil.
    Passe à l'étape suivante ou marque le profil comme complet.
    """
    telegram_id = message.from_user.id
    etat = obtenir_etat(telegram_id)

    if not etat or not etat.startswith("profil_"):
        return

    # Extraction du numéro d'étape depuis l'état
    numero_etape = int(etat.split("_")[1])
    champ, _ = ETAPES_PROFIL[numero_etape]
    valeur = message.text.strip()

    # Validation minimale : champ non vide
    if not valeur:
        bot.send_message(telegram_id, "⚠️ Ce champ ne peut pas être vide. Réessayez :")
        return

    # Validation de l'email à la dernière étape
    if champ == "email" and "@" not in valeur:
        bot.send_message(telegram_id, "⚠️ Adresse email invalide. Réessayez :")
        return

    # Sauvegarde de la valeur en base de données
    mettre_a_jour_champ_profil(telegram_id, champ, valeur)

    # Passage à l'étape suivante
    prochaine_etape = numero_etape + 1

    if prochaine_etape < len(ETAPES_PROFIL):
        # Il reste des étapes : poser la prochaine question
        definir_etat(telegram_id, f"profil_{prochaine_etape}")
        _, question = ETAPES_PROFIL[prochaine_etape]
        progression = f"({prochaine_etape + 1}/{len(ETAPES_PROFIL)})"
        bot.send_message(telegram_id, f"{progression} {question}")
    else:
        # Toutes les étapes complétées : finaliser le profil
        marquer_profil_complet(telegram_id)
        effacer_etat(telegram_id)
        bot.send_message(
            telegram_id,
            "✅ <b>Profil créé avec succès !</b>\n\n"
            "Vous avez maintenant accès à toutes les fonctionnalités.\n"
            "Bienvenue dans notre boutique ! 🎉",
            reply_markup=clavier_menu_principal()
        )


# ══════════════════════════════════════════════════════════════════
# ██  HANDLERS – COMMANDES DE BASE
# ══════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start"])
def handle_start(message: types.Message):
    """
    Handler de la commande /start.
    Enregistre l'utilisateur et lance la collecte du profil si nécessaire.
    """
    telegram_id = message.from_user.id
    username = message.from_user.username

    # Enregistrement ou mise à jour de l'utilisateur en base
    creer_ou_mettre_a_jour_utilisateur(telegram_id, username)

    prenom = message.from_user.first_name or "là"

    if profil_est_complet(telegram_id):
        # Utilisateur déjà enregistré : affichage du menu principal
        bot.send_message(
            telegram_id,
            f"👋 Bon retour, <b>{prenom}</b> !\n\n"
            "Que souhaitez-vous faire aujourd'hui ?",
            reply_markup=clavier_menu_principal()
        )
    else:
        # Nouvel utilisateur : démarrage de la collecte du profil
        bot.send_message(
            telegram_id,
            f"👋 Bonjour <b>{prenom}</b>, bienvenue dans notre boutique !\n\n"
            "Avant de commencer, nous avons besoin de quelques informations."
        )
        demarrer_collecte_profil(message)


@bot.message_handler(commands=["admin"])
def handle_commande_admin(message: types.Message):
    """
    Handler de la commande /admin.
    Affiche le panneau d'administration si l'utilisateur est autorisé.
    """
    telegram_id = message.from_user.id
    if telegram_id not in ADMIN_IDS:
        bot.send_message(telegram_id, "⛔ Accès refusé. Vous n'êtes pas administrateur.")
        return

    definir_etat(telegram_id, "admin")
    bot.send_message(
        telegram_id,
        "🔐 <b>Panneau d'Administration</b>\n\n"
        "Bienvenue dans l'interface de gestion.\n"
        "Choisissez une action :",
        reply_markup=clavier_admin()
    )


@bot.message_handler(commands=["profil"])
def handle_commande_profil(message: types.Message):
    """
    Handler de la commande /profil.
    Affiche ou permet de modifier le profil de l'utilisateur.
    """
    afficher_profil(message)


# ══════════════════════════════════════════════════════════════════
# ██  HANDLERS – MENU PRINCIPAL (REPLY KEYBOARD)
# ══════════════════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: m.text == "🛍️ Boutique")
def handle_boutique(message: types.Message):
    """
    Affiche le catalogue de produits avec les boutons inline ajouter/retirer.
    Vérifie d'abord que le profil est complet pour accéder à la boutique.
    """
    telegram_id = message.from_user.id

    if not profil_est_complet(telegram_id):
        bot.send_message(telegram_id, "⚠️ Veuillez d'abord compléter votre profil.")
        demarrer_collecte_profil(message)
        return

    produits = obtenir_tous_les_produits()

    if not produits:
        bot.send_message(telegram_id, "😔 Aucun produit disponible pour le moment.")
        return

    bot.send_message(telegram_id, "🛍️ <b>Notre Catalogue</b>\n\nDécouvrez nos produits :")

    # Récupération du panier pour afficher les quantités actuelles
    panier = obtenir_panier(telegram_id)
    panier_dict = {article["id"]: article["quantite"] for article in panier}

    # Affichage de chaque produit avec ses boutons inline
    for produit in produits:
        quantite_panier = panier_dict.get(produit["id"], 0)
        stock_txt = f"📦 Stock : {produit['stock']}" if produit["stock"] > 0 else "❌ Rupture de stock"

        texte = (
            f"{produit['emoji']} <b>{produit['nom']}</b>\n"
            f"💬 {produit['description']}\n"
            f"💶 <b>{produit['prix']:.2f} {DEVISE}</b>  |  {stock_txt}"
        )

        bot.send_message(
            telegram_id,
            texte,
            reply_markup=clavier_inline_produit(produit["id"], quantite_panier)
        )


@bot.message_handler(func=lambda m: m.text == "🛒 Mon Panier")
def handle_mon_panier(message: types.Message):
    """
    Affiche le contenu du panier de l'utilisateur avec le total.
    Propose les options de validation ou de vidage du panier.
    """
    telegram_id = message.from_user.id

    if not profil_est_complet(telegram_id):
        bot.send_message(telegram_id, "⚠️ Veuillez d'abord compléter votre profil.")
        return

    articles = obtenir_panier(telegram_id)

    if not articles:
        bot.send_message(
            telegram_id,
            "🛒 Votre panier est vide.\n\n"
            "Visitez la boutique pour ajouter des produits !"
        )
        return

    # Construction du récapitulatif du panier
    lignes = ["🛒 <b>Votre Panier</b>\n"]
    for article in articles:
        lignes.append(
            f"{article['emoji']} {article['nom']}\n"
            f"   {article['quantite']} × {article['prix']:.2f} {DEVISE} "
            f"= <b>{article['sous_total']:.2f} {DEVISE}</b>"
        )

    total = calculer_total_panier(telegram_id)
    solde = obtenir_solde(telegram_id)
    lignes.append(f"\n━━━━━━━━━━━━━━━━━━━━")
    lignes.append(f"💶 <b>Total : {total:.2f} {DEVISE}</b>")
    lignes.append(f"💰 Votre solde : {solde:.2f} {DEVISE}")

    if solde >= total:
        lignes.append("✅ Solde suffisant pour valider")
    else:
        manque = total - solde
        lignes.append(f"⚠️ Solde insuffisant (manque {manque:.2f} {DEVISE})")

    bot.send_message(
        telegram_id,
        "\n".join(lignes),
        reply_markup=clavier_inline_panier(articles)
    )


@bot.message_handler(func=lambda m: m.text == "👤 Mon Profil")
def handle_mon_profil(message: types.Message):
    """
    Affiche le profil complet de l'utilisateur avec toutes ses informations.
    Propose un bouton pour modifier le profil si besoin.
    """
    afficher_profil(message)


@bot.message_handler(func=lambda m: m.text == "💰 Wallet")
def handle_wallet(message: types.Message):
    """
    Affiche le wallet de l'utilisateur : solde et historique des transactions.
    """
    telegram_id = message.from_user.id

    if not profil_est_complet(telegram_id):
        bot.send_message(telegram_id, "⚠️ Veuillez d'abord compléter votre profil.")
        return

    solde = obtenir_solde(telegram_id)
    transactions = obtenir_historique_transactions(telegram_id, limite=5)

    texte = [f"💰 <b>Mon Wallet</b>\n\n💶 Solde actuel : <b>{solde:.2f} {DEVISE}</b>\n"]

    if transactions:
        texte.append("📊 <b>Dernières transactions :</b>")
        for tx in transactions:
            signe = "+" if tx["type_transaction"] == "credit" else "-"
            emoji_tx = "🟢" if tx["type_transaction"] == "credit" else "🔴"
            date_courte = tx["date_transaction"][:10]
            texte.append(
                f"{emoji_tx} {signe}{abs(tx['montant']):.2f} {DEVISE}  "
                f"| {tx['description']}  ({date_courte})"
            )
    else:
        texte.append("Aucune transaction pour le moment.")

    # Bouton de recharge (configuré pour intégration de paiement future)
    clavier = types.InlineKeyboardMarkup()
    clavier.add(
        types.InlineKeyboardButton("💳 Recharger mon Wallet", callback_data="recharger_wallet")
    )

    bot.send_message(telegram_id, "\n".join(texte), reply_markup=clavier)


# ══════════════════════════════════════════════════════════════════
# ██  HANDLERS – INTERFACE ADMIN
# ══════════════════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: m.text == "🚪 Quitter Admin")
def handle_quitter_admin(message: types.Message):
    """
    Quitte le mode administration et retourne au menu principal.
    """
    telegram_id = message.from_user.id
    effacer_etat(telegram_id)
    bot.send_message(
        telegram_id,
        "✅ Mode administrateur quitté. Retour au menu principal.",
        reply_markup=clavier_menu_principal()
    )


@bot.message_handler(func=lambda m: m.text == "➕ Ajouter Produit" and m.from_user.id in ADMIN_IDS)
def handle_admin_ajouter_produit(message: types.Message):
    """
    Lance le workflow d'ajout d'un nouveau produit (admin uniquement).
    Collecte séquentiellement : nom, description, prix, stock, emoji.
    """
    telegram_id = message.from_user.id
    definir_etat(telegram_id, "admin_produit_nom")
    donnees_temporaires[telegram_id] = {}
    bot.send_message(
        telegram_id,
        "➕ <b>Ajout d'un nouveau produit</b>\n\n"
        "Étape 1/5 – Entrez le <b>nom</b> du produit :"
    )


@bot.message_handler(func=lambda m: m.text == "📋 Liste Produits Admin" and m.from_user.id in ADMIN_IDS)
def handle_admin_liste_produits(message: types.Message):
    """
    Affiche tous les produits (actifs et inactifs) avec les boutons de gestion.
    Réservé à l'administration.
    """
    telegram_id = message.from_user.id
    produits = obtenir_tous_les_produits(inclure_inactifs=True)

    if not produits:
        bot.send_message(telegram_id, "Aucun produit dans la base de données.")
        return

    bot.send_message(telegram_id, f"📋 <b>Gestion des produits ({len(produits)} au total)</b>")

    for produit in produits:
        statut = "✅ Actif" if produit["actif"] else "❌ Inactif"
        texte = (
            f"{produit['emoji']} <b>#{produit['id']} – {produit['nom']}</b>\n"
            f"💬 {produit['description']}\n"
            f"💶 {produit['prix']:.2f} {DEVISE}  |  📦 Stock: {produit['stock']}  |  {statut}"
        )
        bot.send_message(
            telegram_id,
            texte,
            reply_markup=clavier_inline_admin_produit(produit["id"])
        )


@bot.message_handler(func=lambda m: m.text == "👥 Liste Utilisateurs" and m.from_user.id in ADMIN_IDS)
def handle_admin_liste_utilisateurs(message: types.Message):
    """
    Affiche la liste de tous les utilisateurs enregistrés.
    Réservé à l'administration.
    """
    telegram_id = message.from_user.id
    conn = obtenir_connexion()
    curseur = conn.cursor()
    curseur.execute("""
        SELECT telegram_id, username, nom, email, solde, profil_complet, date_inscription
        FROM utilisateurs ORDER BY date_inscription DESC
    """)
    utilisateurs = curseur.fetchall()
    conn.close()

    if not utilisateurs:
        bot.send_message(telegram_id, "Aucun utilisateur enregistré.")
        return

    bot.send_message(telegram_id, f"👥 <b>Utilisateurs ({len(utilisateurs)} au total)</b>")

    for u in utilisateurs:
        statut = "✅" if u["profil_complet"] else "⏳"
        texte = (
            f"{statut} <b>{u['nom'] or 'Profil incomplet'}</b>\n"
            f"🆔 {u['telegram_id']}  |  @{u['username'] or 'N/A'}\n"
            f"📧 {u['email'] or 'N/A'}  |  💰 {u['solde']:.2f} {DEVISE}\n"
            f"📅 {u['date_inscription'][:10]}"
        )
        bot.send_message(telegram_id, texte)


@bot.message_handler(func=lambda m: m.text == "💳 Créditer Wallet" and m.from_user.id in ADMIN_IDS)
def handle_admin_crediter_wallet(message: types.Message):
    """
    Lance le workflow de crédit manuel du wallet (admin uniquement).
    Format attendu : /crediter <telegram_id> <montant>
    """
    telegram_id = message.from_user.id
    definir_etat(telegram_id, "admin_crediter_id")
    bot.send_message(
        telegram_id,
        "💳 <b>Crédit Wallet Utilisateur</b>\n\n"
        "Entrez l'<b>ID Telegram</b> de l'utilisateur à créditer :"
    )


# ══════════════════════════════════════════════════════════════════
# ██  HANDLER PRINCIPAL – TRAITEMENT DES MESSAGES TEXTE
# ══════════════════════════════════════════════════════════════════

@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_message_texte(message: types.Message):
    """
    Handler générique qui traite tous les messages texte selon l'état actuel.
    Agit comme un routeur d'états pour les workflows séquentiels.
    """
    telegram_id = message.from_user.id
    etat = obtenir_etat(telegram_id)
    texte = message.text.strip()

    # ── Workflow de collecte du profil utilisateur ──────────────────
    if etat and etat.startswith("profil_"):
        traiter_etape_profil(message)
        return

    # ── Workflow d'ajout de produit (admin) ─────────────────────────
    if etat == "admin_produit_nom":
        donnees_temporaires[telegram_id]["nom"] = texte
        definir_etat(telegram_id, "admin_produit_desc")
        bot.send_message(telegram_id, "Étape 2/5 – Entrez la <b>description</b> du produit :")
        return

    if etat == "admin_produit_desc":
        donnees_temporaires[telegram_id]["description"] = texte
        definir_etat(telegram_id, "admin_produit_prix")
        bot.send_message(telegram_id, "Étape 3/5 – Entrez le <b>prix</b> (ex: 29.99) :")
        return

    if etat == "admin_produit_prix":
        try:
            prix = float(texte.replace(",", "."))
            donnees_temporaires[telegram_id]["prix"] = prix
            definir_etat(telegram_id, "admin_produit_stock")
            bot.send_message(telegram_id, "Étape 4/5 – Entrez le <b>stock initial</b> :")
        except ValueError:
            bot.send_message(telegram_id, "⚠️ Prix invalide. Entrez un nombre (ex: 29.99) :")
        return

    if etat == "admin_produit_stock":
        try:
            stock = int(texte)
            donnees_temporaires[telegram_id]["stock"] = stock
            definir_etat(telegram_id, "admin_produit_emoji")
            bot.send_message(telegram_id, "Étape 5/5 – Entrez l'<b>emoji</b> du produit (ex: 📱) :")
        except ValueError:
            bot.send_message(telegram_id, "⚠️ Stock invalide. Entrez un nombre entier :")
        return

    if etat == "admin_produit_emoji":
        donnees_temporaires[telegram_id]["emoji"] = texte
        d = donnees_temporaires[telegram_id]
        # Sauvegarde du nouveau produit en base
        produit_id = ajouter_produit(d["nom"], d["description"], d["prix"], d["stock"], d["emoji"])
        effacer_etat(telegram_id)
        bot.send_message(
            telegram_id,
            f"✅ <b>Produit ajouté avec succès !</b>\n\n"
            f"{d['emoji']} <b>{d['nom']}</b>\n"
            f"💶 {d['prix']:.2f} {DEVISE}  |  📦 Stock: {d['stock']}\n"
            f"🆔 Identifiant : #{produit_id}",
            reply_markup=clavier_admin()
        )
        return

    # ── Workflow de modification d'un champ produit (admin) ─────────
    if etat and etat.startswith("admin_edit_"):
        traiter_edition_produit(message, etat, texte)
        return

    # ── Workflow de crédit wallet (admin) ───────────────────────────
    if etat == "admin_crediter_id":
        try:
            cible_id = int(texte)
            utilisateur_cible = obtenir_utilisateur(cible_id)
            if not utilisateur_cible:
                bot.send_message(telegram_id, "⚠️ Utilisateur introuvable. Réessayez :")
                return
            donnees_temporaires[telegram_id] = {"cible_id": cible_id}
            definir_etat(telegram_id, "admin_crediter_montant")
            bot.send_message(
                telegram_id,
                f"✅ Utilisateur trouvé : <b>{utilisateur_cible['nom']}</b>\n"
                f"Solde actuel : {utilisateur_cible['solde']:.2f} {DEVISE}\n\n"
                "Entrez le <b>montant à créditer</b> :"
            )
        except ValueError:
            bot.send_message(telegram_id, "⚠️ ID invalide. Entrez un nombre entier :")
        return

    if etat == "admin_crediter_montant":
        try:
            montant = float(texte.replace(",", "."))
            cible_id = donnees_temporaires[telegram_id]["cible_id"]
            crediter_wallet(cible_id, montant, f"Crédit manuel par admin")
            effacer_etat(telegram_id)
            nouveau_solde = obtenir_solde(cible_id)
            bot.send_message(
                telegram_id,
                f"✅ <b>Wallet crédité avec succès !</b>\n\n"
                f"Utilisateur ID: {cible_id}\n"
                f"Montant crédité : +{montant:.2f} {DEVISE}\n"
                f"Nouveau solde : {nouveau_solde:.2f} {DEVISE}",
                reply_markup=clavier_admin()
            )
            # Notification à l'utilisateur crédité
            try:
                bot.send_message(
                    cible_id,
                    f"💰 <b>Wallet rechargé !</b>\n\n"
                    f"Votre wallet a été crédité de <b>{montant:.2f} {DEVISE}</b>.\n"
                    f"Nouveau solde : {nouveau_solde:.2f} {DEVISE}"
                )
            except Exception:
                pass  # L'utilisateur a peut-être bloqué le bot
        except ValueError:
            bot.send_message(telegram_id, "⚠️ Montant invalide. Entrez un nombre :")
        return

    # Message non reconnu
    if not profil_est_complet(telegram_id):
        demarrer_collecte_profil(message)
    else:
        bot.send_message(
            telegram_id,
            "❓ Commande non reconnue.\nUtilisez le menu ci-dessous.",
            reply_markup=clavier_menu_principal()
        )


def traiter_edition_produit(message: types.Message, etat: str, texte: str):
    """
    Traite la nouvelle valeur saisie lors de la modification d'un produit.
    L'état contient le champ à modifier et l'identifiant du produit.
    Format de l'état : admin_edit_{champ}_{produit_id}
    """
    telegram_id = message.from_user.id
    # Décomposition de l'état pour extraire champ et produit_id
    parties = etat.replace("admin_edit_", "").rsplit("_", 1)
    if len(parties) != 2:
        effacer_etat(telegram_id)
        return

    champ, produit_id_str = parties
    produit_id = int(produit_id_str)

    # Validation et conversion selon le type de champ
    valeur = texte
    if champ == "prix":
        try:
            valeur = float(texte.replace(",", "."))
        except ValueError:
            bot.send_message(telegram_id, "⚠️ Prix invalide. Réessayez :")
            return
    elif champ == "stock":
        try:
            valeur = int(texte)
        except ValueError:
            bot.send_message(telegram_id, "⚠️ Stock invalide. Réessayez :")
            return

    # Mise à jour en base de données
    succes = modifier_produit(produit_id, champ, valeur)
    effacer_etat(telegram_id)

    if succes:
        produit = obtenir_produit(produit_id)
        bot.send_message(
            telegram_id,
            f"✅ Champ <b>{champ}</b> mis à jour avec succès !\n"
            f"Nouvelle valeur : <b>{valeur}</b>",
            reply_markup=clavier_admin()
        )
    else:
        bot.send_message(telegram_id, "❌ Erreur lors de la modification.", reply_markup=clavier_admin())


# ══════════════════════════════════════════════════════════════════
# ██  HANDLERS – CALLBACKS INLINE
# ══════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: call.data.startswith("ajouter_"))
def callback_ajouter_panier(call: types.CallbackQuery):
    """
    Callback déclenché par le bouton ➕ sur un produit.
    Ajoute une unité du produit au panier de l'utilisateur.
    """
    telegram_id = call.from_user.id
    produit_id = int(call.data.split("_")[1])

    if not profil_est_complet(telegram_id):
        bot.answer_callback_query(call.id, "⚠️ Complétez votre profil d'abord !")
        return

    produit = obtenir_produit(produit_id)
    if not produit or not produit["actif"]:
        bot.answer_callback_query(call.id, "❌ Produit indisponible.", show_alert=True)
        return

    if produit["stock"] <= 0:
        bot.answer_callback_query(call.id, "❌ Rupture de stock !", show_alert=True)
        return

    ajouter_au_panier(telegram_id, produit_id)

    # Récupération de la nouvelle quantité dans le panier
    panier = obtenir_panier(telegram_id)
    panier_dict = {article["id"]: article["quantite"] for article in panier}
    nouvelle_quantite = panier_dict.get(produit_id, 0)

    # Mise à jour du clavier inline avec la nouvelle quantité
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=clavier_inline_produit(produit_id, nouvelle_quantite)
        )
    except Exception:
        pass  # Ignore si le message n'a pas changé

    bot.answer_callback_query(
        call.id,
        f"✅ {produit['nom']} ajouté au panier ! ({nouvelle_quantite} en tout)"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("retirer_"))
def callback_retirer_panier(call: types.CallbackQuery):
    """
    Callback déclenché par le bouton ➖ sur un produit.
    Retire une unité du produit du panier.
    """
    telegram_id = call.from_user.id
    produit_id = int(call.data.split("_")[1])

    retirer_du_panier(telegram_id, produit_id)

    # Récupération de la nouvelle quantité
    panier = obtenir_panier(telegram_id)
    panier_dict = {article["id"]: article["quantite"] for article in panier}
    nouvelle_quantite = panier_dict.get(produit_id, 0)

    # Mise à jour du clavier inline
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=clavier_inline_produit(produit_id, nouvelle_quantite)
        )
    except Exception:
        pass

    produit = obtenir_produit(produit_id)
    nom = produit["nom"] if produit else "Article"
    bot.answer_callback_query(call.id, f"➖ {nom} retiré du panier.")


@bot.callback_query_handler(func=lambda call: call.data == "valider_commande")
def callback_valider_commande(call: types.CallbackQuery):
    """
    Callback déclenché par le bouton "Valider la commande" dans le panier.
    Vérifie le solde, crée la commande et vide le panier.
    """
    telegram_id = call.from_user.id
    articles = obtenir_panier(telegram_id)

    if not articles:
        bot.answer_callback_query(call.id, "🛒 Votre panier est vide !", show_alert=True)
        return

    total = calculer_total_panier(telegram_id)
    solde = obtenir_solde(telegram_id)

    if solde < total:
        manque = total - solde
        bot.answer_callback_query(
            call.id,
            f"❌ Solde insuffisant !\nIl vous manque {manque:.2f} {DEVISE}.\n"
            "Rechargez votre Wallet.",
            show_alert=True
        )
        return

    # Débit du wallet et création de la commande
    if debiter_wallet(telegram_id, total, f"Commande boutique"):
        # Enregistrement de la commande
        conn = obtenir_connexion()
        curseur = conn.cursor()
        curseur.execute(
            "INSERT INTO commandes (telegram_id, total, statut) VALUES (?, ?, 'confirmee')",
            (telegram_id, total)
        )
        commande_id = curseur.lastrowid

        # Enregistrement des lignes de commande
        for article in articles:
            curseur.execute("""
                INSERT INTO lignes_commande (commande_id, produit_id, quantite, prix_unitaire)
                VALUES (?, ?, ?, ?)
            """, (commande_id, article["id"], article["quantite"], article["prix"]))

            # Mise à jour du stock
            curseur.execute(
                "UPDATE produits SET stock = MAX(0, stock - ?) WHERE id = ?",
                (article["quantite"], article["id"])
            )

        conn.commit()
        conn.close()

        # Vidage du panier après validation
        vider_panier(telegram_id)

        nouveau_solde = obtenir_solde(telegram_id)
        bot.answer_callback_query(call.id, "✅ Commande validée !")
        bot.send_message(
            telegram_id,
            f"✅ <b>Commande #{commande_id} confirmée !</b>\n\n"
            f"💶 Montant débité : {total:.2f} {DEVISE}\n"
            f"💰 Solde restant : {nouveau_solde:.2f} {DEVISE}\n\n"
            "Merci pour votre achat ! 🎉"
        )
    else:
        bot.answer_callback_query(call.id, "❌ Erreur lors du paiement.", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "vider_panier")
def callback_vider_panier(call: types.CallbackQuery):
    """
    Callback déclenché par le bouton "Vider le panier".
    Supprime tous les articles du panier après confirmation.
    """
    telegram_id = call.from_user.id
    vider_panier(telegram_id)
    bot.answer_callback_query(call.id, "🗑️ Panier vidé.")
    bot.send_message(telegram_id, "🗑️ Votre panier a été vidé avec succès.")


@bot.callback_query_handler(func=lambda call: call.data == "recharger_wallet")
def callback_recharger_wallet(call: types.CallbackQuery):
    """
    Callback déclenché par le bouton de recharge du wallet.
    Placeholder pour l'intégration future d'un système de paiement.
    (Telegram Payments, Stripe, CryptoBot, etc.)
    """
    bot.answer_callback_query(
        call.id,
        "💳 Système de recharge en cours d'intégration.\n"
        "Contactez l'administrateur pour recharger votre wallet.",
        show_alert=True
    )


# ── Callbacks d'administration des produits ─────────────────────

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_edit_") and call.from_user.id in ADMIN_IDS)
def callback_admin_editer_produit(call: types.CallbackQuery):
    """
    Callback pour l'édition d'un champ produit depuis l'interface admin.
    Démarre le workflow de saisie du nouveau champ.
    Format callback_data : admin_edit_{champ}_{produit_id}
    """
    telegram_id = call.from_user.id
    # Extraction du champ et de l'ID produit
    parties = call.data.replace("admin_edit_", "").rsplit("_", 1)
    if len(parties) != 2:
        bot.answer_callback_query(call.id, "Erreur de callback.")
        return

    champ, produit_id_str = parties
    produit_id = int(produit_id_str)
    produit = obtenir_produit(produit_id)

    if not produit:
        bot.answer_callback_query(call.id, "Produit introuvable.", show_alert=True)
        return

    # Définition de l'état d'édition
    definir_etat(telegram_id, f"admin_edit_{champ}_{produit_id}")

    labels = {
        "nom": "nom", "desc": "description", "prix": "prix",
        "stock": "stock", "emoji": "emoji"
    }
    label = labels.get(champ, champ)

    bot.answer_callback_query(call.id)
    bot.send_message(
        telegram_id,
        f"✏️ <b>Modification du produit #{produit_id}</b>\n\n"
        f"Valeur actuelle de <b>{label}</b> : "
        f"<code>{produit[champ if champ != 'desc' else 'description']}</code>\n\n"
        f"Entrez la nouvelle valeur :"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_toggle_") and call.from_user.id in ADMIN_IDS)
def callback_admin_toggle_produit(call: types.CallbackQuery):
    """
    Active ou désactive un produit (le rend visible/invisible dans la boutique).
    """
    produit_id = int(call.data.split("_")[2])
    produit = obtenir_produit(produit_id)

    if not produit:
        bot.answer_callback_query(call.id, "Produit introuvable.", show_alert=True)
        return

    nouveau_statut = 0 if produit["actif"] else 1
    modifier_produit(produit_id, "actif", nouveau_statut)
    statut_txt = "activé ✅" if nouveau_statut else "désactivé ❌"
    bot.answer_callback_query(call.id, f"Produit {statut_txt} !", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_suppr_") and call.from_user.id in ADMIN_IDS)
def callback_admin_supprimer_produit(call: types.CallbackQuery):
    """
    Supprime définitivement un produit de la base de données.
    Envoie une demande de confirmation avant la suppression.
    """
    produit_id = int(call.data.split("_")[2])
    produit = obtenir_produit(produit_id)

    if not produit:
        bot.answer_callback_query(call.id, "Produit introuvable.", show_alert=True)
        return

    # Boutons de confirmation
    clavier_confirmation = types.InlineKeyboardMarkup()
    clavier_confirmation.add(
        types.InlineKeyboardButton(
            "✅ Confirmer suppression",
            callback_data=f"admin_confirm_suppr_{produit_id}"
        ),
        types.InlineKeyboardButton(
            "❌ Annuler",
            callback_data=f"admin_annuler_suppr_{produit_id}"
        )
    )
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.from_user.id,
        f"⚠️ <b>Confirmer la suppression ?</b>\n\n"
        f"Produit : {produit['emoji']} {produit['nom']}\n"
        "Cette action est <b>irréversible</b>.",
        reply_markup=clavier_confirmation
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_confirm_suppr_") and call.from_user.id in ADMIN_IDS)
def callback_admin_confirmer_suppression(call: types.CallbackQuery):
    """
    Confirme et exécute la suppression d'un produit.
    """
    produit_id = int(call.data.split("_")[3])
    produit = obtenir_produit(produit_id)
    nom_produit = produit["nom"] if produit else f"#{produit_id}"
    supprimer_produit(produit_id)
    bot.answer_callback_query(call.id, f"🗑️ {nom_produit} supprimé.", show_alert=True)
    bot.edit_message_text(
        f"✅ Produit <b>{nom_produit}</b> supprimé avec succès.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_annuler_suppr_"))
def callback_admin_annuler_suppression(call: types.CallbackQuery):
    """
    Annule la suppression d'un produit.
    """
    bot.answer_callback_query(call.id, "❌ Suppression annulée.")
    bot.edit_message_text(
        "❌ Suppression annulée.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )


# ══════════════════════════════════════════════════════════════════
# ██  FONCTIONS D'AFFICHAGE RÉUTILISABLES
# ══════════════════════════════════════════════════════════════════

def afficher_profil(message: types.Message):
    """
    Affiche le profil complet de l'utilisateur de manière formatée.
    Propose de le modifier ou de démarrer la collecte si incomplet.
    """
    telegram_id = message.from_user.id
    utilisateur = obtenir_utilisateur(telegram_id)

    if not utilisateur:
        creer_ou_mettre_a_jour_utilisateur(telegram_id, message.from_user.username)
        demarrer_collecte_profil(message)
        return

    if not utilisateur["profil_complet"]:
        bot.send_message(
            telegram_id,
            "⚠️ Votre profil est incomplet.\n"
            "Veuillez renseigner toutes les informations requises."
        )
        demarrer_collecte_profil(message)
        return

    solde = obtenir_solde(telegram_id)

    texte = (
        f"👤 <b>Mon Profil</b>\n\n"
        f"📛 <b>Nom :</b> {utilisateur['nom']}\n"
        f"🏠 <b>Adresse :</b> {utilisateur['adresse']}\n"
        f"📮 <b>Code Postal :</b> {utilisateur['code_postal']}\n"
        f"🏙️ <b>Ville :</b> {utilisateur['ville']}\n"
        f"🗺️ <b>Région :</b> {utilisateur['region']}\n"
        f"🌍 <b>Pays :</b> {utilisateur['pays']}\n"
        f"📱 <b>Téléphone :</b> {utilisateur['telephone']}\n"
        f"📧 <b>Email :</b> {utilisateur['email']}\n\n"
        f"💰 <b>Wallet :</b> {solde:.2f} {DEVISE}\n"
        f"📅 <b>Inscrit le :</b> {utilisateur['date_inscription'][:10]}"
    )

    # Bouton de modification du profil
    clavier = types.InlineKeyboardMarkup()
    clavier.add(
        types.InlineKeyboardButton("✏️ Modifier mon profil", callback_data="modifier_profil")
    )

    bot.send_message(telegram_id, texte, reply_markup=clavier)


@bot.callback_query_handler(func=lambda call: call.data == "modifier_profil")
def callback_modifier_profil(call: types.CallbackQuery):
    """
    Relance la collecte séquentielle du profil pour permettre la modification.
    """
    bot.answer_callback_query(call.id)
    demarrer_collecte_profil(call.message)
    # Redéfinition pour utiliser le bon telegram_id
    definir_etat(call.from_user.id, "profil_0")
    bot.send_message(
        call.from_user.id,
        "✏️ <b>Modification du profil</b>\n\n"
        "Vous allez re-saisir toutes vos informations.\n\n"
        + ETAPES_PROFIL[0][1]
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("info_"))
def callback_info_produit(call: types.CallbackQuery):
    """
    Callback du bouton central du compteur panier (bouton informatif).
    Affiche le nombre d'articles du produit dans le panier.
    """
    telegram_id = call.from_user.id
    produit_id = int(call.data.split("_")[1])
    panier = obtenir_panier(telegram_id)
    panier_dict = {article["id"]: article["quantite"] for article in panier}
    quantite = panier_dict.get(produit_id, 0)

    if quantite > 0:
        bot.answer_callback_query(call.id, f"🛒 {quantite} exemplaire(s) dans votre panier.")
    else:
        bot.answer_callback_query(call.id, "🛒 Ce produit n'est pas encore dans votre panier.")


# ══════════════════════════════════════════════════════════════════
# ██  POINT D'ENTRÉE PRINCIPAL
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         BOT TELEGRAM – BOUTIQUE EN LIGNE v1.0          ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Initialisation de la base de données (création des tables si nécessaire)
    initialiser_base_de_donnees()

    print(f"✅ Base de données '{DB_NAME}' initialisée.")
    print(f"👮 Administrateurs configurés : {ADMIN_IDS}")
    print("🤖 Bot en cours de démarrage...")
    print("   Appuyez sur Ctrl+C pour arrêter.\n")

    # Lancement du bot en mode polling (écoute continue des messages)
    # none_stop=True : redémarre automatiquement en cas d'erreur réseau
    bot.infinity_polling(
        none_stop=True,
        logger_level=logging.INFO,
        timeout=20,
        long_polling_timeout=20
    )
