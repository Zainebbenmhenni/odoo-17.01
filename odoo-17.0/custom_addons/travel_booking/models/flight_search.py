from odoo import models, fields, api
import json
from datetime import datetime
import logging
from odoo.exceptions import UserError
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class FlightBooking(models.Model):
    _name = 'flight.booking'
    _description = 'Flight Booking'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    origin_airport = fields.Char(string='Aéroport de départ', required=True)
    destination_airport = fields.Char(string='Aéroport d\'arrivée', required=True)
    origin = fields.Char(string='Origine', required=True)
    destination = fields.Char(string='Destination', required=True)
    departure_date = fields.Date(string='Date de départ', required=True)
    travel_class = fields.Selection([
        ('Economy', 'Economy'),
        ('Business', 'Affaires')
    ], string='Classe', default='Economy')

    adult_count = fields.Integer(string='Adultes', default=1)
    child_count = fields.Integer(string='Enfants', default=0)
    infant_count = fields.Integer(string='Bébés', default=0)

    # Correction de la définition One2many
    flight_lines = fields.One2many(
        'flight.booking.line',
        'booking_id',
        string='Vols disponibles'
    )
    flight_results = fields.Text(string='Résultats bruts', store=True)
    trip_type = fields.Selection([
        ('OneWay', 'Aller simple'),
        ('RoundTrip', 'Aller-retour'),
        ('MultiCity', 'Multi-destinations')
    ], string='Type de voyage', default='OneWay', required=True)

    # Ajoutez aussi un champ pour la date de retour si besoin
    return_date = fields.Date(string='Date de retour')
    recommendation_enabled = fields.Boolean('Activer les recommandations', default=True,
                                            help="Trier les résultats selon les préférences du client")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('flight.booking') or 'New'
        return super().create(vals)

    def _apply_recommendations(self, flight_results):
        """Applique les recommandations aux résultats de vols si activé"""
        # Si les recommandations ne sont pas activées ou si l'utilisateur n'est pas connecté, retourner les résultats tels quels
        if not self.recommendation_enabled or self.env.user.id == self.env.ref('base.public_user').id:
            return flight_results

        # Récupérer ou créer un modèle de recommandation
        recommendation_model = self.env['flight.recommendation.model'].get_active_model()
        if not recommendation_model:
            _logger.info("Aucun modèle de recommandation disponible - création d'un nouveau modèle")
            recommendation_model = self.env['flight.recommendation.model'].create({
                'name': 'Modèle de recommandation auto-créé',
                'active': True
            })
            # Entraîner le nouveau modèle
            try:
                recommendation_model._train_model()
            except Exception as e:
                _logger.error(f"Échec de l'entraînement du nouveau modèle: {str(e)}")
                return flight_results

        # Obtenir l'ID du partenaire courant et son email
        partner_id = self.env.user.partner_id.id
        user_email = self.env.user.partner_id.email

        # Trier les résultats par préférence
        try:
            # Obtenir la liste des vols
            flights = flight_results.get('response', {}).get('flights', [])

            if flights:
                # Appliquer la recommandation
                sorted_flights = recommendation_model.sort_flights_by_preference(
                    partner_id=partner_id,
                    flights_data=flights,
                    email=user_email
                )

                # Mettre à jour les résultats
                flight_results['response']['flights'] = sorted_flights

                # Mettre à jour les lignes de vol existantes avec les scores de recommandation
                for flight in sorted_flights:
                    flight_number = flight.get('flightNumber', '')
                    is_return = flight.get('isReturn', False)

                    # Chercher la ligne de vol correspondante
                    flight_lines = self.flight_lines.filtered(
                        lambda l: l.flight_number == flight_number and l.is_return == is_return
                    )

                    if flight_lines:
                        flight_lines.write({
                            'recommendation_score': flight.get('recommendation_score', 0.0),
                            'is_recommended': flight.get('is_recommended', False)
                        })

                # Sauvegarder les résultats triés
                self.flight_results = json.dumps(flight_results)

                _logger.info(f"Recommandations appliquées pour le partenaire {partner_id}, {len(flights)} vols triés")

        except Exception as e:
            _logger.error(f"Erreur lors de l'application des recommandations: {str(e)}")

        return flight_results

    # def _apply_recommendations(self, flight_results):
    #     """Applique les recommandations aux résultats de vols si activé"""
    #     # Si les recommandations ne sont pas activées ou si l'utilisateur n'est pas connecté, retourner les résultats tels quels
    #     if not self.recommendation_enabled or self.env.user.id == self.env.ref('base.public_user').id:
    #         return flight_results
    #
    #     # Récupérer le modèle de recommandation actif
    #     recommendation_model = self.env['flight.recommendation.model'].get_active_model()
    #     if not recommendation_model:
    #         _logger.info("Aucun modèle de recommandation disponible")
    #         return flight_results
    #
    #     # Obtenir l'ID du partenaire courant et son email
    #     partner_id = self.env.user.partner_id.id
    #     user_email = self.env.user.partner_id.email
    #
    #     # Trier les résultats par préférence
    #     try:
    #         # Obtenir la liste des vols
    #         flights = flight_results.get('response', {}).get('flights', [])
    #
    #         if flights:
    #             # Appliquer la recommandation - CORRECTION: utiliser 'flights' au lieu de 'flights_data'
    #             sorted_flights = recommendation_model.sort_flights_by_preference(
    #                 partner_id=partner_id,
    #                 flights_data=flights,  # Ici nous utilisons 'flights' au lieu de 'flights_data'
    #                 email=user_email
    #             )
    #
    #             # Mettre à jour les résultats
    #             flight_results['response']['flights'] = sorted_flights
    #
    #             # Mettre à jour les lignes de vol existantes avec les scores de recommandation
    #             for flight in sorted_flights:
    #                 flight_number = flight.get('flightNumber', '')
    #                 is_return = flight.get('isReturn', False)
    #
    #                 # Chercher la ligne de vol correspondante
    #                 flight_lines = self.flight_lines.filtered(
    #                     lambda l: l.flight_number == flight_number and l.is_return == is_return
    #                 )
    #
    #                 if flight_lines:
    #                     flight_lines.write({
    #                         'recommendation_score': flight.get('recommendation_score', 0.0),
    #                         'is_recommended': flight.get('is_recommended', False)
    #                     })
    #
    #             # Sauvegarder les résultats triés
    #             self.flight_results = json.dumps(flight_results)
    #
    #             _logger.info(f"Recommandations appliquées pour le partenaire {partner_id}, {len(flights)} vols triés")
    #
    #     except Exception as e:
    #         _logger.error(f"Erreur lors de l'application des recommandations: {str(e)}")
    #
    #     return flight_results
    def action_search_flights(self):
        """Méthode principale de recherche de vols avec recommandations"""
        self.ensure_one()
        # Vérifier si un modèle de recommandation existe et est entraîné
        if self.recommendation_enabled:
            recommendation_model = self.env['flight.recommendation.model'].get_active_model()
            if not recommendation_model:
                # Créer un nouveau modèle si aucun n'existe
                recommendation_model = self.env['flight.recommendation.model'].create({
                    'name': 'Modèle de recommandation automatique',
                    'active': True
                })

            # Si le modèle n'a jamais été entraîné ou n'a pas été entraîné récemment
            if not recommendation_model.last_training_date or \
                    (recommendation_model.last_training_date and
                     fields.Datetime.from_string(recommendation_model.last_training_date) <
                     fields.Datetime.from_string(fields.Datetime.now()) - timedelta(days=7)):
                # Entraîner le modèle
                _logger.info("Entraînement automatique du modèle de recommandation")
                recommendation_model._train_model()

        # Étape 1: Effectuer la recherche de base
        results = self._perform_base_flight_search()

        # Si l'utilisateur est connecté et que les recommandations sont activées
        if self.recommendation_enabled and self.env.user.id != self.env.ref('base.public_user').id:
            # Récupérer le modèle de recommandation
            recommendation_model = self.env['flight.recommendation.model'].get_active_model()
            if recommendation_model:
                # Obtenir l'ID du partenaire courant
                partner_id = self.env.user.partner_id.id

                # Appliquer la recommandation sur les résultats de vol
                flights = results.get('response', {}).get('flights', [])
                if flights:
                    # Trier les vols par préférence
                    sorted_flights = recommendation_model.sort_flights_by_preference(partner_id, flights)
                    # Mettre à jour les résultats
                    results['response']['flights'] = sorted_flights
                    # Sauvegarder les résultats triés
                    self.flight_results = json.dumps(results)

                    # Mettre à jour les lignes de vol avec les scores de recommandation
                    for flight in sorted_flights:
                        for segment in flight.get('segments', []):
                            for seg in segment.get('segment', []):
                                flight_number = seg.get('flightNumber', '')
                                # Trouver la ligne correspondante et mettre à jour le score
                                matching_lines = self.flight_lines.filtered(
                                    lambda l: l.flight_number == flight_number
                                )
                                if matching_lines:
                                    matching_lines.write({
                                        'recommendation_score': flight.get('recommendation_score', 0.0),
                                        'is_recommended': flight.get('is_recommended', False)
                                    })

        # Retourner l'action de rechargement
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _perform_base_flight_search(self):
        """Base method to perform the flight search API call and process results"""
        self.ensure_one()
        flight_api = self.env['flight.api']

        # Supprimer les anciennes lignes
        self.flight_lines.unlink()

        params = {
            'originAirport': self.origin_airport,
            'destinationAirport': self.destination_airport,
            'depart': self.departure_date.strftime("%Y-%m-%d"),
            'adult': str(self.adult_count),
            'child': str(self.child_count),
            'infant': str(self.infant_count),
            'class': self.travel_class,
            'tripType': self.trip_type,
            'partner_id': self.env.user.partner_id.id
        }

        # Ajouter la date de retour si c'est un aller-retour
        if self.trip_type == 'RoundTrip' and self.return_date:
            params['return'] = self.return_date.strftime("%Y-%m-%d")

        _logger.info(f"Paramètres de recherche: {params}")

        try:
            results = flight_api.search_flights(params)

            # Vérification que results n'est pas None
            if not results:
                raise UserError("Aucun résultat n'a été retourné par l'API.")

            # Conversion en dict si c'est une string
            if isinstance(results, str):
                try:
                    results = json.loads(results)
                except json.JSONDecodeError:
                    raise UserError("Format de réponse invalide")

            # Vérification de la structure des résultats
            if not isinstance(results, dict):
                raise UserError("Format de réponse inattendu")

            response = results.get('response')
            if not response:
                raise UserError("Pas de données de réponse dans les résultats")

            flights = response.get('flights', [])
            if not flights:
                raise UserError("Aucun vol trouvé pour ces critères")

            # Si les recommandations sont activées et l'utilisateur est connecté
            if self.recommendation_enabled and self.env.user.id != self.env.ref('base.public_user').id:
                recommendation_model = self.env['flight.recommendation.model'].get_active_model()
                if recommendation_model:
                    partner_id = self.env.user.partner_id.id
                    email = self.env.user.partner_id.email
                    flights = recommendation_model.sort_flights_by_preference(partner_id, flights, email)

            # Création des lignes de vol
            for flight in flights:
                is_return = flight.get('isReturn', False)

                # Pour chaque segment de vol
                segments = flight.get('segments', [])
                if not segments and 'departDateTime' in flight:
                    # Si les segments ne sont pas définis mais que nous avons des données de vol direct
                    self._create_flight_line_from_direct_flight(flight, is_return)
                else:
                    for segment in segments:
                        seg_list = segment.get('segment', [])
                        if not seg_list and 'departDateTime' in segment:
                            # Si c'est un segment direct
                            self._create_flight_line_from_segment(segment, flight, is_return)
                        else:
                            for seg in seg_list:
                                self._create_flight_line_from_segment(seg, flight, is_return)

            # Sauvegarde des résultats bruts (avec les scores de recommandation)
            self.flight_results = json.dumps(results)
            return results

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Erreur lors de la recherche de vols: {error_msg}")
            raise UserError(f"Erreur lors de la recherche : {error_msg}")

    def _create_flight_line_from_direct_flight(self, flight, is_return=False):
        """Créer une ligne de vol à partir d'un vol direct"""
        try:
            # Vérification des données requises
            if not all([
                flight.get('airlines', {}).get('full') or flight.get('airline'),
                flight.get('flightNumber'),
                flight.get('departDateTime'),
                flight.get('arrivalDateTime')
            ]):
                _logger.warning(f"Données de vol incomplètes: {flight}")
                return False

            # Construction des dates
            dep_datetime = None
            arr_datetime = None

            # Traitement de la date/heure de départ
            if isinstance(flight['departDateTime'], dict):
                dep_date = flight['departDateTime'].get('date', '')
                dep_time = flight['departDateTime'].get('time', '')
                if dep_date and dep_time:
                    dep_datetime = f"{dep_date} {dep_time}"
            elif isinstance(flight['departDateTime'], str):
                dep_datetime = flight['departDateTime']

            # Traitement de la date/heure d'arrivée
            if isinstance(flight['arrivalDateTime'], dict):
                arr_date = flight['arrivalDateTime'].get('date', '')
                arr_time = flight['arrivalDateTime'].get('time', '')
                if arr_date and arr_time:
                    arr_datetime = f"{arr_date} {arr_time}"
            elif isinstance(flight['arrivalDateTime'], str):
                arr_datetime = flight['arrivalDateTime']

            # Déterminer la compagnie aérienne
            airline = flight.get('airlines', {}).get('full') or flight.get('airline', 'Unknown')

            # Création de la ligne de vol avec les informations de recommandation
            self.env['flight.booking.line'].create({
                'booking_id': self.id,
                'airline': airline,
                'flight_number': flight.get('flightNumber', ''),
                'departure_date': dep_datetime,
                'arrival_date': arr_datetime,
                'duration': flight.get('duration', ''),
                'price': float(flight.get('price', 0)),
                'currency': flight.get('currency', 'BDT'),
                'baggage': f"{flight.get('baggageWeight', '')} {flight.get('baggageUnit', '')}",
                'travel_class': flight.get('cabin', 'Economy'),
                'recommendation_score': flight.get('recommendation_score', 0.0),
                'is_recommended': flight.get('is_recommended', False),
                'is_return': is_return
            })
            return True
        except Exception as e:
            _logger.error(f"Erreur lors de la création d'une ligne de vol: {str(e)}")
            return False

    def _create_flight_line_from_segment(self, segment, flight, is_return=False):
        """Créer une ligne de vol à partir d'un segment"""
        try:
            # Vérification des données requises
            if not all([
                segment.get('airlines', {}).get('full') or segment.get('airline'),
                segment.get('flightNumber'),
                segment.get('departureDateTime') or segment.get('departDateTime'),
                segment.get('arrivalDateTime') or segment.get('arrivalDateTime')
            ]):
                _logger.warning(f"Données de segment incomplètes")
                return False

            # Extraction des données de date/heure
            dep_dict = segment.get('departureDateTime') or segment.get('departDateTime')
            arr_dict = segment.get('arrivalDateTime') or segment.get('arrivalDateTime')

            dep_datetime = None
            arr_datetime = None

            # Traitement de la date/heure de départ
            if isinstance(dep_dict, dict):
                dep_date = dep_dict.get('date', '')
                dep_time = dep_dict.get('time', '')
                if dep_date and dep_time:
                    dep_datetime = f"{dep_date} {dep_time}"
            elif isinstance(dep_dict, str):
                dep_datetime = dep_dict

            # Traitement de la date/heure d'arrivée
            if isinstance(arr_dict, dict):
                arr_date = arr_dict.get('date', '')
                arr_time = arr_dict.get('time', '')
                if arr_date and arr_time:
                    arr_datetime = f"{arr_date} {arr_time}"
            elif isinstance(arr_dict, str):
                arr_datetime = arr_dict

            # Déterminer la compagnie aérienne
            airline = segment.get('airlines', {}).get('full') or segment.get('airline', 'Unknown')

            # Création de la ligne de vol avec les informations de recommandation
            self.env['flight.booking.line'].create({
                'booking_id': self.id,
                'airline': airline,
                'flight_number': segment.get('flightNumber', ''),
                'departure_date': dep_datetime,
                'arrival_date': arr_datetime,
                'duration': segment.get('duration', flight.get('duration', '')),
                'price': float(flight.get('price', 0)),  # Prix du vol complet
                'currency': flight.get('currency', 'BDT'),
                'baggage': f"{segment.get('baggageWeight', flight.get('baggageWeight', ''))} {segment.get('baggageUnit', flight.get('baggageUnit', ''))}",
                'travel_class': segment.get('cabin', flight.get('cabin', 'Economy')),
                'recommendation_score': flight.get('recommendation_score', 0.0),
                'is_recommended': flight.get('is_recommended', False),
                'is_return': is_return
            })
            return True
        except Exception as e:
            _logger.error(f"Erreur lors de la création d'une ligne de vol: {str(e)}")
            return False
