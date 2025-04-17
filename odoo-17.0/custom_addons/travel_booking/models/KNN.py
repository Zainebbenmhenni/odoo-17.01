# # -*- coding: utf-8 -*-
# from odoo import models, fields, api
# import logging
# import pandas as pd
# from datetime import datetime, timedelta
# from sklearn.model_selection import train_test_split, cross_val_score
# from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
# import numpy as np
# from sklearn.preprocessing import OneHotEncoder, StandardScaler
# from sklearn.neighbors import NearestNeighbors
# from sklearn.ensemble import RandomForestClassifier
# import pickle
# import base64
# import io
# import json
# from collections import Counter
#
# _logger = logging.getLogger(__name__)
#
#
# class FlightRecommendationModel(models.Model):
#     _name = 'flight.recommendation.model'
#     _description = 'Modèle de recommandation de vols'
#
#     name = fields.Char('Nom du modèle', default='Modèle de recommandation', required=True)
#     model_data = fields.Binary('Données du modèle', attachment=True)
#     encoder_data = fields.Binary('Données de l\'encodeur', attachment=True)
#     scaler_data = fields.Binary('Données du normalisateur', attachment=True)
#     second_model_data = fields.Binary('Données du second modèle', attachment=True)
#     algorithm_type = fields.Selection([
#         ('knn', 'K-Nearest Neighbors'),
#         ('random_forest', 'Random Forest'),
#         ('hybrid', 'Hybride (combinaison des deux)')
#     ], string='Type d\'algorithme', default='knn')
#     last_training_date = fields.Datetime('Dernière date d\'entraînement')
#     active = fields.Boolean('Actif', default=True)
#
#     # Métriques d'évaluation des modèles
#     knn_accuracy = fields.Float('Précision KNN', readonly=True)
#     rf_accuracy = fields.Float('Précision Random Forest', readonly=True)
#     hybrid_accuracy = fields.Float('Précision hybride', readonly=True)
#
#     # Statistiques du modèle
#     training_sample_size = fields.Integer('Taille de l\'échantillon d\'entraînement', readonly=True)
#     feature_count = fields.Integer('Nombre de caractéristiques', readonly=True)
#
#     # Configuration
#     min_booking_history = fields.Integer('Historique minimum pour personnalisation', default=3,
#                                          help="Nombre minimum de réservations nécessaires pour personnaliser les résultats")
#     max_history_age_days = fields.Integer('Âge maximum de l\'historique (jours)', default=365,
#                                           help="Âge maximum des réservations à prendre en compte")
#     num_recommendations = fields.Integer('Nombre de recommandations', default=3,
#                                          help="Nombre de vols à marquer comme recommandés")
#
#     def _get_model(self):
#         """Récupère le modèle entraîné depuis le champ binary"""
#         self.ensure_one()
#         if not self.model_data:
#             return None
#
#         try:
#             model_binary = base64.b64decode(self.model_data)
#             model = pickle.loads(model_binary)
#             return model
#         except Exception as e:
#             _logger.error(f"Erreur lors du chargement du modèle: {str(e)}")
#             return None
#
#     def _get_second_model(self):
#         """Récupère le second modèle entraîné depuis le champ binary"""
#         self.ensure_one()
#         if not self.second_model_data:
#             return None
#
#         try:
#             model_binary = base64.b64decode(self.second_model_data)
#             model = pickle.loads(model_binary)
#             return model
#         except Exception as e:
#             _logger.error(f"Erreur lors du chargement du second modèle: {str(e)}")
#             return None
#
#     def _get_encoder(self):
#         """Récupère l'encodeur depuis le champ binary"""
#         self.ensure_one()
#         if not self.encoder_data:
#             return None
#
#         try:
#             encoder_binary = base64.b64decode(self.encoder_data)
#             encoder = pickle.loads(encoder_binary)
#             return encoder
#         except Exception as e:
#             _logger.error(f"Erreur lors du chargement de l'encodeur: {str(e)}")
#             return None
#
#     def _get_scaler(self):
#         """Récupère le normalisateur depuis le champ binary"""
#         self.ensure_one()
#         if not self.scaler_data:
#             return None
#
#         try:
#             scaler_binary = base64.b64decode(self.scaler_data)
#             scaler = pickle.loads(scaler_binary)
#             return scaler
#         except Exception as e:
#             _logger.error(f"Erreur lors du chargement du normalisateur: {str(e)}")
#             return None
#
#
#
#     @api.model
#     def get_active_model(self):
#         """Récupère le modèle actif"""
#         return self.search([('active', '=', True)], limit=1)
#
#     @api.model
#     def schedule_training(self):
#         """Planifie l'entraînement du modèle (pour cron job)"""
#         model = self.get_active_model()
#         if model:
#             model._train_model()
#         else:
#             # Créer un nouveau modèle si aucun n'existe
#             model = self.create({'name': 'Modèle de recommandation'})
#             model._train_model()
#         return True
#
#     def sort_flights_by_preference(self, partner_id, flights_data, email=None):
#         """
#         Trie les vols selon les préférences du client et marque les vols recommandés
#
#         :param partner_id: ID du partenaire connecté
#         :param flights_data: Liste des vols retournés par l'API
#         :param email: Email du client (facultatif, utilisé si partner_id ne donne pas de résultats)
#         :return: Liste triée de vols
#         """
#         self.ensure_one()
#         _logger.info(f"---- DÉBUT DU TRI DES VOLS ----")
#         _logger.info(f"Partner ID: {partner_id}, Email: {email}, Nombre de vols: {len(flights_data)}")
#         _logger.info(
#             f"Utilisation du modèle avec KNN Accuracy: {self.knn_accuracy:.4f}, RF Accuracy: {self.rf_accuracy:.4f}, Hybrid Accuracy: {self.hybrid_accuracy:.4f}")
#
#         if not flights_data:
#             _logger.warning("Aucun vol à trier")
#             return flights_data
#
#         # Vérifier si partner_id est valide
#         if not partner_id:
#             _logger.info("Aucun partner_id fourni, recherche par email")
#             if not email:
#                 _logger.warning("Ni partner_id ni email fourni pour la personnalisation")
#                 return flights_data
#
#             # Rechercher le partenaire par email
#             partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
#             if partner:
#                 partner_id = partner.id
#                 _logger.info(f"Partenaire trouvé par email: {partner_id}")
#             else:
#                 _logger.warning(f"Aucun partenaire trouvé avec l'email: {email}")
#                 return flights_data
#
#         # Charger les modèles selon l'algorithme sélectionné
#         knn_model = None
#         rf_model = None
#
#         if self.algorithm_type in ['knn', 'hybrid']:
#             knn_model = self._get_model()
#
#         if self.algorithm_type in ['random_forest', 'hybrid']:
#             rf_model = self._get_second_model()
#
#         encoder = self._get_encoder()
#         scaler = self._get_scaler()
#
#         if (self.algorithm_type == 'knn' and not knn_model) or \
#                 (self.algorithm_type == 'random_forest' and not rf_model) or \
#                 (self.algorithm_type == 'hybrid' and (not knn_model or not rf_model)) or \
#                 not encoder or not scaler:
#             _logger.warning("Modèle de recommandation non disponible ou incomplet")
#             return flights_data
#
#         # Vérifier l'historique suffisant pour la personnalisation
#         bookings_count = self._get_bookings_count(partner_id, email)
#
#         if bookings_count < self.min_booking_history:
#             _logger.info(f"Historique insuffisant ({bookings_count} réservations) pour personnalisation")
#             return flights_data
#
#         try:
#             # Récupérer le profil client (avec les préférences ordonnées)
#             partner_profile = self._get_partner_profile(partner_id, email)
#             _logger.info(f"Profil partenaire: {partner_profile}")
#
#             # Définition des catégories
#             TIME_CATEGORIES = {
#                 'morning': (5, 12),  # 5h-12h
#                 'afternoon': (12, 17),  # 12h-17h
#                 'evening': (17, 22),  # 17h-22h
#                 'night': (22, 5)  # 22h-5h
#             }
#
#             DURATION_CATEGORIES = {
#                 'short': 2,  # < 2h
#                 'medium': 5,  # <= 5h
#                 'long': float('inf')  # > 5h
#             }
#
#             # Traiter chaque vol et calculer son score de personnalisation
#             for flight in flights_data:
#                 try:
#                     # Extraction adaptée à la structure de données de l'API
#                     airline = self._extract_airline(flight)
#                     departure_date = self._extract_departure_date(flight)
#                     departure_time = self._extract_departure_time(flight)
#                     price = self._extract_price(flight)
#                     is_direct = self._extract_is_direct(flight)
#                     duration_hours = self._extract_duration(flight)
#
#                     # Déterminer la catégorie de l'heure de départ
#                     departure_hour = self._extract_hour_from_time(departure_time)
#
#                     # Attribution de la catégorie d'heure
#                     if 5 <= departure_hour < 12:
#                         time_category = 'morning'
#                     elif 12 <= departure_hour < 17:
#                         time_category = 'afternoon'
#                     elif 17 <= departure_hour < 22:
#                         time_category = 'evening'
#                     else:
#                         time_category = 'night'
#
#                     # Déterminer la catégorie de durée
#                     if duration_hours < DURATION_CATEGORIES['short']:
#                         duration_category = 'short'
#                     elif duration_hours <= DURATION_CATEGORIES['medium']:
#                         duration_category = 'medium'
#                     else:
#                         duration_category = 'long'
#
#                     # Déterminer la catégorie de prix
#                     if price < partner_profile['avg_price'] * 0.8:
#                         price_category = 'low'
#                     elif price > partner_profile['avg_price'] * 1.2:
#                         price_category = 'high'
#                     else:
#                         price_category = 'medium'
#
#                     # Construire l'objet de caractéristiques du vol
#                     flight_features = {
#                         'airline': airline,
#                         'price': price,
#                         'day_of_week': departure_date.weekday(),
#                         'month_of_year': departure_date.month,
#                         'seat_preference': 'window',  # Valeur par défaut
#                         'meal_preference': 'regular',  # Valeur par défaut
#                         'is_direct': is_direct
#                     }
#
#                     _logger.info(
#                         f"Caractéristiques extraites pour vol {flight.get('flightNumber', 'N/A')}: {flight_features}")
#
#                     # Encoder et normaliser les caractéristiques
#                     categorical_df = pd.DataFrame({
#                         'airline': [flight_features['airline']],
#                         'seat_preference': [flight_features['seat_preference']],
#                         'meal_preference': [flight_features['meal_preference']],
#                         'day_of_week': [flight_features['day_of_week']],
#                         'month_of_year': [flight_features['month_of_year']],
#                     })
#
#                     try:
#                         categorical_encoded = encoder.transform(categorical_df)
#                     except ValueError as e:
#                         _logger.warning(
#                             f"Erreur d'encodage des catégories: {str(e)}. Utilisation de la méthode alternative.")
#                         # Gestion des nouvelles catégories (non vues pendant l'entraînement)
#                         # Remplacer par des valeurs connues puis encoder
#                         for col in categorical_df.columns:
#                             if col in encoder.feature_names_in_:
#                                 categories = encoder.categories_[list(encoder.feature_names_in_).index(col)]
#                                 if categorical_df[col][0] not in categories:
#                                     # Remplacer par la catégorie la plus commune dans nos données d'entraînement
#                                     categorical_df[col][0] = categories[0]
#                         categorical_encoded = encoder.transform(categorical_df)
#
#                     numerical_df = pd.DataFrame({
#                         'price': [flight_features['price']]
#                     })
#                     numerical_scaled = scaler.transform(numerical_df)
#
#                     # Ajouter les caractéristiques binaires
#                     binary_features = np.array([[int(flight_features['is_direct'])]])
#
#                     # Combiner les caractéristiques
#                     features = np.hstack((categorical_encoded, numerical_scaled, binary_features))
#
#                     # Initialiser le score final
#                     final_score = 0.0
#
#                     # Calculer les scores selon l'algorithme choisi
#                     if self.algorithm_type in ['knn', 'hybrid']:
#                         try:
#                             distances, _ = knn_model.kneighbors(features)
#                             knn_score = 1.0 / (1.0 + np.mean(distances[0]))
#
#                             if self.algorithm_type == 'knn':
#                                 final_score = knn_score
#                             else:  # hybrid
#                                 final_score = knn_score * 0.5  # Pondération 50%
#                         except Exception as e:
#                             _logger.error(f"Erreur lors du calcul du score KNN: {str(e)}")
#                             if self.algorithm_type == 'knn':
#                                 final_score = 0
#
#                     # Score basé sur Random Forest
#                     if self.algorithm_type in ['random_forest', 'hybrid']:
#                         try:
#                             # Probabilité de la classe la plus élevée comme score
#                             rf_probas = rf_model.predict_proba(features)[0]
#                             rf_score = np.max(rf_probas)
#
#                             if self.algorithm_type == 'random_forest':
#                                 final_score = rf_score
#                             elif self.algorithm_type == 'hybrid':  # On ajoute, pas de réassignation
#                                 final_score += rf_score * 0.5  # Pondération 50%
#                         except Exception as e:
#                             _logger.error(f"Erreur lors du calcul du score Random Forest: {str(e)}")
#                             if self.algorithm_type == 'random_forest':
#                                 final_score = 0
#
#                     # Ajustement du score en fonction des préférences ordonnées
#                     # Bonus pour les compagnies aériennes préférées
#                     if airline in partner_profile.get('preferred_airlines', []):
#                         position = partner_profile['preferred_airlines'].index(airline)
#                         max_position = len(partner_profile['preferred_airlines']) - 1
#                         if max_position > 0:  # Éviter division par zéro
#                             bonus = 0.2 * (1 - position / max_position)
#                             final_score += bonus
#                             _logger.info(f"Bonus compagnie aérienne appliqué: +{bonus:.2f} pour {airline}")
#
#                     # Bonus pour la catégorie de durée préférée
#                     if 'preferred_durations' in partner_profile and duration_category in partner_profile[
#                         'preferred_durations']:
#                         position = partner_profile['preferred_durations'].index(duration_category)
#                         max_position = len(partner_profile['preferred_durations']) - 1
#                         if max_position > 0:  # Éviter division par zéro
#                             bonus = 0.15 * (1 - position / max_position)
#                             final_score += bonus
#                             _logger.info(f"Bonus durée appliqué: +{bonus:.2f} pour {duration_category}")
#
#                     # Bonus pour la catégorie de prix préférée
#                     if 'preferred_price_categories' in partner_profile and price_category in partner_profile[
#                         'preferred_price_categories']:
#                         position = partner_profile['preferred_price_categories'].index(price_category)
#                         max_position = len(partner_profile['preferred_price_categories']) - 1
#                         if max_position > 0:  # Éviter division par zéro
#                             bonus = 0.2 * (1 - position / max_position)
#                             final_score += bonus
#                             _logger.info(f"Bonus catégorie de prix appliqué: +{bonus:.2f} pour {price_category}")
#
#                     # Bonus pour la catégorie d'heure de départ préférée
#                     if 'preferred_departure_times' in partner_profile and time_category in partner_profile[
#                         'preferred_departure_times']:
#                         position = partner_profile['preferred_departure_times'].index(time_category)
#                         max_position = len(partner_profile['preferred_departure_times']) - 1
#                         if max_position > 0:  # Éviter division par zéro
#                             bonus = 0.15 * (1 - position / max_position)
#                             final_score += bonus
#                             _logger.info(f"Bonus heure de départ appliqué: +{bonus:.2f} pour {time_category}")
#
#                     # Bonus pour les jours préférés
#                     day_of_week = flight_features['day_of_week']
#                     if 'preferred_days' in partner_profile and day_of_week in partner_profile['preferred_days']:
#                         position = partner_profile['preferred_days'].index(day_of_week)
#                         max_position = len(partner_profile['preferred_days']) - 1
#                         if max_position > 0:  # Éviter division par zéro
#                             bonus = 0.1 * (1 - position / max_position)
#                             final_score += bonus
#                             _logger.info(f"Bonus jour de la semaine appliqué: +{bonus:.2f} pour jour {day_of_week}")
#
#                     # Bonus pour les mois préférés
#                     month = flight_features['month_of_year']
#                     if 'preferred_months' in partner_profile and month in partner_profile['preferred_months']:
#                         position = partner_profile['preferred_months'].index(month)
#                         max_position = len(partner_profile['preferred_months']) - 1
#                         if max_position > 0:  # Éviter division par zéro
#                             bonus = 0.1 * (1 - position / max_position)
#                             final_score += bonus
#                             _logger.info(f"Bonus mois appliqué: +{bonus:.2f} pour mois {month}")
#
#                     # Bonus pour les vols directs si le client les préfère
#                     if flight_features['is_direct'] and partner_profile.get('prefers_direct', True):
#                         bonus = 0.15
#                         final_score += bonus
#                         _logger.info(f"Bonus vol direct appliqué: +{bonus:.2f}")
#
#                     # Pénalité si le prix est supérieur au prix moyen habituel (avec une marge de tolérance)
#                     if price > partner_profile['avg_price'] * 1.2:  # 20% de tolérance
#                         price_ratio = price / (partner_profile['avg_price'] * 1.2)
#                         penalty = min(0.3, 0.1 * (price_ratio - 1))  # Plafonnée à 0.3
#                         final_score -= penalty
#                         _logger.info(
#                             f"Pénalité prix appliquée: -{penalty:.2f} pour prix {price} vs moyenne {partner_profile['avg_price']}")
#
#                     # Ajouter le score final au vol
#                     flight['recommendation_score'] = final_score
#                     _logger.info(f"Score final calculé: {final_score:.4f} pour vol {flight.get('flightNumber', 'N/A')}")
#
#                 except Exception as e:
#                     _logger.error(f"Erreur lors du traitement d'un vol: {str(e)}")
#                     flight['recommendation_score'] = 0  # Score minimal en cas d'erreur
#                     flight['is_recommended'] = False
#
#             # Trier les vols par score de recommandation
#             flights_data.sort(key=lambda x: x.get('recommendation_score', 0), reverse=True)
#
#             # Marquer les meilleurs vols comme recommandés
#             if flights_data:
#                 top_count = min(self.num_recommendations, len(flights_data))
#                 for i in range(top_count):
#                     flights_data[i]['is_recommended'] = True
#                     _logger.info(
#                         f"Vol marqué comme recommandé: {flights_data[i].get('flightNumber', 'N/A')} avec score {flights_data[i].get('recommendation_score', 0):.4f}")
#
#                 # Initialiser tous les autres à False
#                 for i in range(top_count, len(flights_data)):
#                     flights_data[i]['is_recommended'] = False
#
#             _logger.info(f"Vols triés par préférence pour le partenaire {partner_id}")
#             _logger.info(f"---- FIN DU TRI DES VOLS ----")
#             return flights_data
#
#         except Exception as e:
#             _logger.error(f"Erreur lors du tri des vols par préférence: {str(e)}")
#             return flights_data
#
#     def _extract_departure_time(self, flight):
#         """Extrait l'heure de départ de la structure de données du vol"""
#         depart_time = None
#
#         # Essayer différentes structures possibles
#         if 'departDateTime' in flight and 'time' in flight['departDateTime']:
#             depart_time = flight['departDateTime']['time']
#         elif 'departureTime' in flight:
#             depart_time = flight['departureTime']
#         elif 'departure' in flight and 'time' in flight['departure']:
#             depart_time = flight['departure']['time']
#         elif 'depart' in flight and isinstance(flight['depart'], dict) and 'time' in flight['depart']:
#             depart_time = flight['depart']['time']
#         elif 'depart_time' in flight:
#             depart_time = flight['depart_time']
#
#         # Si aucun format ne correspond, utiliser une valeur par défaut
#         if not depart_time:
#             _logger.warning(f"Impossible d'extraire l'heure de départ, utilisation d'une valeur par défaut")
#             depart_time = "12:00"  # Midi par défaut
#
#         return depart_time
#
#     # Nouvelle méthode d'extraction de la durée
#     def _extract_duration(self, flight):
#         """Extrait la durée du vol en heures"""
#         duration_str = None
#
#         # Essayer différentes structures possibles
#         if 'duration' in flight:
#             duration_str = flight['duration']
#         elif 'flightDuration' in flight:
#             duration_str = flight['flightDuration']
#         elif 'travelDuration' in flight:
#             duration_str = flight['travelDuration']
#
#         if not duration_str:
#             _logger.warning(f"Impossible d'extraire la durée du vol, utilisation d'une valeur par défaut")
#             return 2.0  # 2 heures par défaut
#
#         # Convertir la durée en heures
#         return self._extract_duration_in_hours(duration_str)
#
#     def _extract_airline(self, flight):
#         """Extrait la compagnie aérienne de la structure de données du vol"""
#         airline = flight.get('airlines', {}).get('full', '')
#         if not airline:
#             airline = flight.get('airline', '')
#             if not airline:
#                 airline = flight.get('airlineName', '')
#                 if not airline:
#                     airline = flight.get('carrier', '')
#                     if not airline:
#                         airline = 'Unknown'
#         return airline
#
#     def _extract_departure_date(self, flight):
#         """Extrait la date de départ de la structure de données du vol"""
#         depart_date_str = None
#
#         # Essayer différentes structures possibles
#         if 'departDateTime' in flight and 'date' in flight['departDateTime']:
#             depart_date_str = flight['departDateTime']['date']
#         elif 'departureDate' in flight:
#             depart_date_str = flight['departureDate']
#         elif 'departure' in flight and 'date' in flight['departure']:
#             depart_date_str = flight['departure']['date']
#         elif 'depart' in flight and isinstance(flight['depart'], dict) and 'date' in flight['depart']:
#             depart_date_str = flight['depart']['date']
#         elif 'depart_date' in flight:
#             depart_date_str = flight['depart_date']
#
#         # Convertir la date en objet datetime
#         if depart_date_str:
#             for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
#                 try:
#                     return datetime.strptime(depart_date_str, fmt)
#                 except ValueError:
#                     continue
#
#         # Si aucun format ne correspond, utiliser la date actuelle
#         _logger.warning(f"Impossible d'extraire la date de départ, utilisation de la date actuelle")
#         return datetime.now()
#
#     def _extract_price(self, flight):
#         """Extrait le prix de la structure de données du vol"""
#         price = 0.0
#
#         # Vérifier les différentes possibilités pour le prix
#         if 'price' in flight:
#             if isinstance(flight['price'], (int, float)):
#                 price = float(flight['price'])
#             elif isinstance(flight['price'], str):
#                 # Supprimer les caractères non numériques (sauf le point décimal)
#                 price_str = ''.join(c for c in flight['price'] if c.isdigit() or c == '.')
#                 try:
#                     price = float(price_str)
#                 except ValueError:
#                     price = 0.0
#         elif 'amount' in flight:
#             if isinstance(flight['amount'], (int, float)):
#                 price = float(flight['amount'])
#             elif isinstance(flight['amount'], str):
#                 price_str = ''.join(c for c in flight['amount'] if c.isdigit() or c == '.')
#                 try:
#                     price = float(price_str)
#                 except ValueError:
#                     price = 0.0
#         elif 'totalPrice' in flight:
#             if isinstance(flight['totalPrice'], (int, float)):
#                 price = float(flight['totalPrice'])
#             elif isinstance(flight['totalPrice'], str):
#                 price_str = ''.join(c for c in flight['totalPrice'] if c.isdigit() or c == '.')
#                 try:
#                     price = float(price_str)
#                 except ValueError:
#                     price = 0.0
#
#         return price
#
#     def _extract_is_direct(self, flight):
#         """Détermine si le vol est direct"""
#         is_direct = True  # Par défaut
#
#         if 'isDirect' in flight:
#             is_direct = bool(flight['isDirect'])
#         elif 'direct' in flight:
#             is_direct = bool(flight['direct'])
#         elif 'stops' in flight:
#             is_direct = flight['stops'] == 0 or flight['stops'] == '0'
#         elif 'stopovers' in flight:
#             is_direct = flight['stopovers'] == 0 or flight['stopovers'] == '0'
#         elif 'segments' in flight and isinstance(flight['segments'], list):
#             is_direct = len(flight['segments']) == 1
#
#         return is_direct
#
#
#     def _get_bookings_count(self, partner_id, email=None):
#         """
#         Obtient le nombre total de réservations pour un partenaire
#
#         :param partner_id: ID du partenaire ou liste d'IDs
#         :param email: Email du client (facultatif)
#         :return: Nombre total de réservations
#         """
#         if isinstance(partner_id, list):
#             partner_ids = partner_id
#         else:
#             partner_ids = [partner_id]
#
#         bookings_count = self.env['booking'].search_count([
#             ('partner_id', 'in', partner_ids),
#             ('state', '=', 'confirmed')
#         ])
#
#         # Si pas assez d'historique avec partner_id, essayer avec email
#         if bookings_count < self.min_booking_history and email:
#             # Chercher d'autres partenaires avec le même email
#             other_partners = self.env['res.partner'].search([
#                 ('email', '=', email),
#                 ('id', 'not in', partner_ids)
#             ])
#
#             if other_partners:
#                 other_partner_ids = other_partners.ids
#                 additional_bookings_count = self.env['booking'].search_count([
#                     ('partner_id', 'in', other_partner_ids),
#                     ('state', '=', 'confirmed')
#                 ])
#
#                 bookings_count += additional_bookings_count
#
#                 # Mettre à jour la liste des partenaires pour l'analyse des préférences
#                 partner_ids.extend(other_partner_ids)
#
#         return bookings_count
#
#     def _get_partner_profile(self, partner_id, email=None):
#         """
#         Récupère le profil des préférences du partenaire
#         avec des listes ordonnées de préférences et catégories
#
#         :param partner_id: ID du partenaire ou liste d'IDs de partenaires
#         :param email: Email du client (facultatif)
#         :return: Profil des préférences
#         """
#         # Gérer le cas où partner_id est une liste
#         if isinstance(partner_id, list):
#             partner_ids = partner_id
#         else:
#             partner_ids = [partner_id]
#
#         # Si email est fourni, ajouter les autres partenaires avec le même email
#         if email:
#             other_partners = self.env['res.partner'].search([
#                 ('email', '=', email),
#                 ('id', 'not in', partner_ids)
#             ])
#             if other_partners:
#                 partner_ids.extend(other_partners.ids)
#
#         # Récupérer les réservations confirmées du/des client(s)
#         domain = [
#             ('partner_id', 'in', partner_ids),
#             ('state', '=', 'confirmed'),
#             ('create_date', '>=', fields.Datetime.now() - timedelta(days=self.max_history_age_days))
#         ]
#
#         bookings = self.env['booking'].search(domain, limit=50)
#
#         # Analyser l'historique pour extraire les préférences
#         airlines = []
#         price_points = []
#         is_direct_list = []
#         departure_times = []  # Pour les préférences d'horaire
#         durations = []  # Pour les préférences de durée
#
#         # Catégories de temps
#         MORNING = 'morning'  # 5h-12h
#         AFTERNOON = 'afternoon'  # 12h-17h
#         EVENING = 'evening'  # 17h-22h
#         NIGHT = 'night'  # 22h-5h
#
#         # Catégories de prix
#         LOW = 'low'
#         MEDIUM = 'medium'
#         HIGH = 'high'
#
#         # Catégories de durée
#         SHORT = 'short'  # < 2h
#         MEDIUM_DURATION = 'medium'  # 2h-5h
#         LONG = 'long'  # > 5h
#
#         # Collecter les données des réservations passées
#         for booking in bookings:
#             airlines.append(booking.airline)
#             price_points.append(booking.price)
#
#             if hasattr(booking, 'is_direct'):
#                 is_direct_list.append(booking.is_direct)
#
#             # Extraire l'heure de départ et la catégoriser
#             if booking.departure_time:
#                 departure_hour = self._extract_hour_from_time(booking.departure_time)
#
#                 # Catégoriser l'heure de départ
#                 if 5 <= departure_hour < 12:
#                     departure_times.append(MORNING)
#                 elif 12 <= departure_hour < 17:
#                     departure_times.append(AFTERNOON)
#                 elif 17 <= departure_hour < 22:
#                     departure_times.append(EVENING)
#                 else:
#                     departure_times.append(NIGHT)
#
#             # Extraire la durée de vol et la catégoriser
#             if hasattr(booking, 'duration'):
#                 duration_hours = self._extract_duration_in_hours(booking.duration)
#
#                 # Catégoriser la durée
#                 if duration_hours < 2:
#                     durations.append(SHORT)
#                 elif 2 <= duration_hours <= 5:
#                     durations.append(MEDIUM_DURATION)
#                 else:
#                     durations.append(LONG)
#
#         # Calculer la moyenne des prix pour catégoriser les préférences de prix
#         avg_price = sum(price_points) / len(price_points) if price_points else 0
#
#         # Catégoriser les réservations précédentes par niveau de prix
#         price_categories = []
#         for price in price_points:
#             if price < avg_price * 0.8:
#                 price_categories.append(LOW)
#             elif price > avg_price * 1.2:
#                 price_categories.append(HIGH)
#             else:
#                 price_categories.append(MEDIUM)
#
#         # Créer des listes ordonnées de préférences
#         profile = {
#             'preferred_airlines': self._get_ordered_preferences(airlines),
#             'avg_price': avg_price,
#             'preferred_price_categories': self._get_ordered_preferences(price_categories),
#             'preferred_departure_times': self._get_ordered_preferences(departure_times),
#             'preferred_durations': self._get_ordered_preferences(durations),
#             'prefers_direct': sum(is_direct_list) / len(is_direct_list) > 0.5 if is_direct_list else True  # Majorité
#         }
#
#         return profile
#
#     def _extract_hour_from_time(self, time_str):
#         """
#         Extrait l'heure d'une chaîne de temps (gère plusieurs formats)
#         """
#         try:
#             # Pour les formats comme "14:30:00" ou "14:30"
#             if isinstance(time_str, str) and ':' in time_str:
#                 return int(time_str.split(':')[0])
#
#             # Pour les objets datetime
#             elif hasattr(time_str, 'hour'):
#                 return time_str.hour
#
#             # Pour les formats numériques (float ou int)
#             elif isinstance(time_str, (int, float)):
#                 return int(time_str)
#
#         except (ValueError, AttributeError, IndexError):
#             pass
#
#         # Valeur par défaut
#         return 12  # Midi par défaut
#
#     def _extract_duration_in_hours(self, duration):
#         """
#         Convertit la durée en heures, quelle que soit sa représentation
#         """
#         try:
#             # Si c'est déjà un nombre
#             if isinstance(duration, (int, float)):
#                 return float(duration)
#
#             # Format "2h30m" ou "2h 30m"
#             elif isinstance(duration, str):
#                 hours = 0
#                 minutes = 0
#
#                 # Extraire les heures
#                 if 'h' in duration:
#                     hours_part = duration.split('h')[0].strip()
#                     hours = float(hours_part) if hours_part else 0
#
#                 # Extraire les minutes
#                 if 'm' in duration:
#                     if 'h' in duration:
#                         minutes_part = duration.split('h')[1].split('m')[0].strip()
#                     else:
#                         minutes_part = duration.split('m')[0].strip()
#                     minutes = float(minutes_part) if minutes_part else 0
#
#                 return hours + (minutes / 60)
#
#         except (ValueError, IndexError):
#             pass
#
#         # Valeur par défaut
#         return 2.0  # 2 heures par défaut
#
#     # def _get_partner_profile(self, partner_id, email=None):
#     #     """
#     #     Récupère le profil des préférences du partenaire
#     #     avec des listes ordonnées de préférences
#     #
#     #     :param partner_id: ID du partenaire ou liste d'IDs de partenaires
#     #     :param email: Email du client (facultatif)
#     #     :return: Profil des préférences
#     #     """
#     #     # Gérer le cas où partner_id est une liste
#     #     if isinstance(partner_id, list):
#     #         partner_ids = partner_id
#     #     else:
#     #         partner_ids = [partner_id]
#     #
#     #     # Si email est fourni, ajouter les autres partenaires avec le même email
#     #     if email:
#     #         other_partners = self.env['res.partner'].search([
#     #             ('email', '=', email),
#     #             ('id', 'not in', partner_ids)
#     #         ])
#     #         if other_partners:
#     #             partner_ids.extend(other_partners.ids)
#     #
#     #     # Récupérer les réservations confirmées du/des client(s)
#     #     domain = [
#     #         ('partner_id', 'in', partner_ids),
#     #         ('state', '=', 'confirmed'),
#     #         ('create_date', '>=', fields.Datetime.now() - timedelta(days=self.max_history_age_days))
#     #     ]
#     #
#     #     bookings = self.env['booking'].search(domain, limit=50)
#     #
#     #     # Analyser l'historique pour extraire les préférences
#     #     airlines = []
#     #     seat_preferences = []
#     #     meal_preferences = []
#     #     price_points = []
#     #     days_of_week = []
#     #     months_of_year = []
#     #
#     #     is_direct_list = []
#     #
#     #     for booking in bookings:
#     #         airlines.append(booking.airline)
#     #         seat_preferences.append(booking.seat_preference)
#     #         meal_preferences.append(booking.meal_preference)
#     #         price_points.append(booking.price)
#     #
#     #
#     #         if hasattr(booking, 'is_direct'):
#     #             is_direct_list.append(booking.is_direct)
#     #
#     #         if booking.departure_date:
#     #             days_of_week.append(booking.departure_date.weekday())
#     #             months_of_year.append(booking.departure_date.month)
#     #
#     #     # Créer des listes ordonnées de préférences
#     #     profile = {
#     #         'preferred_airlines': self._get_ordered_preferences(airlines),
#     #         'preferred_seat': self._get_ordered_preferences(seat_preferences),
#     #         'preferred_meal': self._get_ordered_preferences(meal_preferences),
#     #         'avg_price': sum(price_points) / len(price_points) if price_points else 0,
#     #         'preferred_days': self._get_ordered_preferences(days_of_week),
#     #         'preferred_months': self._get_ordered_preferences(months_of_year),
#     #         'prefers_direct': sum(is_direct_list) / len(is_direct_list) > 0.5 if is_direct_list else True  # Majorité
#     #     }
#     #     return profile
#
#     def _get_ordered_preferences(self, lst):
#         """
#         Crée une liste ordonnée de préférences, du plus fréquent au moins fréquent
#
#         :param lst: Liste d'éléments
#         :return: Liste ordonnée des éléments par fréquence décroissante
#         """
#         if not lst:
#             return []
#
#         # Utiliser Counter pour compter les occurrences
#         counter = Counter(lst)
#
#         # Trier par fréquence décroissante
#         ordered_items = [item for item, count in counter.most_common()]
#
#         return ordered_items
#
#
#
#     @api.model
#     def schedule_training(self):
#         """Planifie l'entraînement du modèle (pour cron job)"""
#         model = self.get_active_model()
#         if model:
#             success = model._train_model()
#             if success:
#                 _logger.info(
#                     f"Entraînement réussi - KNN Accuracy: {model.knn_accuracy:.4f}, RF Accuracy: {model.rf_accuracy:.4f}, Hybrid Accuracy: {model.hybrid_accuracy:.4f}")
#             else:
#                 _logger.warning("Échec de l'entraînement du modèle")
#         else:
#             # Créer un nouveau modèle si aucun n'existe
#             model = self.create({'name': 'Modèle de recommandation'})
#             success = model._train_model()
#             if success:
#                 _logger.info(
#                     f"Nouveau modèle créé et entraîné - KNN Accuracy: {model.knn_accuracy:.4f}, RF Accuracy: {model.rf_accuracy:.4f}, Hybrid Accuracy: {model.hybrid_accuracy:.4f}")
#         return True
#
#     def _train_model(self):
#         """Entraîne le modèle de recommandation sur les données historiques"""
#         self.ensure_one()
#         _logger.info("Début de l'entraînement du modèle de recommandation")
#
#         # Récupérer les données historiques
#         bookings = self.env['booking'].search([
#             ('state', '=', 'confirmed'),
#             ('create_date', '>=', fields.Datetime.now() - timedelta(days=self.max_history_age_days))
#         ])
#
#         _logger.info(f"Nombre de réservations récupérées pour l'entraînement: {len(bookings)}")
#
#         if not bookings or len(bookings) < 10:
#             _logger.warning(
#                 f"Pas suffisamment de données pour entraîner le modèle: {len(bookings)} réservations trouvées")
#             return False
#
#         # Transformer les données en DataFrame
#         data = []
#         for booking in bookings:
#             # Récupérer les détails du vol principal
#             data.append({
#                 'partner_id': booking.partner_id.id,
#                 'airline': booking.airline,
#                 'flight_number': booking.flight_number,
#                 'departure_date': booking.departure_date,
#                 'departure_time': booking.departure_time,
#                 'arrival_date': booking.arrival_date,
#                 'arrival_time': booking.arrival_time,
#                 'price': booking.price,
#                 'seat_preference': booking.seat_preference,
#                 'meal_preference': booking.meal_preference,
#                 'day_of_week': booking.departure_date.weekday() if booking.departure_date else 0,
#                 'month_of_year': booking.departure_date.month if booking.departure_date else 1,
#                 'is_direct': booking.is_direct if hasattr(booking, 'is_direct') else True,
#             })
#
#         df = pd.DataFrame(data)
#         _logger.info(f"DataFrame créé avec {len(df)} lignes et {len(df.columns)} colonnes")
#         _logger.info(f"Colonnes disponibles: {df.columns.tolist()}")
#         _logger.info(
#             f"Statistiques des prix: min={df['price'].min()}, max={df['price'].max()}, mean={df['price'].mean()}")
#
#         # Préparation des caractéristiques
#         categorical_features = ['airline', 'seat_preference', 'meal_preference', 'day_of_week', 'month_of_year']
#         numerical_features = ['price']
#         binary_features = ['is_direct']
#
#         # Vérifier si tous les features existent
#         for feature in categorical_features + numerical_features + binary_features:
#             if feature not in df.columns:
#                 _logger.warning(f"Caractéristique manquante: {feature}")
#                 if feature in categorical_features:
#                     df[feature] = 'unknown'  # Valeur par défaut pour catégories
#                 elif feature == 'price':
#                     df[feature] = df['price'].mean() if 'price' in df else 0.0
#                 else:
#                     df[feature] = False if feature == 'is_direct' else 0
#
#         # Encoder les variables catégorielles
#         encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
#         categorical_encoded = encoder.fit_transform(df[categorical_features])
#         _logger.info(f"Encodage terminé: {categorical_encoded.shape} caractéristiques catégorielles encodées")
#
#         # Normaliser les variables numériques
#         scaler = StandardScaler()
#         numerical_scaled = scaler.fit_transform(df[numerical_features])
#         _logger.info(f"Normalisation terminée: {numerical_scaled.shape} caractéristiques numériques normalisées")
#
#         # Ajouter les variables binaires (si présentes)
#         binary_data = df[binary_features].values if binary_features and all(
#             f in df.columns for f in binary_features) else np.array([]).reshape(len(df), 0)
#         _logger.info(f"Variables binaires: {binary_data.shape}")
#
#         # Combiner toutes les caractéristiques
#         features = np.hstack((categorical_encoded, numerical_scaled, binary_data))
#         _logger.info(f"Matrice de caractéristiques combinées: {features.shape}")
#
#         # Créer et entraîner les modèles
#         # 1. K-Nearest Neighbors
#         knn_model = NearestNeighbors(n_neighbors=min(5, len(features)), algorithm='ball_tree')
#         knn_model.fit(features)
#         _logger.info("Modèle KNN entraîné avec succès")
#
#         # 2. Random Forest pour classification/recommandation
#         # Création d'une cible plus robuste basée sur les prix
#         try:
#             # Vérifier que les prix ne sont pas tous identiques
#             price_unique_count = df['price'].nunique()
#             _logger.info(f"Nombre de prix uniques: {price_unique_count}")
#
#             if price_unique_count >= 4:
#                 price_quartiles = pd.qcut(df['price'], 4, labels=False, duplicates='drop')
#             else:
#                 # Si moins de 4 valeurs uniques, utiliser une approche binaire
#                 price_median = df['price'].median()
#                 price_quartiles = (df['price'] > price_median).astype(int)
#
#             _logger.info(f"Distribution des quartiles de prix: {pd.Series(price_quartiles).value_counts().to_dict()}")
#
#             rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
#             rf_model.fit(features, price_quartiles)
#             _logger.info("Modèle Random Forest entraîné avec succès")
#         except Exception as e:
#             _logger.error(f"Erreur lors de l'entraînement du Random Forest: {str(e)}")
#             # Approche alternative si qcut échoue
#             price_median = df['price'].median()
#             price_quartiles = (df['price'] > price_median).astype(int)
#             rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
#             rf_model.fit(features, price_quartiles)
#             _logger.info("Modèle Random Forest entraîné avec approche alternative")
#
#         # Évaluer les modèles avec la fonction d'évaluation améliorée
#         evaluation_metrics = self._evaluate_model(df, features, price_quartiles)
#
#         _logger.info(f"Métriques d'évaluation: {evaluation_metrics}")
#
#         # Sauvegarder les modèles
#         knn_binary = pickle.dumps(knn_model)
#         rf_binary = pickle.dumps(rf_model)
#         encoder_binary = pickle.dumps(encoder)
#         scaler_binary = pickle.dumps(scaler)
#
#         self.write({
#             'model_data': base64.b64encode(knn_binary),
#             'second_model_data': base64.b64encode(rf_binary),
#             'encoder_data': base64.b64encode(encoder_binary),
#             'scaler_data': base64.b64encode(scaler_binary),
#             'last_training_date': fields.Datetime.now(),
#             'training_sample_size': len(df),
#             'feature_count': features.shape[1],
#             'knn_accuracy': evaluation_metrics.get('knn_accuracy', 0.5),  # Valeur par défaut si non défini
#             'rf_accuracy': evaluation_metrics.get('rf_accuracy', 0.5),  # Valeur par défaut si non défini
#             'hybrid_accuracy': evaluation_metrics.get('hybrid_accuracy', 0.5)  # Valeur par défaut si non défini
#         })
#
#         _logger.info(f"Modèles entraînés avec succès sur {len(df)} exemples")
#         return True
#
#     def _evaluate_model(self, df=None, features=None, target=None):
#         """
#         Évalue la performance du modèle avec validation croisée
#         et calcule les métriques de performance
#
#         :param df: DataFrame avec les données (optionnel)
#         :param features: Matrice de caractéristiques pré-calculée (optionnel)
#         :param target: Cible pré-calculée (optionnel)
#         :return: Dictionnaire des métriques
#         """
#         _logger.info("Début de l'évaluation du modèle")
#
#         metrics = {
#             'knn_accuracy': 0.5,  # Valeurs par défaut raisonnables
#             'rf_accuracy': 0.5,  # plutôt que zéro
#             'hybrid_accuracy': 0.5,
#         }
#
#         # Si les données ne sont pas fournies, les récupérer
#         if df is None or features is None or target is None:
#             # Récupérer les données d'entraînement
#             bookings = self.env['booking'].search([
#                 ('state', '=', 'confirmed'),
#                 ('create_date', '>=', fields.Datetime.now() - timedelta(days=self.max_history_age_days))
#             ])
#
#             _logger.info(f"Évaluation: {len(bookings)} réservations récupérées")
#
#             if len(bookings) < 20:  # Minimum pour une évaluation fiable
#                 _logger.warning("Données insuffisantes pour une évaluation fiable")
#                 return metrics
#
#             # Transformer les données
#             data = []
#             for booking in bookings:
#                 data.append({
#                     'partner_id': booking.partner_id.id,
#                     'airline': booking.airline,
#                     'flight_number': booking.flight_number,
#                     'departure_date': booking.departure_date,
#                     'departure_time': booking.departure_time,
#                     'arrival_date': booking.arrival_date,
#                     'arrival_time': booking.arrival_time,
#                     'price': booking.price,
#                     'seat_preference': booking.seat_preference,
#                     'meal_preference': booking.meal_preference,
#                     'day_of_week': booking.departure_date.weekday() if booking.departure_date else 0,
#                     'month_of_year': booking.departure_date.month if booking.departure_date else 1,
#                     'is_direct': booking.is_direct if hasattr(booking, 'is_direct') else True,
#                 })
#
#             df = pd.DataFrame(data)
#             _logger.info(f"Évaluation: DataFrame créé avec {len(df)} lignes")
#
#             # Préparation des caractéristiques
#             categorical_features = ['airline', 'seat_preference', 'meal_preference', 'day_of_week', 'month_of_year']
#             numerical_features = ['price']
#             binary_features = ['is_direct']
#
#             # Vérifier les features manquants
#             for feature in categorical_features + numerical_features + binary_features:
#                 if feature not in df.columns:
#                     if feature in categorical_features:
#                         df[feature] = 'unknown'
#                     elif feature == 'price':
#                         df[feature] = df['price'].mean() if 'price' in df else 0.0
#                     else:
#                         df[feature] = False if feature == 'is_direct' else 0
#
#             # Encoder les variables catégorielles
#             encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
#             categorical_encoded = encoder.fit_transform(df[categorical_features])
#
#             # Normaliser les variables numériques
#             scaler = StandardScaler()
#             numerical_scaled = scaler.fit_transform(df[numerical_features])
#
#             # Ajouter les variables binaires
#             binary_data = df[binary_features].values if binary_features and all(
#                 f in df.columns for f in binary_features) else np.array([]).reshape(len(df), 0)
#
#             # Combiner toutes les caractéristiques
#             features = np.hstack((categorical_encoded, numerical_scaled, binary_data))
#
#             # Créer une cible pour l'évaluation
#             try:
#                 if df['price'].nunique() >= 4:
#                     target = pd.qcut(df['price'], 4, labels=False, duplicates='drop')
#                 else:
#                     # Si moins de 4 valeurs uniques, utiliser une approche binaire
#                     price_median = df['price'].median()
#                     target = (df['price'] > price_median).astype(int)
#
#                 _logger.info(f"Distribution des cibles: {pd.Series(target).value_counts().to_dict()}")
#             except Exception as e:
#                 _logger.error(f"Erreur lors de la création de la cible: {str(e)}")
#                 # Approche par défaut si qcut échoue
#                 price_median = df['price'].median()
#                 target = (df['price'] > price_median).astype(int)
#
#         # Vérification que les données sont suffisantes
#         if len(df) < 10 or np.unique(target).size < 2:
#             _logger.warning(
#                 f"Données insuffisantes pour l'évaluation: {len(df)} lignes, {np.unique(target).size} classes")
#             return metrics
#
#         try:
#             # Diviser les données en ensembles d'entraînement et de test
#             X_train, X_test, y_train, y_test = train_test_split(
#                 features, target, test_size=0.25, random_state=42, stratify=target
#             )
#
#             _logger.info(f"Ensembles de données divisés: Train={X_train.shape}, Test={X_test.shape}")
#
#             # Évaluer le modèle KNN
#             if self.algorithm_type in ['knn', 'hybrid']:
#                 # Pour KNN, nous devons adapter pour la classification
#                 from sklearn.neighbors import KNeighborsClassifier
#                 knn_clf = KNeighborsClassifier(n_neighbors=min(5, len(X_train)))
#
#                 # Entraînement avec gestion d'erreurs
#                 try:
#                     knn_clf.fit(X_train, y_train)
#                     y_pred_knn = knn_clf.predict(X_test)
#                     metrics['knn_accuracy'] = accuracy_score(y_test, y_pred_knn)
#
#                     # Calcul des métriques supplémentaires
#                     metrics['knn_precision'] = precision_score(y_test, y_pred_knn, average='weighted', zero_division=0)
#                     metrics['knn_recall'] = recall_score(y_test, y_pred_knn, average='weighted', zero_division=0)
#                     metrics['knn_f1'] = f1_score(y_test, y_pred_knn, average='weighted', zero_division=0)
#
#                     _logger.info(f"KNN - Accuracy: {metrics['knn_accuracy']:.4f}")
#                 except Exception as e:
#                     _logger.error(f"Erreur lors de l'évaluation KNN: {str(e)}")
#
#             # Évaluer le modèle Random Forest
#             if self.algorithm_type in ['random_forest', 'hybrid']:
#                 rf_clf = RandomForestClassifier(n_estimators=100, random_state=42)
#
#                 # Entraînement avec gestion d'erreurs
#                 try:
#                     rf_clf.fit(X_train, y_train)
#                     y_pred_rf = rf_clf.predict(X_test)
#                     metrics['rf_accuracy'] = accuracy_score(y_test, y_pred_rf)
#
#                     # Calcul des métriques supplémentaires
#                     metrics['rf_precision'] = precision_score(y_test, y_pred_rf, average='weighted', zero_division=0)
#                     metrics['rf_recall'] = recall_score(y_test, y_pred_rf, average='weighted', zero_division=0)
#                     metrics['rf_f1'] = f1_score(y_test, y_pred_rf, average='weighted', zero_division=0)
#
#                     _logger.info(f"Random Forest - Accuracy: {metrics['rf_accuracy']:.4f}")
#                 except Exception as e:
#                     _logger.error(f"Erreur lors de l'évaluation Random Forest: {str(e)}")
#
#             # Calcul des métriques hybrides si applicable
#             if self.algorithm_type == 'hybrid':
#                 metrics['hybrid_accuracy'] = (metrics.get('knn_accuracy', 0.5) + metrics.get('rf_accuracy', 0.5)) / 2
#                 metrics['hybrid_precision'] = (metrics.get('knn_precision', 0.5) + metrics.get('rf_precision', 0.5)) / 2
#                 metrics['hybrid_recall'] = (metrics.get('knn_recall', 0.5) + metrics.get('rf_recall', 0.5)) / 2
#                 metrics['hybrid_f1'] = (metrics.get('knn_f1', 0.5) + metrics.get('rf_f1', 0.5)) / 2
#
#                 _logger.info(f"Hybrid - Accuracy: {metrics['hybrid_accuracy']:.4f}")
#
#         except Exception as e:
#             _logger.error(f"Erreur générale lors de l'évaluation du modèle: {str(e)}")
#             # Garder les valeurs par défaut définies au début
#
#         _logger.info(f"Évaluation du modèle terminée: {metrics}")
#         return metrics