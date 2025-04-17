# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
import pandas as pd
from datetime import datetime, timedelta
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import numpy as np
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
import pickle
import base64
from collections import Counter
from sklearn.metrics import ndcg_score

_logger = logging.getLogger(__name__)


class FlightRecommendationModel(models.Model):
    _name = 'flight.recommendation.model'
    _description = 'Modèle de recommandation de vols'

    name = fields.Char('Nom du modèle', default='Modèle de recommandation Random Forest', required=True)
    model_data = fields.Binary('Données du modèle', attachment=True)
    encoder_data = fields.Binary('Données de l\'encodeur', attachment=True)
    scaler_data = fields.Binary('Données du normalisateur', attachment=True)
    last_training_date = fields.Datetime('Dernière date d\'entraînement')
    active = fields.Boolean('Actif', default=True)

    # Métriques d'évaluation du modèle
    rf_accuracy = fields.Float('Précision Random Forest', readonly=True)

    # Statistiques du modèle
    training_sample_size = fields.Integer('Taille de l\'échantillon d\'entraînement', readonly=True)
    feature_count = fields.Integer('Nombre de caractéristiques', readonly=True)

    # Configuration
    min_booking_history = fields.Integer('Historique minimum pour personnalisation', default=3,
                                         help="Nombre minimum de réservations nécessaires pour personnaliser les résultats")
    max_history_age_days = fields.Integer('Âge maximum de l\'historique (jours)', default=365,
                                          help="Âge maximum des réservations à prendre en compte")
    num_recommendations = fields.Integer('Nombre de recommandations', default=3,
                                         help="Nombre de vols à marquer comme recommandés")

    def _get_model(self):
        """Récupère le modèle entraîné depuis le champ binary"""
        self.ensure_one()
        if not self.model_data:
            return None

        try:
            model_binary = base64.b64decode(self.model_data)
            model = pickle.loads(model_binary)
            return model
        except Exception as e:
            _logger.error(f"Erreur lors du chargement du modèle: {str(e)}")
            return None

    def _get_encoder(self):
        """Récupère l'encodeur depuis le champ binary"""
        self.ensure_one()
        if not self.encoder_data:
            return None

        try:
            encoder_binary = base64.b64decode(self.encoder_data)
            encoder = pickle.loads(encoder_binary)
            return encoder
        except Exception as e:
            _logger.error(f"Erreur lors du chargement de l'encodeur: {str(e)}")
            return None

    def _get_scaler(self):
        self.ensure_one()
        if not self.scaler_data:
            return None

        try:
            scaler_binary = base64.b64decode(self.scaler_data)
            scaler = pickle.loads(scaler_binary)
            return scaler
        except Exception as e:
            _logger.error(f"Erreur lors du chargement du normalisateur: {str(e)}")
            return None

    @api.model
    def get_active_model(self):
        return self.search([('active', '=', True)], limit=1)

    def sort_flights_by_preference(self, partner_id, flights_data, email=None):
        self.ensure_one()
        _logger.info("Début du tri des vols")

        if not flights_data:
            _logger.warning("Aucun vol à trier")
            return flights_data

        # Vérifier la disponibilité du modèle
        if not self.model_data or not self.encoder_data or not self.scaler_data:
            _logger.warning("Modèle de recommandation non initialisé - entraînement nécessaire")
            try:
                self._train_model()
            except Exception as e:
                _logger.error(f"Échec de l'entraînement automatique: {str(e)}")
                return flights_data

        _logger.info(f"---- DÉBUT DU TRI DES VOLS ----")
        _logger.info(f"Partner ID: {partner_id}, Email: {email}, Nombre de vols: {len(flights_data)}")

        if not flights_data:
            _logger.warning("Aucun vol à trier")
            return flights_data

        # Vérifier si partner_id est valide
        if not partner_id:
            _logger.info("Aucun partner_id fourni, recherche par email")
            if not email:
                _logger.warning("Ni partner_id ni email fourni pour la personnalisation")
                return flights_data

            # Rechercher le partenaire par email
            partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
            if partner:
                partner_id = partner.id
                _logger.info(f"Partenaire trouvé par email: {partner_id}")
            else:
                _logger.warning(f"Aucun partenaire trouvé avec l'email: {email}")
                return flights_data

        # Charger le modèle Random Forest
        rf_model = self._get_model()
        encoder = self._get_encoder()
        scaler = self._get_scaler()

        if not rf_model or not encoder or not scaler:
            _logger.warning("Modèle de recommandation non disponible ou incomplet")
            return flights_data

        # Vérifier l'historique suffisant pour la personnalisation
        bookings_count = self._get_bookings_count(partner_id, email)

        if bookings_count < self.min_booking_history:
            _logger.info(f"Historique insuffisant ({bookings_count} réservations) pour personnalisation")
            # Attribuer un score minimal au lieu de renvoyer directement
            for flight in flights_data:
                flight['recommendation_score'] = 0.1
                flight['is_recommended'] = False

            # Trier les vols par un critère par défaut (par exemple le prix)
            flights_data.sort(key=lambda x: x.get('price', float('inf')))

            # Marquer les meilleurs vols comme recommandés
            top_count = min(self.num_recommendations, len(flights_data))
            for i in range(top_count):
                flights_data[i]['is_recommended'] = True

            return flights_data

        try:
            # Récupérer le profil client
            partner_profile = self._get_partner_profile(partner_id, email)
            _logger.info(f"Profil partenaire récupéré avec succès: {partner_profile}")

            # Définition des catégories
            TIME_CATEGORIES = {
                'morning': (5, 12),
                'afternoon': (12, 17),
                'evening': (17, 22),
                'night': (22, 5)
            }

            DURATION_CATEGORIES = {
                'short': 2,
                'medium': 5,
                'long': float('inf')
            }

            # Traiter chaque vol et calculer son score de personnalisation
            for flight in flights_data:
                try:
                    # Extraction des caractéristiques du vol avec valeurs par défaut
                    airline = self._extract_airline(flight) or "Unknown"
                    departure_date = self._extract_departure_date(flight) or datetime.now()
                    departure_time = self._extract_departure_time(flight) or "12:00"
                    price = self._extract_price(flight) or partner_profile.get('avg_price', 500)
                    is_direct = self._extract_is_direct(flight) if self._extract_is_direct(flight) is not None else True
                    duration_hours = self._extract_duration(flight) or 2.0

                    # Déterminer la catégorie de l'heure de départ
                    departure_hour = self._extract_hour_from_time(departure_time)
                    _logger.debug(f"Heure de départ extraite: {departure_hour}")

                    # Attribution de la catégorie d'heure
                    if 5 <= departure_hour < 12:
                        time_category = 'morning'
                    elif 12 <= departure_hour < 17:
                        time_category = 'afternoon'
                    elif 17 <= departure_hour < 22:
                        time_category = 'evening'
                    else:
                        time_category = 'night'
                    _logger.debug(f"Catégorie d'heure: {time_category}")

                    # Déterminer la catégorie de durée
                    if duration_hours < DURATION_CATEGORIES['short']:
                        duration_category = 'short'
                    elif duration_hours <= DURATION_CATEGORIES['medium']:
                        duration_category = 'medium'
                    else:
                        duration_category = 'long'
                    _logger.debug(f"Catégorie de durée: {duration_category}")

                    # Déterminer la catégorie de prix
                    if price < partner_profile.get('avg_price', 500) * 0.8:
                        price_category = 'low'
                    elif price > partner_profile.get('avg_price', 500) * 1.2:
                        price_category = 'high'
                    else:
                        price_category = 'medium'
                    _logger.debug(f"Catégorie de prix: {price_category}")

                    # Construire l'objet de caractéristiques du vol
                    flight_features = {
                        'airline': airline,
                        'price': price,
                        'day_of_week': departure_date.weekday(),
                        'month_of_year': departure_date.month,
                        'seat_preference': 'window',  # Valeur par défaut
                        'meal_preference': 'regular',  # Valeur par défaut
                        'is_direct': is_direct
                    }

                    _logger.info(
                        f"Caractéristiques extraites pour vol {flight.get('flightNumber', 'N/A')}: {flight_features}")

                    # Encoder et normaliser les caractéristiques
                    categorical_df = pd.DataFrame({
                        'airline': [flight_features['airline']],
                        'seat_preference': [flight_features['seat_preference']],
                        'meal_preference': [flight_features['meal_preference']],
                        'day_of_week': [flight_features['day_of_week']],
                        'month_of_year': [flight_features['month_of_year']],
                    })

                    # Vérifier si les valeurs existent dans les catégories de l'encodeur
                    try:
                        categorical_encoded = encoder.transform(categorical_df)
                    except ValueError as e:
                        _logger.warning(
                            f"Erreur d'encodage des catégories: {str(e)}. Utilisation de valeurs sécurisées.")
                        # Remplacer les valeurs inconnues par des valeurs connues
                        for col in categorical_df.columns:
                            if col in encoder.feature_names_in_:
                                categories = encoder.categories_[list(encoder.feature_names_in_).index(col)]
                                if categorical_df[col].iloc[0] not in categories:
                                    _logger.warning(f"Catégorie inconnue pour {col}: {categorical_df[col].iloc[0]}")
                                    categorical_df.loc[0, col] = categories[0]  # Utiliser la première catégorie connue
                        categorical_encoded = encoder.transform(categorical_df)

                    numerical_df = pd.DataFrame({
                        'price': [flight_features['price']]
                    })
                    numerical_scaled = scaler.transform(numerical_df)

                    # Ajouter les caractéristiques binaires
                    binary_features = np.array([[int(flight_features['is_direct'])]])

                    # Combiner les caractéristiques
                    features = np.hstack((categorical_encoded, numerical_scaled, binary_features))

                    # Calculer le score avec Random Forest
                    # CORRECTION: Utiliser predict au lieu de predict_proba pour les modèles de régression
                    final_score = 0
                    try:
                        # Vérifier si c'est un modèle de classification ou de régression
                        if hasattr(rf_model, 'predict_proba'):
                            # C'est un modèle de classification
                            proba = rf_model.predict_proba(features)
                            if proba.shape[1] > 1:  # Multi-classe
                                rf_score = proba[0][1] if proba.shape[1] == 2 else np.max(proba[0])
                            else:
                                rf_score = proba[0][0]
                        else:
                            # C'est un modèle de régression
                            rf_prediction = rf_model.predict(features)[0]
                            # Normaliser entre 0 et 1 si nécessaire
                            rf_score = max(0, min(1, rf_prediction))

                        # S'assurer que rf_score est un float
                        rf_score = float(rf_score)
                        rf_contribution = rf_score * 0.3  # 30% du score total
                        _logger.info(f"Score RF: {rf_score}, contribution: {rf_contribution}")
                        final_score = rf_contribution
                    except Exception as e:
                        _logger.error(f"Erreur lors du calcul du score Random Forest: {str(e)}")
                        rf_score = 0.5  # Valeur par défaut neutre
                        final_score = rf_score * 0.3

                    # Score de la compagnie aérienne (25% du score total)
                    airline_score = 0
                    if 'preferred_airlines' in partner_profile and airline in partner_profile.get('preferred_airlines',
                                                                                                  []):
                        position = partner_profile['preferred_airlines'].index(airline)
                        max_position = len(partner_profile['preferred_airlines']) - 1
                        if max_position > 0:
                            airline_score = 0.25 * (1 - position / max_position)
                        else:
                            airline_score = 0.25
                    _logger.info(f"Score compagnie aérienne: {airline_score:.2f} pour {airline}")
                    final_score += airline_score

                    # Score du prix (25% du score total)
                    price_score = 0
                    if 'preferred_price_categories' in partner_profile and price_category in partner_profile.get(
                            'preferred_price_categories', []):
                        position = partner_profile['preferred_price_categories'].index(price_category)
                        max_position = len(partner_profile['preferred_price_categories']) - 1
                        if max_position > 0:
                            price_score = 0.25 * (1 - position / max_position)
                        else:
                            price_score = 0.25

                    avg_price = partner_profile.get('avg_price',
                                                    price)  # Utiliser le prix actuel comme référence si aucune moyenne
                    if avg_price > 0:
                        price_ratio = price / avg_price
                        if price_ratio < 0.8:
                            price_score += 0.1
                        elif price_ratio > 1.3:
                            price_score -= 0.1

                    price_score = max(0, min(0.25, price_score))
                    _logger.info(f"Score prix: {price_score:.2f} pour {price_category} (ratio: {price_ratio:.2f})")
                    final_score += price_score

                    # Score de la durée (20% du score total)
                    duration_score = 0
                    if 'preferred_durations' in partner_profile and duration_category in partner_profile.get(
                            'preferred_durations', []):
                        position = partner_profile['preferred_durations'].index(duration_category)
                        max_position = len(partner_profile['preferred_durations']) - 1
                        if max_position > 0:
                            duration_score = 0.20 * (1 - position / max_position)
                        else:
                            duration_score = 0.20

                    if is_direct and partner_profile.get('prefers_direct', True):
                        duration_score += 0.05

                    duration_score = max(0, min(0.20, duration_score))
                    _logger.info(f"Score durée: {duration_score:.2f} pour {duration_category} (direct: {is_direct})")
                    final_score += duration_score

                    # Score de l'heure de départ (15% du score total)
                    time_score = 0
                    if 'preferred_departure_times' in partner_profile and time_category in partner_profile.get(
                            'preferred_departure_times', []):
                        position = partner_profile['preferred_departure_times'].index(time_category)
                        max_position = len(partner_profile['preferred_departure_times']) - 1
                        if max_position > 0:
                            time_score = 0.15 * (1 - position / max_position)
                        else:
                            time_score = 0.15

                    _logger.info(f"Score heure de départ: {time_score:.2f} pour {time_category}")
                    final_score += time_score

                    # Facteurs secondaires
                    day_adjustment = 0
                    day_of_week = flight_features['day_of_week']
                    if 'preferred_days' in partner_profile and day_of_week in partner_profile.get('preferred_days', []):
                        position = partner_profile['preferred_days'].index(day_of_week)
                        max_position = len(partner_profile['preferred_days']) - 1
                        if max_position > 0:
                            day_adjustment = 0.05 * (1 - position / max_position)
                        else:
                            day_adjustment = 0.05
                    _logger.info(f"Ajustement jour: {day_adjustment:.2f} pour jour {day_of_week}")
                    final_score += day_adjustment

                    # S'assurer que le score n'est jamais zéro
                    if final_score <= 0:
                        final_score = 0.01  # Score minimal pour éviter les zéros

                    # Ajouter le score final au vol
                    flight['recommendation_score'] = final_score
                    _logger.info(f"Score final calculé: {final_score:.4f} pour vol {flight.get('flightNumber', 'N/A')}")

                    # Détail des composantes du score
                    flight['score_components'] = {
                        'rf': rf_score * 0.3,
                        'airline': airline_score,
                        'price': price_score,
                        'duration': duration_score,
                        'departure_time': time_score,
                        'day_adjustment': day_adjustment
                    }

                except Exception as e:
                    _logger.error(f"Erreur lors du traitement d'un vol: {str(e)}")
                    flight['recommendation_score'] = 0.01  # Score minimal pour éviter les zéros
                    flight['is_recommended'] = False

            # Trier les vols par score de recommandation
            flights_data.sort(key=lambda x: x.get('recommendation_score', 0), reverse=True)

            # Marquer les meilleurs vols comme recommandés
            if flights_data:
                top_count = min(self.num_recommendations, len(flights_data))
                for i in range(top_count):
                    flights_data[i]['is_recommended'] = True
                    _logger.info(
                        f"Vol marqué comme recommandé: {flights_data[i].get('flightNumber', 'N/A')} avec score {flights_data[i].get('recommendation_score', 0):.4f}")

                for i in range(top_count, len(flights_data)):
                    flights_data[i]['is_recommended'] = False

            _logger.info(f"Vols triés par préférence pour le partenaire {partner_id}")
            _logger.info(f"---- FIN DU TRI DES VOLS ----")
            return flights_data

        except Exception as e:
            _logger.error(f"Erreur lors du tri des vols par préférence: {str(e)}")
            # En cas d'erreur, renvoyer les vols sans tri particulier
            for flight in flights_data:
                if 'recommendation_score' not in flight:
                    flight['recommendation_score'] = 0.01
                if 'is_recommended' not in flight:
                    flight['is_recommended'] = False

            return flights_data
    # Les méthodes d'extraction (_extract_*) restent identiques à votre code original

    def _train_model(self):
        self.ensure_one()
        _logger.info("Début de l'entraînement du modèle Random Forest")

        # Récupérer les données historiques
        bookings = self.env['booking'].search([
            ('state', '=', 'confirmed'),
            ('create_date', '>=', fields.Datetime.now() - timedelta(days=self.max_history_age_days))
        ])

        _logger.info(f"Nombre de réservations récupérées pour l'entraînement: {len(bookings)}")

        if not bookings or len(bookings) < 10:
            _logger.warning(
                f"Pas suffisamment de données pour entraîner le modèle: {len(bookings)} réservations trouvées")
            return False

        # Transformer les données en DataFrame
        data = []
        for booking in bookings:
            data.append({
                'partner_id': booking.partner_id.id,
                'airline': booking.airline,
                'flight_number': booking.flight_number,
                'departure_date': booking.departure_date,
                'departure_time': booking.departure_time,
                'arrival_date': booking.arrival_date,
                'arrival_time': booking.arrival_time,
                'price': booking.price,
                'seat_preference': booking.seat_preference,
                'meal_preference': booking.meal_preference,
                'day_of_week': booking.departure_date.weekday() if booking.departure_date else 0,
                'month_of_year': booking.departure_date.month if booking.departure_date else 1,
                'is_direct': booking.is_direct if hasattr(booking, 'is_direct') else True,
            })

        df = pd.DataFrame(data)
        _logger.info(f"DataFrame créé avec {len(df)} lignes et {len(df.columns)} colonnes")

        # Préparation des caractéristiques
        categorical_features = ['airline', 'seat_preference', 'meal_preference', 'day_of_week', 'month_of_year']
        numerical_features = ['price']
        binary_features = ['is_direct']

        # Vérifier et compléter les features manquants
        for feature in categorical_features + numerical_features + binary_features:
            if feature not in df.columns:
                _logger.warning(f"Caractéristique manquante: {feature}")
                if feature in categorical_features:
                    df[feature] = 'unknown'
                elif feature == 'price':
                    df[feature] = df['price'].mean() if 'price' in df else 0.0
                else:
                    df[feature] = False if feature == 'is_direct' else 0

        # Encoder les variables catégorielles
        encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
        categorical_encoded = encoder.fit_transform(df[categorical_features])
        _logger.info(f"Encodage terminé: {categorical_encoded.shape} caractéristiques catégorielles encodées")

        # Normaliser les variables numériques
        scaler = StandardScaler()
        numerical_scaled = scaler.fit_transform(df[numerical_features])
        _logger.info(f"Normalisation terminée: {numerical_scaled.shape} caractéristiques numériques normalisées")

        # Ajouter les variables binaires
        binary_data = df[binary_features].values if binary_features and all(
            f in df.columns for f in binary_features) else np.array([]).reshape(len(df), 0)
        _logger.info(f"Variables binaires: {binary_data.shape}")

        # Combiner toutes les caractéristiques
        features = np.hstack((categorical_encoded, numerical_scaled, binary_data))
        _logger.info(f"Matrice de caractéristiques combinées: {features.shape}")

        # Créer une cible synthétique basée sur les préférences utilisateur
        # Nous allons créer plusieurs cibles pour évaluer différentes facettes

        # 1. Cible basée sur le prix (classification)
        if df['price'].nunique() >= 5:
            price_target = pd.qcut(df['price'], 5, labels=False, duplicates='drop')
        else:
            price_median = df['price'].median()
            price_target = (df['price'] > price_median).astype(int)

        # 2. Cible basée sur la compagnie aérienne préférée par utilisateur
        airline_counts = df.groupby(['partner_id', 'airline']).size().reset_index(name='count')
        preferred_airlines = airline_counts.sort_values(['partner_id', 'count'], ascending=[True, False]) \
            .drop_duplicates('partner_id')
        airline_mapping = dict(zip(preferred_airlines['partner_id'], preferred_airlines.index))
        airline_target = df['partner_id'].map(airline_mapping).fillna(0).astype(int)

        # 3. Cible basée sur préférence horaire (matin/soir)
        if 'departure_time' in df.columns:
            departure_hours = []
            for time_str in df['departure_time']:
                try:
                    if isinstance(time_str, str) and ':' in time_str:
                        departure_hours.append(int(time_str.split(':')[0]))
                    elif hasattr(time_str, 'hour'):
                        departure_hours.append(time_str.hour)
                    else:
                        departure_hours.append(12)
                except:
                    departure_hours.append(12)

            df['departure_hour'] = departure_hours
            time_target = pd.cut(df['departure_hour'],
                                 [0, 6, 12, 18, 24],
                                 labels=[0, 1, 2, 3],
                                 include_lowest=True)
        else:
            time_target = np.zeros(len(df))

        # Créer une cible globale combinée
        # Nous allons utiliser une approche de régression avec un score de pertinence
        relevance_scores = []

        # Grouper par partenaire pour calculer les scores de pertinence
        for partner_id, partner_df in df.groupby('partner_id'):
            if len(partner_df) < 2:
                for _ in range(len(partner_df)):
                    relevance_scores.append(1)  # Score neutre
                continue

            # Calculer les préférences par compagnie aérienne
            airline_counts = partner_df['airline'].value_counts()
            max_count = airline_counts.max()

            # Calculer les scores pour chaque réservation de ce partenaire
            for _, row in partner_df.iterrows():
                score = 0

                # Score basé sur la fréquence de la compagnie aérienne
                airline_score = airline_counts.get(row['airline'], 0) / max_count if max_count > 0 else 0

                # Score basé sur le prix (inversement proportionnel)
                avg_price = partner_df['price'].mean()
                price_score = 0
                if avg_price > 0:
                    ratio = row['price'] / avg_price
                    if ratio <= 0.8:
                        price_score = 1.0  # Bon prix
                    elif ratio <= 1.0:
                        price_score = 0.8  # Prix moyen
                    elif ratio <= 1.2:
                        price_score = 0.6  # Prix un peu élevé
                    else:
                        price_score = 0.4  # Prix élevé

                # Score combiné (avec plus de poids sur le prix)
                score = 0.4 * airline_score + 0.6 * price_score
                relevance_scores.append(score)

        relevance_target = np.array(relevance_scores)

        # Créer et entraîner le modèle Random Forest
        rf_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1  # Utiliser tous les cœurs disponibles
        )

        rf_model.fit(features, relevance_target)
        _logger.info("Modèle Random Forest entraîné avec succès")

        # Évaluer le modèle
        evaluation_metrics = self._evaluate_model(df, features, rf_model)

        _logger.info(f"Métriques d'évaluation: {evaluation_metrics}")

        # Sauvegarder le modèle
        rf_binary = pickle.dumps(rf_model)
        encoder_binary = pickle.dumps(encoder)
        scaler_binary = pickle.dumps(scaler)

        self.write({
            'model_data': base64.b64encode(rf_binary),
            'encoder_data': base64.b64encode(encoder_binary),
            'scaler_data': base64.b64encode(scaler_binary),
            'last_training_date': fields.Datetime.now(),
            'training_sample_size': len(df),
            'feature_count': features.shape[1],
            'rf_accuracy': evaluation_metrics.get('rf_accuracy', 0.5)
        })

        _logger.info(f"Modèle entraîné avec succès sur {len(df)} exemples")
        return True

    def _evaluate_model(self, df, features, model=None):
        _logger.info("Début de l'évaluation du modèle")

        metrics = {
            'rf_accuracy': 0.5,
            'rf_precision': 0.5,
            'rf_recall': 0.5,
            'rf_f1': 0.5,
            'ndcg_score': 0.0,
            'map_score': 0.0,
            'precision_at_k': {},
            'recall_at_k': {},
            'f1_at_k': {}
        }

        try:
            # Créer une cible de pertinence synthétique
            relevance_scores = []
            for partner_id, partner_df in df.groupby('partner_id'):
                if len(partner_df) < 2:
                    for _ in range(len(partner_df)):
                        relevance_scores.append(1)
                    continue

                airline_counts = partner_df['airline'].value_counts()
                max_count = airline_counts.max()

                for _, row in partner_df.iterrows():
                    airline_score = airline_counts.get(row['airline'], 0) / max_count if max_count > 0 else 0

                    avg_price = partner_df['price'].mean()
                    price_score = 0
                    if avg_price > 0:
                        ratio = row['price'] / avg_price
                        if ratio <= 0.8:
                            price_score = 1.0
                        elif ratio <= 1.0:
                            price_score = 0.8
                        elif ratio <= 1.2:
                            price_score = 0.6
                        else:
                            price_score = 0.4

                    score = 0.4 * airline_score + 0.6 * price_score
                    relevance_scores.append(score)

            relevance_target = np.array(relevance_scores)

            # Division en ensembles d'entraînement et de test
            X_train, X_test, y_train, y_test = train_test_split(
                features, relevance_target, test_size=0.3, random_state=42
            )

            # Entraîner un nouveau modèle pour l'évaluation
            eval_model = RandomForestRegressor(
                n_estimators=50,
                max_depth=8,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            )
            eval_model.fit(X_train, y_train)

            # Prédire les scores pour l'ensemble de test
            y_pred = eval_model.predict(X_test)

            # Calculer R² score
            from sklearn.metrics import r2_score
            metrics['rf_r2'] = r2_score(y_test, y_pred)

            # Calculer MAE et RMSE
            from sklearn.metrics import mean_absolute_error, mean_squared_error
            metrics['rf_mae'] = mean_absolute_error(y_test, y_pred)
            metrics['rf_rmse'] = np.sqrt(mean_squared_error(y_test, y_pred))

            # Calculer NDCG (si nous avons les IDs des partenaires)
            partner_ids_test = df.iloc[X_test.shape[0]:].reset_index(drop=True)['partner_id'].values

            if len(partner_ids_test) == len(y_test):
                unique_partners = np.unique(partner_ids_test)
                ndcg_scores = []
                map_scores = []

                k_values = [1, 3, 5, 10]
                for k in k_values:
                    metrics['precision_at_k'][k] = []
                    metrics['recall_at_k'][k] = []
                    metrics['f1_at_k'][k] = []

                for partner in unique_partners:
                    partner_mask = partner_ids_test == partner
                    if np.sum(partner_mask) > 1:
                        try:
                            partner_y_true = y_test[partner_mask].reshape(1, -1)
                            partner_y_pred = y_pred[partner_mask].reshape(1, -1)

                            # NDCG@k
                            k = min(5, len(partner_y_true[0]))
                            partner_ndcg = ndcg_score(partner_y_true, partner_y_pred, k=k)
                            ndcg_scores.append(partner_ndcg)

                            # Calculer precision@K, recall@K et F1@K
                            for k_val in k_values:
                                if k_val <= len(partner_y_true[0]):
                                    true_top_k_indices = np.argsort(-partner_y_true[0])[:k_val]
                                    pred_top_k_indices = np.argsort(-partner_y_pred[0])[:k_val]

                                    true_top_k_set = set(true_top_k_indices)
                                    pred_top_k_set = set(pred_top_k_indices)

                                    if len(pred_top_k_set) > 0:
                                        precision_k = len(true_top_k_set.intersection(pred_top_k_set)) / len(
                                            pred_top_k_set)
                                        metrics['precision_at_k'][k_val].append(precision_k)

                                    if len(true_top_k_set) > 0:
                                        recall_k = len(true_top_k_set.intersection(pred_top_k_set)) / len(
                                            true_top_k_set)
                                        metrics['recall_at_k'][k_val].append(recall_k)

                                    if precision_k + recall_k > 0:
                                        f1_k = 2 * precision_k * recall_k / (precision_k + recall_k)
                                        metrics['f1_at_k'][k_val].append(f1_k)

                            # MAP
                            true_ranks = np.argsort(-partner_y_true[0])
                            pred_ranks = np.argsort(-partner_y_pred[0])
                            ap = self._average_precision(true_ranks, pred_ranks)
                            map_scores.append(ap)
                        except Exception as e:
                            _logger.error(f"Erreur lors du calcul des métriques pour partenaire {partner}: {str(e)}")

                if ndcg_scores:
                    metrics['ndcg_score'] = np.mean(ndcg_scores)
                if map_scores:
                    metrics['map_score'] = np.mean(map_scores)

                for k in k_values:
                    if metrics['precision_at_k'][k]:
                        avg_precision_k = np.mean(metrics['precision_at_k'][k])
                        metrics['precision_at_k'][k] = avg_precision_k
                    else:
                        metrics['precision_at_k'][k] = 0.0

                    if metrics['recall_at_k'][k]:
                        avg_recall_k = np.mean(metrics['recall_at_k'][k])
                        metrics['recall_at_k'][k] = avg_recall_k
                    else:
                        metrics['recall_at_k'][k] = 0.0

                    if metrics['f1_at_k'][k]:
                        avg_f1_k = np.mean(metrics['f1_at_k'][k])
                        metrics['f1_at_k'][k] = avg_f1_k
                    else:
                        metrics['f1_at_k'][k] = 0.0

            # Score global basé sur les différentes métriques
            metrics['rf_accuracy'] = 0.5 * metrics.get('rf_r2', 0) + 0.3 * metrics.get('ndcg_score', 0) + 0.2 * (
                        1 - metrics.get('rf_mae', 1))

        except Exception as e:
            _logger.error(f"Erreur lors de l'évaluation du modèle: {str(e)}")

        _logger.info(f"Évaluation du modèle terminée: {metrics}")
        return metrics

    # Les autres méthodes restent identiques à votre code original
    # (_extract_*, _get_bookings_count, _get_partner_profile, etc.)
    def _get_bookings_count(self, partner_id, email=None):
        if isinstance(partner_id, list):
            partner_ids = partner_id
        else:
            partner_ids = [partner_id]

        bookings_count = self.env['booking'].search_count([
            ('partner_id', 'in', partner_ids),
            ('state', '=', 'confirmed')
        ])

        # Si pas assez d'historique avec partner_id, essayer avec email
        if bookings_count < self.min_booking_history and email:
            # Chercher d'autres partenaires avec le même email
            other_partners = self.env['res.partner'].search([
                ('email', '=', email),
                ('id', 'not in', partner_ids)
            ])

            if other_partners:
                other_partner_ids = other_partners.ids
                additional_bookings_count = self.env['booking'].search_count([
                    ('partner_id', 'in', other_partner_ids),
                    ('state', '=', 'confirmed')
                ])

                bookings_count += additional_bookings_count

                # Mettre à jour la liste des partenaires pour l'analyse des préférences
                partner_ids.extend(other_partner_ids)

        return bookings_count

    def _average_precision(self, true_ranks, pred_ranks, k=None):
        if k is None:
            k = len(true_ranks)
        else:
            k = min(k, len(true_ranks))

        # On s'intéresse aux k premiers éléments prédits
        top_k_pred = pred_ranks[:k]

        # Calculer la précision à chaque position
        precisions = []
        num_relevant = 0

        for i, item_rank in enumerate(top_k_pred):
            # Un élément est pertinent s'il est dans les premiers rangs réels
            is_relevant = item_rank in true_ranks[:k]

            if is_relevant:
                num_relevant += 1
                # Précision@i: nombre d'éléments pertinents jusqu'à la position i / i
                precisions.append(num_relevant / (i + 1))

        # AP est la moyenne des précisions aux positions pertinentes
        return np.mean(precisions) if precisions else 0.0
    def _get_partner_profile(self, partner_id, email=None):
        # Gérer le cas où partner_id est une liste
        if isinstance(partner_id, list):
            partner_ids = partner_id
        else:
            partner_ids = [partner_id]

        # Si email est fourni, ajouter les autres partenaires avec le même email
        if email:
            other_partners = self.env['res.partner'].search([
                ('email', '=', email),
                ('id', 'not in', partner_ids)
            ])
            if other_partners:
                partner_ids.extend(other_partners.ids)

        # Récupérer les réservations confirmées du/des client(s)
        domain = [
            ('partner_id', 'in', partner_ids),
            ('state', '=', 'confirmed'),
            ('create_date', '>=', fields.Datetime.now() - timedelta(days=self.max_history_age_days))
        ]

        bookings = self.env['booking'].search(domain, limit=50)

        # Analyser l'historique pour extraire les préférences
        airlines = []
        price_points = []
        is_direct_list = []
        departure_times = []  # Pour les préférences d'horaire
        durations = []  # Pour les préférences de durée

        # Catégories de temps
        MORNING = 'morning'  # 5h-12h
        AFTERNOON = 'afternoon'  # 12h-17h
        EVENING = 'evening'  # 17h-22h
        NIGHT = 'night'  # 22h-5h

        # Catégories de prix
        LOW = 'low'
        MEDIUM = 'medium'
        HIGH = 'high'

        # Catégories de durée
        SHORT = 'short'  # < 2h
        MEDIUM_DURATION = 'medium'  # 2h-5h
        LONG = 'long'  # > 5h

        # Collecter les données des réservations passées
        for booking in bookings:
            airlines.append(booking.airline)
            price_points.append(booking.price)

            if hasattr(booking, 'is_direct'):
                is_direct_list.append(booking.is_direct)

            # Extraire l'heure de départ et la catégoriser
            if booking.departure_time:
                departure_hour = self._extract_hour_from_time(booking.departure_time)

                # Catégoriser l'heure de départ
                if 5 <= departure_hour < 12:
                    departure_times.append(MORNING)
                elif 12 <= departure_hour < 17:
                    departure_times.append(AFTERNOON)
                elif 17 <= departure_hour < 22:
                    departure_times.append(EVENING)
                else:
                    departure_times.append(NIGHT)

            # Extraire la durée de vol et la catégoriser
            if hasattr(booking, 'duration'):
                duration_hours = self._extract_duration_in_hours(booking.duration)

                # Catégoriser la durée
                if duration_hours < 2:
                    durations.append(SHORT)
                elif 2 <= duration_hours <= 5:
                    durations.append(MEDIUM_DURATION)
                else:
                    durations.append(LONG)

        # Calculer la moyenne des prix pour catégoriser les préférences de prix
        avg_price = sum(price_points) / len(price_points) if price_points else 0

        # Catégoriser les réservations précédentes par niveau de prix
        price_categories = []
        for price in price_points:
            if price < avg_price * 0.8:
                price_categories.append(LOW)
            elif price > avg_price * 1.2:
                price_categories.append(HIGH)
            else:
                price_categories.append(MEDIUM)

        # Créer des listes ordonnées
        # Créer des listes ordonnées de préférences
        profile = {
                    'preferred_airlines': self._get_ordered_preferences(airlines),
                    'avg_price': avg_price,
                    'preferred_price_categories': self._get_ordered_preferences(price_categories),
                    'preferred_departure_times': self._get_ordered_preferences(departure_times),
                    'preferred_durations': self._get_ordered_preferences(durations),
                    'prefers_direct': sum(is_direct_list) / len(is_direct_list) > 0.5 if is_direct_list else True
                    # Majorité
                }

        return profile
    def _extract_hour_from_time(self, time_str):
                try:
                    # Pour les formats comme "14:30:00" ou "14:30"
                    if isinstance(time_str, str) and ':' in time_str:
                        return int(time_str.split(':')[0])

                    # Pour les objets datetime
                    elif hasattr(time_str, 'hour'):
                        return time_str.hour

                    # Pour les formats numériques (float ou int)
                    elif isinstance(time_str, (int, float)):
                        return int(time_str)

                except (ValueError, AttributeError, IndexError):
                    pass

                # Valeur par défaut
                return 12  # Midi par défaut

    def _extract_duration_in_hours(self, duration):

                try:
                    # Si c'est déjà un nombre
                    if isinstance(duration, (int, float)):
                        return float(duration)

                    # Format "2h30m" ou "2h 30m"
                    elif isinstance(duration, str):
                        hours = 0
                        minutes = 0

                        # Extraire les heures
                        if 'h' in duration:
                            hours_part = duration.split('h')[0].strip()
                            hours = float(hours_part) if hours_part else 0

                        # Extraire les minutes
                        if 'm' in duration:
                            if 'h' in duration:
                                minutes_part = duration.split('h')[1].split('m')[0].strip()
                            else:
                                minutes_part = duration.split('m')[0].strip()
                            minutes = float(minutes_part) if minutes_part else 0

                        return hours + (minutes / 60)

                except (ValueError, IndexError):
                    pass

                # Valeur par défaut
                return 2.0  # 2 heures par défaut

    def _get_ordered_preferences(self, lst):
                if not lst:
                    return []

                # Utiliser Counter pour compter les occurrences
                counter = Counter(lst)

                # Trier par fréquence décroissante
                ordered_items = [item for item, count in counter.most_common()]

                return ordered_items
