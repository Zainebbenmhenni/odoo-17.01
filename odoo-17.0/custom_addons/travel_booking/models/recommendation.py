# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
import pandas as pd
from datetime import datetime, timedelta
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import numpy as np
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.neighbors import NearestNeighbors
from sklearn.model_selection import train_test_split
import pickle
import base64
from collections import Counter

_logger = logging.getLogger(__name__)


class FlightRecommendationModel(models.Model):
    _name = 'flight.recommendation.model'
    _description = 'Modèle de recommandation de vols'

    name = fields.Char('Nom du modèle', default='Modèle de recommandation KNN', required=True)
    model_data = fields.Binary('Données du modèle', attachment=True)
    encoder_data = fields.Binary('Données de l\'encodeur', attachment=True)
    scaler_data = fields.Binary('Données du normalisateur', attachment=True)
    last_training_date = fields.Datetime('Dernière date d\'entraînement')
    active = fields.Boolean('Actif', default=True)

    # Métriques d'évaluation du modèle
    knn_accuracy = fields.Float('Précision KNN', readonly=True)

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
            # Option: lancer un entraînement automatique ici
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

        # Charger le modèle KNN
        knn_model = self._get_model()
        encoder = self._get_encoder()
        scaler = self._get_scaler()

        if not knn_model or not encoder or not scaler:
            _logger.warning("Modèle de recommandation non disponible ou incomplet")
            return flights_data

        # Vérifier l'historique suffisant pour la personnalisation
        bookings_count = self._get_bookings_count(partner_id, email)

        if bookings_count < self.min_booking_history:
            _logger.info(f"Historique insuffisant ({bookings_count} réservations) pour personnalisation")
            return flights_data

        try:
            # Récupérer le profil client (avec les préférences ordonnées)
            partner_profile = self._get_partner_profile(partner_id, email)
            _logger.info(f"Profil partenaire: {partner_profile}")

            # Définition des catégories
            TIME_CATEGORIES = {
                'morning': (5, 12),  # 5h-12h
                'afternoon': (12, 17),  # 12h-17h
                'evening': (17, 22),  # 17h-22h
                'night': (22, 5)  # 22h-5h
            }

            DURATION_CATEGORIES = {
                'short': 2,  # < 2h
                'medium': 5,  # <= 5h
                'long': float('inf')  # > 5h
            }

            # Traiter chaque vol et calculer son score de personnalisation
            for flight in flights_data:
                try:
                    # Extraction adaptée à la structure de données de l'API
                    airline = self._extract_airline(flight)
                    departure_date = self._extract_departure_date(flight)
                    departure_time = self._extract_departure_time(flight)
                    price = self._extract_price(flight)
                    is_direct = self._extract_is_direct(flight)
                    duration_hours = self._extract_duration(flight)

                    # Déterminer la catégorie de l'heure de départ
                    departure_hour = self._extract_hour_from_time(departure_time)

                    # Attribution de la catégorie d'heure
                    if 5 <= departure_hour < 12:
                        time_category = 'morning'
                    elif 12 <= departure_hour < 17:
                        time_category = 'afternoon'
                    elif 17 <= departure_hour < 22:
                        time_category = 'evening'
                    else:
                        time_category = 'night'

                    # Déterminer la catégorie de durée
                    if duration_hours < DURATION_CATEGORIES['short']:
                        duration_category = 'short'
                    elif duration_hours <= DURATION_CATEGORIES['medium']:
                        duration_category = 'medium'
                    else:
                        duration_category = 'long'

                    # Déterminer la catégorie de prix
                    if price < partner_profile['avg_price'] * 0.8:
                        price_category = 'low'
                    elif price > partner_profile['avg_price'] * 1.2:
                        price_category = 'high'
                    else:
                        price_category = 'medium'

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

                    try:
                        categorical_encoded = encoder.transform(categorical_df)
                    except ValueError as e:
                        _logger.warning(
                            f"Erreur d'encodage des catégories: {str(e)}. Utilisation de la méthode alternative.")
                        # Gestion des nouvelles catégories (non vues pendant l'entraînement)
                        # Remplacer par des valeurs connues puis encoder
                        for col in categorical_df.columns:
                            if col in encoder.feature_names_in_:
                                categories = encoder.categories_[list(encoder.feature_names_in_).index(col)]
                                if categorical_df[col][0] not in categories:
                                    # Remplacer par la catégorie la plus commune dans nos données d'entraînement
                                    categorical_df[col][0] = categories[0]
                        categorical_encoded = encoder.transform(categorical_df)

                    numerical_df = pd.DataFrame({
                        'price': [flight_features['price']]
                    })
                    numerical_scaled = scaler.transform(numerical_df)

                    # Ajouter les caractéristiques binaires
                    binary_features = np.array([[int(flight_features['is_direct'])]])

                    # Combiner les caractéristiques
                    features = np.hstack((categorical_encoded, numerical_scaled, binary_features))

                    # Calculer le score KNN
                    try:
                        distances, _ = knn_model.kneighbors(features)
                        knn_score = 1.0 / (1.0 + np.mean(distances[0]))

                        # Score initial basé sur KNN mais avec un poids réduit pour équilibrer avec les autres facteurs
                        final_score = knn_score * 0.2  # 20% du score total
                    except Exception as e:
                        _logger.error(f"Erreur lors du calcul du score KNN: {str(e)}")
                        final_score = 0

                    # Nouvelle distribution des scores pour mieux équilibrer les facteurs clés
                    # 1. Score de la compagnie aérienne (25% du score total)
                    airline_score = 0
                    if airline in partner_profile.get('preferred_airlines', []):
                        position = partner_profile['preferred_airlines'].index(airline)
                        max_position = len(partner_profile['preferred_airlines']) - 1
                        if max_position > 0:  # Éviter division par zéro
                            airline_score = 0.35 * (1 - position / max_position)
                        else:
                            airline_score = 0.35
                    _logger.info(f"Score compagnie aérienne: {airline_score:.2f} pour {airline}")
                    final_score += airline_score

                    # 2. Score du prix (25% du score total)
                    price_score = 0
                    if 'preferred_price_categories' in partner_profile and price_category in partner_profile[
                        'preferred_price_categories']:
                        position = partner_profile['preferred_price_categories'].index(price_category)
                        max_position = len(partner_profile['preferred_price_categories']) - 1
                        if max_position > 0:  # Éviter division par zéro
                            price_score = 0.30 * (1 - position / max_position)
                        else:
                            price_score = 0.30
                    # Ajustement supplémentaire basé sur le rapport de prix
                    price_ratio = price / partner_profile['avg_price'] if partner_profile['avg_price'] > 0 else 1
                    if price_ratio < 0.8:
                        price_score += 0.1  # Bonus pour les prix très bas
                    elif price_ratio > 1.3:
                        price_score -= 0.1  # Pénalité pour les prix très élevés

                    price_score = max(0, min(0.30, price_score))  # Limiter à 25%
                    _logger.info(f"Score prix: {price_score:.2f} pour {price_category} (ratio: {price_ratio:.2f})")
                    final_score += price_score

                    # 3. Score de la durée (25% du score total)
                    duration_score = 0
                    if 'preferred_durations' in partner_profile and duration_category in partner_profile[
                        'preferred_durations']:
                        position = partner_profile['preferred_durations'].index(duration_category)
                        max_position = len(partner_profile['preferred_durations']) - 1
                        if max_position > 0:  # Éviter division par zéro
                            duration_score = 0.20 * (1 - position / max_position)
                        else:
                            duration_score = 0.20
                    # Bonus pour les vols directs si client les préfère
                    if is_direct and partner_profile.get('prefers_direct', True):
                        duration_score += 0.05

                    duration_score = max(0, min(0.20, duration_score))  # Limiter à 25%
                    _logger.info(f"Score durée: {duration_score:.2f} pour {duration_category} (direct: {is_direct})")
                    final_score += duration_score

                    # 4. Score de l'heure de départ (25% du score total)
                    time_score = 0
                    if 'preferred_departure_times' in partner_profile and time_category in partner_profile[
                        'preferred_departure_times']:
                        position = partner_profile['preferred_departure_times'].index(time_category)
                        max_position = len(partner_profile['preferred_departure_times']) - 1
                        if max_position > 0:  # Éviter division par zéro
                            time_score = 0.15 * (1 - position / max_position)
                        else:
                            time_score = 0.15

                    _logger.info(f"Score heure de départ: {time_score:.2f} pour {time_category}")
                    final_score += time_score

                    # Facteurs secondaires avec influence réduite
                    # 5. Jour de la semaine (5% d'ajustement)
                    day_adjustment = 0
                    day_of_week = flight_features['day_of_week']
                    if 'preferred_days' in partner_profile and day_of_week in partner_profile['preferred_days']:
                        position = partner_profile['preferred_days'].index(day_of_week)
                        max_position = len(partner_profile['preferred_days']) - 1
                        if max_position > 0:  # Éviter division par zéro
                            day_adjustment = 0.05 * (1 - position / max_position)
                        else:
                            day_adjustment = 0.05
                    _logger.info(f"Ajustement jour: {day_adjustment:.2f} pour jour {day_of_week}")
                    final_score += day_adjustment

                    # Ajouter le score final au vol
                    flight['recommendation_score'] = final_score
                    _logger.info(f"Score final calculé: {final_score:.4f} pour vol {flight.get('flightNumber', 'N/A')}")

                    # Détail des composantes du score pour le débogage
                    flight['score_components'] = {
                        'knn': knn_score * 0.2,
                        'airline': airline_score,
                        'price': price_score,
                        'duration': duration_score,
                        'departure_time': time_score,
                        'day_adjustment': day_adjustment
                    }

                except Exception as e:
                    _logger.error(f"Erreur lors du traitement d'un vol: {str(e)}")
                    flight['recommendation_score'] = 0  # Score minimal en cas d'erreur
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

                # Initialiser tous les autres à False
                for i in range(top_count, len(flights_data)):
                    flights_data[i]['is_recommended'] = False

            _logger.info(f"Vols triés par préférence pour le partenaire {partner_id}")
            _logger.info(f"---- FIN DU TRI DES VOLS ----")
            return flights_data

        except Exception as e:
            _logger.error(f"Erreur lors du tri des vols par préférence: {str(e)}")
            return flights_data


    def _extract_departure_time(self, flight):
        depart_time = None

        # Essayer différentes structures possibles
        if 'departDateTime' in flight and 'time' in flight['departDateTime']:
            depart_time = flight['departDateTime']['time']
        elif 'departureTime' in flight:
            depart_time = flight['departureTime']
        elif 'departure' in flight and 'time' in flight['departure']:
            depart_time = flight['departure']['time']
        elif 'depart' in flight and isinstance(flight['depart'], dict) and 'time' in flight['depart']:
            depart_time = flight['depart']['time']
        elif 'depart_time' in flight:
            depart_time = flight['depart_time']

        # Si aucun format ne correspond, utiliser une valeur par défaut
        if not depart_time:
            _logger.warning(f"Impossible d'extraire l'heure de départ, utilisation d'une valeur par défaut")
            depart_time = "12:00"  # Midi par défaut

        return depart_time

    def _extract_duration(self, flight):
        duration_str = None

        # Essayer différentes structures possibles
        if 'duration' in flight:
            duration_str = flight['duration']
        elif 'flightDuration' in flight:
            duration_str = flight['flightDuration']
        elif 'travelDuration' in flight:
            duration_str = flight['travelDuration']

        if not duration_str:
            _logger.warning(f"Impossible d'extraire la durée du vol, utilisation d'une valeur par défaut")
            return 2.0  # 2 heures par défaut

        # Convertir la durée en heures
        return self._extract_duration_in_hours(duration_str)

    def _extract_airline(self, flight):
        airline = flight.get('airlines', {}).get('full', '')
        if not airline:
            airline = flight.get('airline', '')
            if not airline:
                airline = flight.get('airlineName', '')
                if not airline:
                    airline = flight.get('carrier', '')
                    if not airline:
                        airline = 'Unknown'
        return airline

    def _extract_departure_date(self, flight):
        depart_date_str = None

        # Essayer différentes structures possibles
        if 'departDateTime' in flight and 'date' in flight['departDateTime']:
            depart_date_str = flight['departDateTime']['date']
        elif 'departureDate' in flight:
            depart_date_str = flight['departureDate']
        elif 'departure' in flight and 'date' in flight['departure']:
            depart_date_str = flight['departure']['date']
        elif 'depart' in flight and isinstance(flight['depart'], dict) and 'date' in flight['depart']:
            depart_date_str = flight['depart']['date']
        elif 'depart_date' in flight:
            depart_date_str = flight['depart_date']

        # Convertir la date en objet datetime
        if depart_date_str:
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                try:
                    return datetime.strptime(depart_date_str, fmt)
                except ValueError:
                    continue

        # Si aucun format ne correspond, utiliser la date actuelle
        _logger.warning(f"Impossible d'extraire la date de départ, utilisation de la date actuelle")
        return datetime.now()

    def _extract_price(self, flight):
        price = 0.0

        # Vérifier les différentes possibilités pour le prix
        if 'price' in flight:
            if isinstance(flight['price'], (int, float)):
                price = float(flight['price'])
            elif isinstance(flight['price'], str):
                # Supprimer les caractères non numériques (sauf le point décimal)
                price_str = ''.join(c for c in flight['price'] if c.isdigit() or c == '.')
                try:
                    price = float(price_str)
                except ValueError:
                    price = 0.0
        elif 'amount' in flight:
            if isinstance(flight['amount'], (int, float)):
                price = float(flight['amount'])
            elif isinstance(flight['amount'], str):
                price_str = ''.join(c for c in flight['amount'] if c.isdigit() or c == '.')
                try:
                    price = float(price_str)
                except ValueError:
                    price = 0.0
        elif 'totalPrice' in flight:
            if isinstance(flight['totalPrice'], (int, float)):
                price = float(flight['totalPrice'])
            elif isinstance(flight['totalPrice'], str):
                price_str = ''.join(c for c in flight['totalPrice'] if c.isdigit() or c == '.')
                try:
                    price = float(price_str)
                except ValueError:
                    price = 0.0

        return price

    def _extract_is_direct(self, flight):
        is_direct = True  # Par défaut

        if 'isDirect' in flight:
            is_direct = bool(flight['isDirect'])
        elif 'direct' in flight:
            is_direct = bool(flight['direct'])
        elif 'stops' in flight:
            is_direct = flight['stops'] == 0 or flight['stops'] == '0'
        elif 'stopovers' in flight:
            is_direct = flight['stopovers'] == 0 or flight['stopovers'] == '0'
        elif 'segments' in flight and isinstance(flight['segments'], list):
            is_direct = len(flight['segments']) == 1

        return is_direct

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

    @api.model
    def schedule_training(self):
        """Planifie l'entraînement du modèle (pour cron job)"""
        try:
            # Vérifier si un modèle actif existe déjà
            model = self.get_active_model()

            if model:
                _logger.info(f"Modèle actif trouvé (ID: {model.id}), début de l'entraînement")
                success = model._train_model()
                if success:
                    _logger.info(f"Entraînement réussi - KNN Accuracy: {model.knn_accuracy:.4f}")
                    # Commit explicite pour s'assurer que les modifications sont enregistrées
                    self.env.cr.commit()
                else:
                    _logger.warning("Échec de l'entraînement du modèle")
            else:
                # Créer un nouveau modèle si aucun n'existe
                _logger.info("Aucun modèle actif trouvé, création d'un nouveau modèle")
                model = self.create({'name': 'Modèle de recommandation KNN'})
                # Vérifier que le modèle a bien été créé
                if model and model.id:
                    _logger.info(f"Nouveau modèle créé avec ID: {model.id}")
                    success = model._train_model()
                    if success:
                        _logger.info(f"Nouveau modèle entraîné avec succès - KNN Accuracy: {model.knn_accuracy:.4f}")
                        # Commit explicite
                        self.env.cr.commit()
                    else:
                        _logger.warning("Échec de l'entraînement du nouveau modèle")
                else:
                    _logger.error("Échec de la création du modèle")

            return True
        except Exception as e:
            _logger.error(f"Erreur lors de la planification de l'entraînement: {str(e)}")
            # Rollback en cas d'erreur
            self.env.cr.rollback()
            return False
    def _train_model(self):
                self.ensure_one()
                _logger.info("Début de l'entraînement du modèle de recommandation")

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
                    # Récupérer les détails du vol principal
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
                _logger.info(f"Colonnes disponibles: {df.columns.tolist()}")
                _logger.info(
                    f"Statistiques des prix: min={df['price'].min()}, max={df['price'].max()}, mean={df['price'].mean()}")

                # Préparation des caractéristiques
                categorical_features = ['airline', 'seat_preference', 'meal_preference', 'day_of_week', 'month_of_year']
                numerical_features = ['price']
                binary_features = ['is_direct']

                # Vérifier si tous les features existent
                for feature in categorical_features + numerical_features + binary_features:
                    if feature not in df.columns:
                        _logger.warning(f"Caractéristique manquante: {feature}")
                        if feature in categorical_features:
                            df[feature] = 'unknown'  # Valeur par défaut pour catégories
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
                _logger.info(
                    f"Normalisation terminée: {numerical_scaled.shape} caractéristiques numériques normalisées")

                # Ajouter les variables binaires (si présentes)
                binary_data = df[binary_features].values if binary_features and all(
                    f in df.columns for f in binary_features) else np.array([]).reshape(len(df), 0)
                _logger.info(f"Variables binaires: {binary_data.shape}")

                # Combiner toutes les caractéristiques
                features = np.hstack((categorical_encoded, numerical_scaled, binary_data))
                _logger.info(f"Matrice de caractéristiques combinées: {features.shape}")

                # Créer et entraîner le modèle KNN
                knn_model = NearestNeighbors(n_neighbors=min(5, len(features)), algorithm='ball_tree')
                knn_model.fit(features)
                _logger.info("Modèle KNN entraîné avec succès")

                # Évaluer le modèle avec la fonction d'évaluation
                evaluation_metrics = self._evaluate_model(df, features)

                _logger.info(f"Métriques d'évaluation: {evaluation_metrics}")

                # Sauvegarder le modèle
                knn_binary = pickle.dumps(knn_model)
                encoder_binary = pickle.dumps(encoder)
                scaler_binary = pickle.dumps(scaler)

                self.write({
                    'model_data': base64.b64encode(knn_binary),
                    'encoder_data': base64.b64encode(encoder_binary),
                    'scaler_data': base64.b64encode(scaler_binary),
                    'last_training_date': fields.Datetime.now(),
                    'training_sample_size': len(df),
                    'feature_count': features.shape[1],
                    'knn_accuracy': evaluation_metrics.get('knn_accuracy', 0.5)  # Valeur par défaut si non défini
                })
                _logger.info(f"Utilisation du modèle avec KNN Accuracy: {self.knn_accuracy:.4f}")
                _logger.warning(
                    f"MÉTRIQUES D'ÉVALUATION: {evaluation_metrics}")  # Utilisez WARNING pour être sûr que ça s'affiche
                # Et après la mise à jour du modèle
                _logger.warning(f"ACCURACY APRÈS MISE À JOUR: {self.knn_accuracy}")

                _logger.info(f"Modèle entraîné avec succès sur {len(df)} exemples")
                return True

    def _evaluate_model(self, df=None, features=None):
        _logger.info("Début de l'évaluation du modèle")

        metrics = {
            'knn_accuracy': 0.5,  # Valeur par défaut
            'knn_precision': 0.5,
            'knn_recall': 0.5,
            'knn_f1': 0.5,
            'ndcg_score': 0.0,  # Normalized Discounted Cumulative Gain
            'map_score': 0.0,  # Mean Average Precision
            'precision_at_k': {},  # Precision@K pour différentes valeurs de K
            'recall_at_k': {},  # Recall@K pour différentes valeurs de K
            'f1_at_k': {}  # F1@K pour différentes valeurs de K
        }

        # Si les données ne sont pas fournies, les récupérer
        if df is None or features is None:
            # Récupérer les données d'entraînement
            bookings = self.env['booking'].search([
                ('state', '=', 'confirmed'),
                ('create_date', '>=', fields.Datetime.now() - timedelta(days=self.max_history_age_days))
            ])

            _logger.info(f"Évaluation: {len(bookings)} réservations récupérées")

            if len(bookings) < 20:  # Minimum pour une évaluation fiable
                _logger.warning("Données insuffisantes pour une évaluation fiable")
                return metrics

            # Transformer les données
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
            _logger.info(f"Évaluation: DataFrame créé avec {len(df)} lignes")

            # Préparation des caractéristiques
            categorical_features = ['airline', 'seat_preference', 'meal_preference', 'day_of_week',
                                    'month_of_year']
            numerical_features = ['price']
            binary_features = ['is_direct']

            # Vérifier les features manquants
            for feature in categorical_features + numerical_features + binary_features:
                if feature not in df.columns:
                    if feature in categorical_features:
                        df[feature] = 'unknown'
                    elif feature == 'price':
                        df[feature] = df['price'].mean() if 'price' in df else 0.0
                    else:
                        df[feature] = False if feature == 'is_direct' else 0

            # Encoder les variables catégorielles
            encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
            categorical_encoded = encoder.fit_transform(df[categorical_features])

            # Normaliser les variables numériques
            scaler = StandardScaler()
            numerical_scaled = scaler.fit_transform(df[numerical_features])

            # Ajouter les variables binaires
            binary_data = df[binary_features].values if binary_features and all(
                f in df.columns for f in binary_features) else np.array([]).reshape(len(df), 0)

            # Combiner toutes les caractéristiques
            features = np.hstack((categorical_encoded, numerical_scaled, binary_data))

        try:
            # Approche 1: Utiliser la validation croisée pour une évaluation plus robuste
            from sklearn.model_selection import KFold, cross_val_score
            from sklearn.neighbors import KNeighborsClassifier
            from sklearn.metrics import ndcg_score, make_scorer

            # Création d'une cible plus représentative des préférences utilisateur
            # On crée plusieurs cibles pour évaluer différentes facettes du modèle

            # 1. Cible basée sur le prix (comme avant mais avec plus de nuance)
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
                # Convertir les heures de départ en entiers
                departure_hours = []
                for time_str in df['departure_time']:
                    try:
                        if isinstance(time_str, str) and ':' in time_str:
                            departure_hours.append(int(time_str.split(':')[0]))
                        elif hasattr(time_str, 'hour'):
                            departure_hours.append(time_str.hour)
                        else:
                            departure_hours.append(12)  # Valeur par défaut
                    except:
                        departure_hours.append(12)  # Valeur par défaut

                df['departure_hour'] = departure_hours
                time_target = pd.cut(df['departure_hour'],
                                     [0, 6, 12, 18, 24],
                                     labels=[0, 1, 2, 3],
                                     include_lowest=True)
            else:
                time_target = np.zeros(len(df))

            # Initialiser les modèles et les scores
            knn_price = KNeighborsClassifier(n_neighbors=min(5, len(df)))
            knn_airline = KNeighborsClassifier(n_neighbors=min(5, len(df)))
            knn_time = KNeighborsClassifier(n_neighbors=min(5, len(df)))

            # Validation croisée stratifiée pour garantir une distribution équilibrée
            from sklearn.model_selection import StratifiedKFold
            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

            # Scores pour le modèle basé sur le prix
            try:
                price_scores = cross_val_score(knn_price, features, price_target,
                                               cv=cv, scoring='accuracy')
                metrics['knn_price_accuracy'] = np.mean(price_scores)
                _logger.info(f"KNN Price Accuracy: {metrics['knn_price_accuracy']:.4f}")
            except Exception as e:
                _logger.error(f"Erreur lors de l'évaluation KNN prix: {str(e)}")
                metrics['knn_price_accuracy'] = 0.5

            # Scores pour le modèle basé sur la compagnie aérienne
            try:
                airline_scores = cross_val_score(knn_airline, features, airline_target,
                                                 cv=cv, scoring='accuracy')
                metrics['knn_airline_accuracy'] = np.mean(airline_scores)
                _logger.info(f"KNN Airline Accuracy: {metrics['knn_airline_accuracy']:.4f}")
            except Exception as e:
                _logger.error(f"Erreur lors de l'évaluation KNN compagnie: {str(e)}")
                metrics['knn_airline_accuracy'] = 0.5

            # Scores pour le modèle basé sur l'heure
            try:
                time_scores = cross_val_score(knn_time, features, time_target,
                                              cv=cv, scoring='accuracy')
                metrics['knn_time_accuracy'] = np.mean(time_scores)
                _logger.info(f"KNN Time Accuracy: {metrics['knn_time_accuracy']:.4f}")
            except Exception as e:
                _logger.error(f"Erreur lors de l'évaluation KNN heure: {str(e)}")
                metrics['knn_time_accuracy'] = 0.5

            # Score global: moyenne pondérée des trois scores
            metrics['knn_accuracy'] = (0.4 * metrics['knn_price_accuracy'] +
                                       0.4 * metrics['knn_airline_accuracy'] +
                                       0.2 * metrics['knn_time_accuracy'])
            _logger.info(f"KNN Accuracy globale: {metrics['knn_accuracy']:.4f}")

            # Approche 2: Évaluation de la qualité du ranking (pour système de recommandation)
            try:
                from sklearn.model_selection import train_test_split
                from sklearn.metrics import precision_score, recall_score, f1_score

                # Créer un score de pertinence synthétique pour chaque réservation
                # Basé sur une combinaison de facteurs
                relevance_scores = []

                # Grouper par partenaire pour calculer les scores de pertinence
                for partner_id, partner_df in df.groupby('partner_id'):
                    if len(partner_df) < 2:
                        # Pas assez de données pour ce partenaire
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

                        # Normaliser entre 0 et 3 pour avoir des niveaux de pertinence
                        relevance_scores.append(int(score * 3))

                relevance_array = np.array(relevance_scores)

                # Division en ensembles d'entraînement et de test
                X_train, X_test, y_train, y_test = train_test_split(
                    features, relevance_array, test_size=0.3, random_state=42
                )

                # Entraîner un modèle de régression pour prédire les scores de pertinence
                from sklearn.neighbors import KNeighborsRegressor
                knn_reg = KNeighborsRegressor(n_neighbors=min(5, len(X_train)))
                knn_reg.fit(X_train, y_train)

                # Prédire les scores pour l'ensemble de test
                y_pred = knn_reg.predict(X_test)

                # Arrondir les prédictions pour les traiter comme des classes
                y_pred_rounded = np.round(y_pred).astype(int)

                # Calculer precision, recall et F1 globaux
                metrics['knn_precision'] = precision_score(y_test, y_pred_rounded, average='weighted', zero_division=0)
                metrics['knn_recall'] = recall_score(y_test, y_pred_rounded, average='weighted', zero_division=0)
                metrics['knn_f1'] = f1_score(y_test, y_pred_rounded, average='weighted', zero_division=0)

                _logger.warning(f"Precision globale: {metrics['knn_precision']:.4f}")
                _logger.warning(f"Recall global: {metrics['knn_recall']:.4f}")
                _logger.warning(f"F1-score global: {metrics['knn_f1']:.4f}")

                # Calculer NDCG (mesure de la qualité du ranking)
                # Regrouper par partenaire pour calculer NDCG pour chaque utilisateur
                partner_ids_test = df.iloc[X_test.shape[0]:].reset_index(drop=True)['partner_id'].values

                ndcg_scores = []
                map_scores = []

                # Valeurs de K à évaluer pour precision@K, recall@K, etc.
                k_values = [1, 3, 5, 10]

                # Initialiser les listes pour stocker les métriques à différentes valeurs de K
                for k in k_values:
                    metrics['precision_at_k'][k] = []
                    metrics['recall_at_k'][k] = []
                    metrics['f1_at_k'][k] = []

                # Si nous avons les IDs des partenaires
                if len(partner_ids_test) == len(y_test):
                    unique_partners = np.unique(partner_ids_test)

                    for partner in unique_partners:
                        partner_mask = partner_ids_test == partner
                        if np.sum(partner_mask) > 1:  # Au moins 2 éléments pour calculer NDCG
                            try:
                                partner_y_true = y_test[partner_mask].reshape(1, -1)
                                partner_y_pred = y_pred[partner_mask].reshape(1, -1)

                                # NDCG@k, où k est le nombre d'éléments pour ce partenaire
                                k = min(5, len(partner_y_true[0]))
                                partner_ndcg = ndcg_score(partner_y_true, partner_y_pred, k=k)
                                ndcg_scores.append(partner_ndcg)

                                # Calculer precision@K, recall@K et F1@K pour différentes valeurs de K
                                for k_val in k_values:
                                    if k_val <= len(partner_y_true[0]):
                                        # Convertir en binaire : 1 si pertinent (dans le top-k réel), 0 sinon
                                        true_top_k_indices = np.argsort(-partner_y_true[0])[:k_val]
                                        pred_top_k_indices = np.argsort(-partner_y_pred[0])[:k_val]

                                        # Créer des ensembles pour faciliter le calcul
                                        true_top_k_set = set(true_top_k_indices)
                                        pred_top_k_set = set(pred_top_k_indices)

                                        # Calculer precision@K et recall@K
                                        if len(pred_top_k_set) > 0:
                                            precision_k = len(true_top_k_set.intersection(pred_top_k_set)) / len(
                                                pred_top_k_set)
                                            metrics['precision_at_k'][k_val].append(precision_k)

                                        if len(true_top_k_set) > 0:
                                            recall_k = len(true_top_k_set.intersection(pred_top_k_set)) / len(
                                                true_top_k_set)
                                            metrics['recall_at_k'][k_val].append(recall_k)

                                        # Calculer F1@K
                                        if precision_k + recall_k > 0:
                                            f1_k = 2 * precision_k * recall_k / (precision_k + recall_k)
                                            metrics['f1_at_k'][k_val].append(f1_k)

                                # MAP (Mean Average Precision)
                                # Convertir en rangs
                                true_ranks = np.argsort(-partner_y_true[0])
                                pred_ranks = np.argsort(-partner_y_pred[0])

                                # Calculer AP (Average Precision)
                                ap = self._average_precision(true_ranks, pred_ranks)
                                map_scores.append(ap)
                            except Exception as e:
                                _logger.error(
                                    f"Erreur lors du calcul des métriques pour partenaire {partner}: {str(e)}")

                # Calculer les moyennes pour chaque métrique@K
                for k in k_values:
                    if metrics['precision_at_k'][k]:
                        avg_precision_k = np.mean(metrics['precision_at_k'][k])
                        _logger.warning(f"Precision@{k}: {avg_precision_k:.4f}")
                        metrics['precision_at_k'][k] = avg_precision_k
                    else:
                        metrics['precision_at_k'][k] = 0.0

                    if metrics['recall_at_k'][k]:
                        avg_recall_k = np.mean(metrics['recall_at_k'][k])
                        _logger.warning(f"Recall@{k}: {avg_recall_k:.4f}")
                        metrics['recall_at_k'][k] = avg_recall_k
                    else:
                        metrics['recall_at_k'][k] = 0.0

                    if metrics['f1_at_k'][k]:
                        avg_f1_k = np.mean(metrics['f1_at_k'][k])
                        _logger.warning(f"F1@{k}: {avg_f1_k:.4f}")
                        metrics['f1_at_k'][k] = avg_f1_k
                    else:
                        metrics['f1_at_k'][k] = 0.0

                if ndcg_scores:
                    metrics['ndcg_score'] = np.mean(ndcg_scores)
                    _logger.warning(f"NDCG Score: {metrics['ndcg_score']:.4f}")

                if map_scores:
                    metrics['map_score'] = np.mean(map_scores)
                    _logger.warning(f"MAP Score: {metrics['map_score']:.4f}")

            except ImportError:
                _logger.warning("scikit-learn 0.22+ requis pour ndcg_score, métriques de ranking ignorées")
            except Exception as e:
                _logger.error(f"Erreur lors du calcul des métriques de ranking: {str(e)}")

        except Exception as e:
            _logger.error(f"Erreur générale lors de l'évaluation du modèle: {str(e)}")
            # Garder les valeurs par défaut définies au début

        _logger.info(f"Évaluation du modèle terminée: {metrics}")
        return metrics

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

