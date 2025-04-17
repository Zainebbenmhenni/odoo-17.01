from datetime import datetime, timedelta

import logging
import json
import stripe

from odoo import http, fields,api
from odoo.http import request

_logger = logging.getLogger(__name__)


class TravelController(http.Controller):
    @http.route(['/traveling', '/travel'], type='http', auth="public", website=True)
    def travel_search(self, **kwargs):
        return request.render('travel_booking.website_travel_search')

    @http.route(['/travel/booking'], type='http', auth="public", website=True)
    def flight_booking_form(self, **post):
        adult_count = int(post.get('adult_count', 1))
        child_count = int(post.get('child_count', 0))
        infant_count = int(post.get('infant_count', 0))

        # Calculer le nombre total de passagers
        total_passengers = adult_count + child_count + infant_count
        _logger.info("Valeurs de passagers reçues: adultes=%s, enfants=%s, bébés=%s, total=%s",
                     adult_count, child_count, infant_count, total_passengers)

        # Vérifier si l'utilisateur est connecté
        is_logged_in = request.env.user.id != request.env.ref('base.public_user').id

        # Préparation des valeurs de base pour tous les cas
        values = {
            'flight_number': post.get('flight_number'),
            'departure_date': post.get('departure_date'),
            'departure_time': post.get('departure_time'),
            'arrival_date': post.get('arrival_date'),
            'arrival_time': post.get('arrival_time'),
            'airline': post.get('airline'),
            'price': post.get('price'),
            'baggage': post.get('baggage'),
            'currency': post.get('currency', 'EUR'),
            'adult_count': adult_count,
            'child_count': child_count,
            'infant_count': infant_count,
            'total_passengers': total_passengers,
            'is_logged_in': is_logged_in
        }

        if is_logged_in:
            # L'utilisateur est connecté, ajouter ses informations
            values['partner'] = request.env.user.partner_id
            return request.render('travel_booking.flight_booking_form', values)
        else:
            # L'utilisateur n'est pas connecté, stocker les données de vol dans la session
            request.session['booking_data'] = values.copy()
            # Render le template avec is_logged_in = False
            return request.render('travel_booking.flight_booking_form', values)

    @http.route(['/travel/booking/confirm'], type='http', auth="public", website=True)
    def booking_confirm(self, **post):
        try:
            adult_count = int(post.get('adult_count', 1) or 1)
            child_count = int(post.get('child_count', 0) or 0)
            infant_count = int(post.get('infant_count', 0) or 0)
            _logger.info(
                f"Nombre de passagers reçu: adultes={adult_count}, enfants={child_count}, bébés={infant_count}")

            # Créer l'enregistrement de réservation principale (contact principal)
            booking_values = {
                'partner_id': request.env.user.partner_id.id,
                'name': post.get('adult_name_1', ''),
                'email': post.get('email', ''),
                'phone': post.get('phone', ''),
                'passport': post.get('adult_passport_1', ''),
                'birth_date': post.get('adult_birth_date_1', ''),
                'gender': post.get('adult_gender_1', ''),
                'flight_number': post.get('flight_number', ''),
                'departure_date': post.get('departure_date', ''),
                'departure_time': post.get('departure_time', ''),
                'arrival_date': post.get('arrival_date', ''),
                'arrival_time': post.get('arrival_time', ''),
                'airline': post.get('airline', ''),
                'price': float(post.get('price', 0) or 0),
                'currency': post.get('currency', ''),
                'seat_preference': post.get('adult_seat_1', ''),
                'meal_preference': post.get('adult_meal_1', ''),
                'state': 'en attente de paiement',
                'adult_count': adult_count,
                'child_count': child_count,
                'infant_count': infant_count,
            }

            # Création de la réservation principale
            booking = request.env['booking'].sudo().create(booking_values)

            # Création des passagers additionnels (autres adultes)
            passenger_model = request.env['booking.passenger'].sudo()
            partner_model = request.env['res.partner'].sudo()

            # Traitement des autres adultes (à partir de 2)
            if adult_count > 1:
                for i in range(2, adult_count + 1):
                    # Créer un partenaire pour cet adulte
                    partner_vals = {
                        'name': post.get(f'adult_name_{i}', ''),
                        'phone': post.get(f'adult_phone_{i}', ''),
                        'passport_number': post.get(f'adult_passport_{i}', ''),
                        'birth_date': post.get(f'adult_birth_date_{i}', ''),
                        'gender': post.get(f'adult_gender_{i}', ''),
                        'type': 'contact',
                    }

                    partner = partner_model.create(partner_vals)

                    adult_values = {
                        'booking_id': booking.id,
                        'partner_id': partner.id,
                        'passenger_type': 'adult',
                        'seat_preference': post.get(f'adult_seat_{i}', ''),
                        'meal_preference': post.get(f'adult_meal_{i}', ''),
                    }
                    passenger_model.create(adult_values)

            # Traitement des enfants
            if child_count > 0:
                for i in range(1, child_count + 1):
                    # Créer un partenaire pour cet enfant
                    partner_vals = {
                        'name': post.get(f'child_name_{i}', ''),
                        'passport_number': post.get(f'child_passport_{i}', ''),
                        'birth_date': post.get(f'child_birth_date_{i}', ''),
                        'gender': post.get(f'child_gender_{i}', ''),
                        'type': 'contact',
                    }

                    partner = partner_model.create(partner_vals)

                    child_values = {
                        'booking_id': booking.id,
                        'partner_id': partner.id,
                        'passenger_type': 'child',
                        'seat_preference': post.get(f'child_seat_{i}', ''),
                        'meal_preference': post.get(f'child_meal_{i}', ''),
                    }
                    passenger_model.create(child_values)

            # Traitement des bébés
            if infant_count > 0:
                for i in range(1, infant_count + 1):
                    # Créer un partenaire pour ce bébé
                    partner_vals = {
                        'name': post.get(f'infant_name_{i}', ''),
                        'passport_number': post.get(f'infant_passport_{i}', ''),
                        'birth_date': post.get(f'infant_birth_date_{i}', ''),
                        'gender': post.get(f'infant_gender_{i}', ''),
                        'type': 'contact',
                    }

                    partner = partner_model.create(partner_vals)

                    infant_values = {
                        'booking_id': booking.id,
                        'partner_id': partner.id,
                        'passenger_type': 'infant',
                        'seat_preference': post.get(f'infant_seat_{i}', ''),
                        'meal_preference': post.get(f'infant_meal_{i}', ''),
                    }
                    passenger_model.create(infant_values)

            # Création d'ordre pour cette nouvelle réservation
            order = request.website.sale_get_order(force_create=1)
            product = request.env.ref('travel_booking.product_flight')  # Référence à votre produit "billet d'avion"

            total_passengers = adult_count + child_count + infant_count

            order_line_values = {
                'product_id': product.id,
                'name': f"Vol {post.get('flight_number')} - {post.get('departure_date')} ({total_passengers} passagers)",
                'product_uom_qty': 1,
                'price_unit': float(post.get('price', 0)),
            }

            order.write({
                'order_line': [(0, 0, order_line_values)],
                'booking_id': booking.id,  # Lier la commande à la réservation
            })

            # Appeler la méthode d'envoi d'email de confirmation
            booking.action_confirm()

            # Stocker l'ID de réservation dans la session
            request.session['booking_id'] = booking.id

            return request.redirect(f'/travel/payment?booking_id={booking.id}')

        except Exception as e:
            _logger.error(f"Erreur lors de la création de la réservation: {str(e)}")
            return request.render('travel_booking.travel_error', {
                'error': str(e),
                'message': 'Une erreur est survenue lors de la création de la réservation.'
            })

    @http.route(['/travel/submit'], type='http', auth="public", website=True, csrf=True, methods=['POST'])
    def travel_submit(self, **post):
        if post:
            try:
                adult_count = int(post.get('adult_count', 1))
                child_count = int(post.get('child_count', 0))
                infant_count = int(post.get('infant_count', 0))

                # recherche de flight pour le booking
                booking_vals = {
                    'origin_airport': post.get('departure_id'),
                    'destination_airport': post.get('destination_id'),
                    'origin': post.get('departure_id'),
                    'destination': post.get('destination_id'),
                    'departure_date': post.get('travel_date'),
                    'travel_class': post.get('travel_class'),
                    'adult_count': adult_count,
                    'child_count': child_count,
                    'infant_count': infant_count,
                    'trip_type': post.get('trip_type', 'OneWay')
                }

                # Ajouter la date de retour si c'est un aller-retour
                if post.get('trip_type') == 'RoundTrip' and post.get('return_date'):
                    booking_vals['return_date'] = post.get('return_date')

                booking = request.env['flight.booking'].sudo().create(booking_vals)
                booking.action_search_flights()

                # Debug print
                _logger.info('Flight Results: %s', booking.flight_results)

                values = {
                    'flights': json.loads(booking.flight_results) if booking.flight_results else None,
                    'search_params': post,
                    'booking': booking
                }
                return request.render('travel_booking.flight_search_results', values)
            except Exception as e:
                _logger.error("Error in travel_submit: %s", str(e))
                values = {
                    'error': str(e),
                    'message': 'Une erreur est survenue lors de la recherche des vols.'
                }
                return request.render('travel_booking.travel_error', values)
        return request.redirect('/')
    @http.route(['/travel/payment'], type='http', auth="public", website=True)
    def payment_options(self, **post):
        booking_id = post.get('booking_id')

        # Si non présent dans post, vérifier s'il est dans la commande active
        if not booking_id:
            order = request.website.sale_get_order()
            if order and hasattr(order, 'booking_id') and order.booking_id:
                booking_id = order.booking_id.id

        # Si toujours pas de booking_id, vérifier s'il y en a un dans la session
        if not booking_id and request.session.get('booking_id'):
            booking_id = request.session.get('booking_id')

        if not booking_id:
            # Si aucun ID n'est trouvé
            _logger.error("Aucun booking_id trouvé pour la page de paiement")
            return request.redirect('/')

        try:
            # Récupérer les informations de la réservation
            booking = request.env['booking'].sudo().browse(int(booking_id))
            if not booking.exists():
                return request.render('travel_booking.travel_error', {
                    'error': 'Réservation introuvable',
                    'message': 'La réservation demandée est introuvable.'
                })

            # Préparer les valeurs pour le template
            values = {
                'booking': booking,
                'currency': 'eur',
            }

            return request.render('travel_booking.payment_options_template', values)

        except Exception as e:
            _logger.error(f"Erreur dans payment_options: {str(e)}")
            return request.render('travel_booking.travel_error', {
                'error': str(e),
                'message': 'Une erreur est survenue lors du chargement des options de paiement.'
            })

    @http.route(['/travel/payment/process'], type='http', auth="public", website=True, csrf=True, methods=['POST'])
    def process_payment(self, **post):
        stripe.api_key = "sk_test_51R0hP2R3N0dhVd1wtDbfc8EUF97ZLOdRLoVulmiVDlLxSpFbHdU84AqrpsW3imbiW8VlNSfaMbfM6BBC2Y3GksXB00KJpyK5eV"
        booking_id = post.get('booking_id')
        token = post.get('stripeToken')

        _logger.info(f"Process payment - booking_id: {booking_id}, token present: {token is not None}")

        if not booking_id or not token:
            _logger.error(f"Données manquantes - booking_id: {booking_id}, token présent: {token is not None}")
            return request.render('travel_booking.travel_error', {
                'error': 'Données manquantes',
                'message': 'Des informations nécessaires sont manquantes pour traiter votre paiement.'
            })

        try:
            booking_id = int(booking_id)
            booking = request.env['booking'].sudo().browse(booking_id)

            if not booking.exists():
                _logger.error(f"Réservation {booking_id} introuvable")
                return request.render('travel_booking.travel_error', {
                    'error': 'Réservation introuvable',
                    'message': 'La réservation demandée est introuvable.'
                })

            # Processus de paiement Stripe
            _logger.info(f"Traitement paiement Stripe pour booking {booking_id}")

            try:
                charge = stripe.Charge.create(
                    amount=int(booking.price * 100),  # Convertir en centimes
                    currency='eur',
                    description=f"Paiement pour la réservation {booking.booking_reference}",
                    source=token,
                )

                booking.write({
                    'state': 'confirmed',
                    'payment_method': 'stripe',
                    'payment_date': fields.Datetime.now()
                })

                booking.action_confirm1()

                return request.render('travel_booking.payment_success', {
                    'booking': booking,
                    'message': 'Votre paiement a été traité avec succès. Un email de confirmation vous a été envoyé.'
                })

            except stripe.error.CardError as e:
                _logger.error(f"Erreur de carte: {str(e)}")
                return request.render('travel_booking.travel_error', {
                    'error': str(e),
                    'message': 'Une erreur est survenue lors du traitement de votre paiement.'
                })

        except Exception as e:
            _logger.error(f"Erreur lors du traitement du paiement: {str(e)}", exc_info=True)
            return request.render('travel_booking.travel_error', {
                'error': str(e),
                'message': 'Une erreur est survenue lors du traitement de votre paiement.'
            })

    @http.route(['/travel/signup'], type='http', auth="public", website=True)
    def travel_signup(self, **kw):
        qcontext = {
            'error': {},
            'error_message': []
        }
        return request.render('travel_booking.travel_signup_template', qcontext)

    # @http.route(['/travel/do_signin'], type='http', auth="public", website=True, csrf=True)
    # def travel_do_signin(self, **post):
    #     qcontext = {
    #         'error': {},
    #         'error_message': []
    #     }
    #
    #     # Check required fields
    #     if not post.get('login') or not post.get('password'):
    #         qcontext['error_message'].append("Veuillez remplir votre email et mot de passe.")
    #         return request.render('travel_booking.travel_signin_template', qcontext)
    #
    #     try:
    #         # Try to authenticate
    #         db, login, password = request.cr.dbname, post.get('login'), post.get('password')
    #         uid = request.session.authenticate(db, login, password)
    #         if not uid:
    #             qcontext['error_message'].append("Email ou mot de passe incorrect.")
    #             return request.render('travel_booking.travel_signin_template', qcontext)
    #
    #         # Vérifier s'il y a des données de réservation en attente
    #         if request.session.get('booking_data'):
    #             # Rediriger vers le formulaire de réservation avec les données sauvegardées
    #             return request.redirect('/travel/booking/continue')
    #
    #         # Vérifier s'il y a un paramètre de redirection dans l'URL
    #         redirect = post.get('redirect') or request.params.get('redirect')
    #         if redirect:
    #             return request.redirect(f'/travel/{redirect}')
    #
    #         # Sinon, rediriger vers la page principale travel
    #         return request.redirect('/travel')
    #
    #     except Exception as e:
    #         _logger.error("Error during signin: %s", str(e))
    #         qcontext['error_message'] = [str(e)]
    #         return request.render('travel_booking.travel_signin_template', qcontext)

    @http.route(['/travel/booking/continue'], type='http', auth="user", website=True)
    def continue_booking(self, **post):
        # Récupérer les données de réservation stockées dans la session
        booking_data = request.session.get('booking_data', {})
        if not booking_data:
            return request.redirect('/travel')

        # Préparer les valeurs pour le template
        values = booking_data.copy()
        values['partner'] = request.env.user.partner_id
        values['is_logged_in'] = True

        # Supprimer les données de la session car elles ne sont plus nécessaires
        request.session.pop('booking_data', None)

        return request.render('travel_booking.flight_booking_form', values)

    @http.route(['/travel/signin'], type='http', auth="public", website=True)
    def travel_signin(self, **kw):
        qcontext = {
            'error': {},
            'error_message': []
        }
        return request.render('travel_booking.travel_signin_template', qcontext)

    # @http.route(['/travel/do_signin'], type='http', auth="public", website=True, csrf=True)
    # def travel_do_signin(self, **post):
    #     qcontext = {
    #         'error': {},
    #         'error_message': []
    #     }
    #
    #     # Check required fields
    #     if not post.get('login') or not post.get('password'):
    #         qcontext['error_message'].append("Veuillez remplir votre email et mot de passe.")
    #         return request.render('travel_booking.travel_signin_template', qcontext)
    #
    #     try:
    #         # Try to authenticate
    #         db, login, password = request.cr.dbname, post.get('login'), post.get('password')
    #         uid = request.session.authenticate(db, login, password)
    #         if not uid:
    #             qcontext['error_message'].append("Email ou mot de passe incorrect.")
    #             return request.render('travel_booking.travel_signin_template', qcontext)
    #
    #         # Redirect to dashboard or home
    #         return request.redirect('/travel')
    #
    #     except Exception as e:
    #         _logger.error("Error during signin: %s", str(e))
    #         qcontext['error_message'] = [str(e)]
    #         return request.render('travel_booking.travel_signin_template', qcontext)

    @http.route(['/my/travel'], type='http', auth="user", website=True)
    def my_travel_dashboard(self, **kw):
        partner = request.env.user.partner_id

        # Ajouter des logs pour le débogage
        _logger.info(f"Dashboard accessed by partner ID: {partner.id}, name: {partner.name}")

        # Récupérer toutes les réservations où ce partenaire est le passager principal
        bookings = request.env['booking'].sudo().search([
            ('partner_id', '=', partner.id)
        ])

        _logger.info(f"Found {len(bookings)} bookings as main passenger")

        # Récupérer également les réservations où ce partenaire est un passager additionnel
        passenger_bookings = request.env['booking.passenger'].sudo().search([
            ('partner_id', '=', partner.id)
        ]).mapped('booking_id')

        _logger.info(f"Found {len(passenger_bookings)} bookings as additional passenger")

        # Combiner toutes les réservations sans doublons
        all_bookings = bookings | passenger_bookings

        _logger.info(f"Total unique bookings: {len(all_bookings)}")

        # Récupérer tous les tickets associés à ce partenaire
        tickets = request.env['booking.ticket'].sudo().search([
            ('partner_id', '=', partner.id)
        ])

        _logger.info(f"Found {len(tickets)} tickets")

        # Si aucune réservation n'est trouvée, vérifier dans la base de données si des réservations existent
        if not all_bookings:
            total_bookings = request.env['booking'].sudo().search_count([])
            _logger.info(f"Total bookings in database: {total_bookings}")

            # Vérifier si des réservations existent pour d'autres partenaires
            other_bookings = request.env['booking'].sudo().search([], limit=5)
            for booking in other_bookings:
                _logger.info(
                    f"Sample booking: ID={booking.id}, partner_id={booking.partner_id.id}, name={booking.name}")

        return request.render('travel_booking.my_travel_dashboard', {
            'bookings': all_bookings,
            'tickets': tickets,
            'partner': partner
        })

    @http.route(['/my/travel/booking/<int:booking_id>'], type='http', auth="user", website=True)
    def my_travel_booking_details(self, booking_id, **kw):
        partner = request.env.user.partner_id

        booking = request.env['booking'].sudo().browse(int(booking_id))

        # Security check - only show bookings that belong to this user
        is_passenger = request.env['booking.passenger'].sudo().search_count([
            ('booking_id', '=', booking.id),
            ('partner_id', '=', partner.id)
        ])

        if booking.partner_id.id != partner.id and not is_passenger:
            return request.redirect('/travel')

        return request.render('travel_booking.my_travel_booking_details', {
            'booking': booking
        })

    @http.route(['/my/travel/tickets/<int:ticket_id>'], type='http', auth="user", website=True)
    def my_travel_ticket_details(self, ticket_id, **kw):
        partner = request.env.user.partner_id

        ticket = request.env['booking.ticket'].sudo().browse(int(ticket_id))

        # Security check - only show tickets that belong to this user
        if ticket.partner_id.id != partner.id:
            return request.redirect('/travel')

        return request.render('travel_booking.my_travel_ticket_details', {
            'ticket': ticket
        })

    @http.route(['/my/profile'], type='http', auth="user", website=True)
    def my_travel_profile(self, **kw):
        partner = request.env.user.partner_id
        return request.render('travel_booking.my_travel_profile', {
            'partner': partner
        })

    @http.route(['/my/profile/update'], type='http', auth="user", website=True, csrf=True)
    def my_travel_profile_update(self, **post):
        partner = request.env.user.partner_id

        # Update partner info
        partner_vals = {
            'name': post.get('name'),
            'phone': post.get('phone'),
            'passport_number': post.get('passport_number'),
            'birth_date': post.get('birth_date'),
            'gender': post.get('gender')
        }

        partner.sudo().write(partner_vals)

        return request.redirect('/my/profile?updated=1')

    @http.route(['/'], type='http', auth="public", website=True)
    def welcome_page(self, **kwargs):
        return request.render('travel_booking.welcome_page')

    @http.route(['/travel/signin'], type='http', auth="public", website=True)
    def travel_signin(self, **kw):
        qcontext = {
            'error': {},
            'error_message': [],
            'redirect': kw.get('redirect', '')  # Capture le paramètre de redirection
        }
        return request.render('travel_booking.travel_signin_template', qcontext)

    @http.route(['/travel/do_signin'], type='http', auth="public", website=True, csrf=True)
    def travel_do_signin(self, **post):
        qcontext = {
            'error': {},
            'error_message': [],
            'redirect': post.get('redirect', '')  # Conserver le paramètre lors des erreurs
        }

        # Check required fields
        if not post.get('login') or not post.get('password'):
            qcontext['error_message'].append("Veuillez remplir votre email et mot de passe.")
            return request.render('travel_booking.travel_signin_template', qcontext)

        try:
            # Try to authenticate
            db, login, password = request.cr.dbname, post.get('login'), post.get('password')
            uid = request.session.authenticate(db, login, password)
            if not uid:
                qcontext['error_message'].append("Email ou mot de passe incorrect.")
                return request.render('travel_booking.travel_signin_template', qcontext)

            # Vérifier s'il y a des données de réservation en attente dans la session
            if request.session.get('booking_data'):
                # Rediriger vers la continuation de la réservation
                return request.redirect('/travel/booking/continue')

            # Vérifier s'il y a un paramètre de redirection
            redirect = post.get('redirect')
            if redirect and redirect == 'booking':
                return request.redirect('/travel/booking')

            # Sinon, rediriger vers la page principale travel
            return request.redirect('/travel')

        except Exception as e:
            _logger.error("Error during signin: %s", str(e))
            qcontext['error_message'] = [str(e)]
            return request.render('travel_booking.travel_signin_template', qcontext)

    @http.route(['/travel/do_signup'], type='http', auth="public", website=True, csrf=True)
    def travel_do_signup(self, **post):
        qcontext = {
            'error': {},
            'error_message': []
        }

        # Check required fields
        required_fields = ['name', 'login', 'password', 'confirm_password', 'passport_number', 'birth_date', 'gender']
        for field in required_fields:
            if not post.get(field):
                qcontext['error'][field] = True
                qcontext['error_message'].append(f"Le champ {field} est obligatoire.")

        # Check if passwords match
        if post.get('password') != post.get('confirm_password'):
            qcontext['error']['confirm_password'] = True
            qcontext['error_message'].append("Les mots de passe ne correspondent pas.")

        # If errors found, return form with errors
        if qcontext['error_message']:
            # Copy form values to context
            for field in ['name', 'login', 'phone', 'passport_number', 'birth_date', 'gender']:
                qcontext[field] = post.get(field, '')
            return request.render('travel_booking.travel_signup_template', qcontext)

        try:
            # Check if login (email) already exists
            if request.env['res.users'].sudo().search([('login', '=', post.get('login'))]):
                qcontext['error']['login'] = True
                qcontext['error_message'].append("Cet email est déjà utilisé.")
                for field in ['name', 'login', 'phone', 'passport_number', 'birth_date', 'gender']:
                    qcontext[field] = post.get(field, '')
                return request.render('travel_booking.travel_signup_template', qcontext)

            # Create the new user
            values = {
                'name': post.get('name'),
                'login': post.get('login'),
                'password': post.get('password'),
                'phone': post.get('phone'),
                'passport_number': post.get('passport_number'),
                'birth_date': post.get('birth_date'),
                'gender': post.get('gender'),
            }

            # Create user and partner
            user_sudo = request.env['res.users'].sudo().with_context(no_reset_password=True).create(values)

            # Automatic sign in
            request.env.cr.commit()  # As authenticate will use its own cursor we need to commit the current transaction
            request.session.authenticate(request.env.cr.dbname, post.get('login'), post.get('password'))

            # Redirect to success page
            return request.render('travel_booking.signup_success', {
                'login': post.get('login')
            })

        except Exception as e:
            _logger.error("Error during signup: %s", str(e))
            qcontext['error_message'] = [str(e)]
            for field in ['name', 'login', 'phone', 'passport_number', 'birth_date', 'gender']:
                qcontext[field] = post.get(field, '')
            return request.render('travel_booking.travel_signup_template', qcontext)

    @http.route(['/travel/logout'], type='http', auth="public", website=True)
    def travel_logout(self, **kw):
        # Déconnexion de l'utilisateur
        request.session.logout(keep_db=True)
        # Redirection vers la page d'accueil
        return request.redirect('/')