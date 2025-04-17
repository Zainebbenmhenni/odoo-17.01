from odoo import models, fields
from odoo.exceptions import UserError
import http.client
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class FlightAPI(models.AbstractModel):
    _name = 'flight.api'
    _description = 'Amadeus Flight Search API Integration'

    # Removed problematic __init__ method

    def _get_api_credentials(self):
        # Identifiants codés en dur (à utiliser uniquement en développement)
        return {
            'api_key': 'gI1YHhAF1p5rG9ORm16MHwwH8oIH3i90',
            'api_secret': 'mV3vOseqavcGaI3T'
        }

    def _get_auth_token(self):
        """Obtenir un token d'authentification Amadeus"""
        try:
            credentials = self._get_api_credentials()

            # Ajouter des logs pour débugger
            _logger.info(f"Tentative d'authentification avec API Amadeus (endpoint: test.api.amadeus.com)")

            conn = http.client.HTTPSConnection("test.api.amadeus.com")
            payload = f"grant_type=client_credentials&client_id={credentials['api_key']}&client_secret={credentials['api_secret']}"

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            conn.request("POST", "/v1/security/oauth2/token", payload, headers)
            response = conn.getresponse()
            data = json.loads(response.read().decode('utf-8'))

            _logger.info(f"Réponse auth API: {data}")

            if 'access_token' not in data:
                _logger.error(f"Échec d'authentification: {data}")
                return None

            return data.get('access_token')
        except Exception as e:
            _logger.error(f"Erreur lors de l'authentification API: {str(e)}")
            return None

    def search_flights(self, params):
        try:
            token = self._get_auth_token()
            if not token:
                return {"error": "Impossible d'obtenir un token d'authentification"}

            conn = http.client.HTTPSConnection("test.api.amadeus.com")

            # Conversion des paramètres pour l'API Amadeus
            originLocationCode = params.get('originAirport')
            destinationLocationCode = params.get('destinationAirport')
            departureDate = params.get('depart')
            returnDate = params.get('return', '')
            adults = params.get('adult', '1')
            children = params.get('child', '0')
            infants = params.get('infant', '0')

            # Vérifier que tripType est bien défini
            tripType = params.get('tripType', 'OneWay')

            # Conversion de la classe
            travel_class_map = {
                'Economy': 'ECONOMY',
                'Business': 'BUSINESS',
                'ECONOMY': 'ECONOMY',
                'BUSINESS': 'BUSINESS'
            }
            travelClass = travel_class_map.get(params.get('class', 'Economy'), 'ECONOMY')

            # Construction de l'URL
            url = f"/v2/shopping/flight-offers"
            query_params = [
                f"originLocationCode={originLocationCode}",
                f"destinationLocationCode={destinationLocationCode}",
                f"departureDate={departureDate}",
                f"adults={adults}"
            ]

            # Ajouter la date de retour si aller-retour
            if tripType == 'RoundTrip' and returnDate:
                query_params.append(f"returnDate={returnDate}")

            # Ajouter d'autres paramètres si présents
            if children != '0':
                query_params.append(f"children={children}")
            if infants != '0':
                query_params.append(f"infants={infants}")
            if travelClass != 'ECONOMY':
                query_params.append(f"travelClass={travelClass}")

            # Possibilité d'ajouter des paramètres supplémentaires
            query_params.append("nonStop=false")  # Pour permettre les vols avec escales

            # Composer l'URL finale avec les paramètres
            url_with_params = f"{url}?{'&'.join(query_params)}"
            _logger.info(f"URL API Amadeus: {url_with_params}")

            headers = {
                'Authorization': f'Bearer {token}'
            }

            # Faire la requête avec l'URL complète
            conn.request("GET", url_with_params, headers=headers)
            response = conn.getresponse()
            data = response.read()

            # Log de la réponse brute pour débogage
            _logger.info(f"Statut réponse API: {response.status}")
            raw_response = json.loads(data.decode('utf-8'))
            _logger.info(f"Structure réponse API: {list(raw_response.keys())}")

            # Vérifie la présence d'erreurs dans la réponse
            if "errors" in raw_response:
                error_details = raw_response["errors"][0]["detail"]
                _logger.error(f"Erreur API: {error_details}")
                return {"error": error_details}

            # Vérifie la présence de données dans la réponse
            if "data" not in raw_response:
                _logger.error(f"Pas de données dans la réponse API: {raw_response}")
                # Plutôt que de renvoyer une erreur, on peut retourner une structure vide
                return {"response": {"flights": []}}

            # Transformation de la réponse
            transformed_response = self._transform_amadeus_response(raw_response, params)
            return transformed_response

        except Exception as e:
            _logger.error(f"Exception lors de la recherche: {str(e)}")
            return {"error": str(e)}

    def _transform_amadeus_response(self, amadeus_response, original_params):
        """
        Transforme la réponse Amadeus au format attendu par l'application
        """
        try:
            response = {"response": {"flights": []}}

            # Si erreur dans la réponse
            if "errors" in amadeus_response:
                _logger.error(f"Erreur dans la réponse API: {amadeus_response['errors']}")
                return {"error": amadeus_response["errors"][0]["detail"]}

            # Si pas d'offres mais une réponse valide
            if "data" not in amadeus_response or not amadeus_response["data"]:
                _logger.info("Aucune offre de vol trouvée dans la réponse API")
                return response

            # Log pour debug
            _logger.info(f"Nombre d'offres trouvées: {len(amadeus_response['data'])}")

            # Ajouter les paramètres de recherche à la réponse
            response["parameters"] = {
                "originAirport": original_params.get('originAirport'),
                "destinationAirport": original_params.get('destinationAirport'),
                "tripType": original_params.get('tripType'),
                "class": original_params.get('class')
            }

            # Parcourir les offres
            for offer in amadeus_response["data"]:
                try:
                    # Parcourir les itinéraires (aller/retour)
                    for i, itinerary in enumerate(offer["itineraries"]):
                        # Déterminer s'il s'agit d'un vol retour
                        is_return = (i > 0 and original_params.get('tripType') == 'RoundTrip')

                        flight_data = {
                            "price": offer["price"]["total"],
                            "currency": offer["price"]["currency"],
                            "refundable": offer.get("pricingOptions", {}).get("refundable", False),
                            "isReturn": is_return
                        }

                        # S'assurer que les segments existent
                        if not itinerary.get("segments") or len(itinerary["segments"]) == 0:
                            _logger.warning(f"Itinéraire sans segments: {itinerary}")
                            continue

                        # Segment courant
                        first_segment = itinerary["segments"][0]
                        last_segment = itinerary["segments"][-1]

                        # Informations de vol
                        carrier_code = first_segment.get("carrierCode", "")
                        flight_data.update({
                            "airlines": {
                                "full": self._get_airline_name(carrier_code)
                            },
                            "flightNumber": f"{carrier_code}{first_segment.get('number', '')}",
                            "departDateTime": {
                                "date": first_segment.get("departure", {}).get("at", "").split("T")[0],
                                "time": first_segment.get("departure", {}).get("at", "").split("T")[1].split("+")[
                                    0] if "T" in first_segment.get("departure", {}).get("at", "") else ""
                            },
                            "arrivalDateTime": {
                                "date": last_segment.get("arrival", {}).get("at", "").split("T")[0],
                                "time": last_segment.get("arrival", {}).get("at", "").split("T")[1].split("+")[
                                    0] if "T" in last_segment.get("arrival", {}).get("at", "") else ""
                            },
                            "duration": itinerary.get("duration", "").replace("PT", ""),
                            "cabin": self._get_cabin_class(first_segment.get("cabin", "ECONOMY")),
                            "baggageWeight": "Inclus",
                            "baggageUnit": "kg",
                            "originAirport": first_segment.get("departure", {}).get("iataCode", ""),
                            "destinationAirport": last_segment.get("arrival", {}).get("iataCode", ""),
                            "seatsRemaining": first_segment.get("numberOfStops", 0) + 1  # Estimation
                        })

                        response["response"]["flights"].append(flight_data)
                except KeyError as ke:
                    _logger.error(f"Clé manquante lors du traitement de l'offre: {ke}")
                    continue

            return response
        except Exception as e:
            _logger.error(f"Erreur lors de la transformation de la réponse: {str(e)}")
            return {"error": f"Erreur lors de la transformation de la réponse: {str(e)}"}

    def _get_airline_name(self, carrier_code):
        """Obtenir le nom complet de la compagnie aérienne à partir du code"""
        airlines_map = {
            "AF": "Air France",
            "KL": "KLM",
            "BA": "British Airways",
            "LH": "Lufthansa",
            "DL": "Delta Airlines",
            "AA": "American Airlines",
            "UA": "United Airlines",
            "TU":"Tunisair airlines",
            "UG":"Uganda Airlines",
            "BG":"Biman Bangladesh Airlines",
            # Ajouter d'autres compagnies selon vos besoins
        }
        return airlines_map.get(carrier_code, carrier_code)

    def _get_cabin_class(self, cabin_code):
        """Convertir le code de cabine en nom lisible"""
        cabin_map = {
            "ECONOMY": "Economy",
            "BUSINESS": "Business",
            "FIRST": "First",
            "PREMIUM_ECONOMY": "Premium Economy"
        }
        return cabin_map.get(cabin_code, "Economy")

    def action_search_flights(self):
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
            'tripType': self.trip_type
        }

        # Ajouter la date de retour si c'est un aller-retour
        if self.trip_type == 'RoundTrip' and self.return_date:
            params['return'] = self.return_date.strftime("%Y-%m-%d")

        _logger.info(f"Paramètres de recherche: {params}")

        try:
            results = flight_api.search_flights(params)

            # Log des résultats pour debug
            _logger.info(f"Type de résultats reçus: {type(results)}")

            # Vérification que results n'est pas None
            if not results:
                _logger.warning("Aucun résultat n'a été retourné par l'API.")
                raise UserError("Aucun résultat n'a été retourné par l'API.")

            # Traiter les erreurs explicites
            if isinstance(results, dict) and "error" in results:
                _logger.error(f"Erreur retournée par l'API: {results['error']}")
                raise UserError(f"Erreur API: {results['error']}")

            # S'assurer que la structure contient des résultats
            if not isinstance(results, dict) or not results.get('response'):
                _logger.error(f"Structure de réponse inattendue: {results}")
                results = {"response": {"flights": []}}

            flights = results.get('response', {}).get('flights', [])
            _logger.info(f"Nombre de vols trouvés: {len(flights)}")

            # Création des lignes de vol
            for flight in flights:
                # Extraction des données de base
                price = float(flight.get('price', 0))
                currency = flight.get('currency', 'EUR')
                is_return = flight.get('isReturn', False)

                # Informations de vol
                airline = flight.get('airlines', {}).get('full', 'Inconnu')
                flight_number = flight.get('flightNumber', '')

                # Dates
                try:
                    dep_date_str = f"{flight.get('departDateTime', {}).get('date', '')} {flight.get('departDateTime', {}).get('time', '')}"
                    arr_date_str = f"{flight.get('arrivalDateTime', {}).get('date', '')} {flight.get('arrivalDateTime', {}).get('time', '')}"

                    dep_date = fields.Datetime.to_datetime(dep_date_str.strip()) if dep_date_str.strip() else False
                    arr_date = fields.Datetime.to_datetime(arr_date_str.strip()) if arr_date_str.strip() else False

                    if not dep_date or not arr_date:
                        _logger.warning(f"Dates invalides pour le vol {flight_number}: {dep_date_str} - {arr_date_str}")
                        continue

                    # Création de la ligne de vol
                    self.env['flight.booking.line'].create({
                        'booking_id': self.id,
                        'airline': airline,
                        'flight_number': flight_number,
                        'departure_date': dep_date,
                        'arrival_date': arr_date,
                        'duration': flight.get('duration', ''),
                        'price': price,
                        'currency': currency,
                        'baggage': f"{flight.get('baggageWeight', '')} {flight.get('baggageUnit', '')}",
                        'travel_class': flight.get('cabin', 'Economy'),
                        'is_return': is_return
                    })
                except Exception as e:
                    _logger.error(f"Erreur lors de la création d'une ligne de vol: {str(e)}")
                    continue

            # Sauvegarde des résultats bruts
            self.flight_results = json.dumps(results)

            # Retourner l'action de rechargement
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        except UserError as ue:
            raise ue
        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Erreur lors de la recherche de vols: {error_msg}")
            raise UserError(f"Erreur lors de la recherche : {error_msg}")