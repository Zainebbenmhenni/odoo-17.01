from odoo import models, fields, api
import json
import logging
from datetime import datetime
import numpy as np
from sklearn.preprocessing import OneHotEncoder
import pickle
import base64

_logger = logging.getLogger(__name__)


class UserFlightPreference(models.Model):
    _name = 'user.flight.preference'
    _description = 'User Flight Preferences'

    partner_id = fields.Many2one('res.partner', string='Client', required=True, index=True)

    # Préférences explicites
    preferred_airlines = fields.Many2many('res.airline', string='Compagnies préférées')
    preferred_travel_class = fields.Selection([
        ('Economy', 'Economy'),
        ('Business', 'Affaires')
    ], string='Classe préférée')
    preferred_departure_time = fields.Selection([
        ('morning', 'Matin (5h-12h)'),
        ('afternoon', 'Après-midi (12h-18h)'),
        ('evening', 'Soir (18h-22h)'),
        ('night', 'Nuit (22h-5h)')
    ], string='Heure de départ préférée')
    price_sensitivity = fields.Selection([
        ('low', 'Faible - Qualité privilégiée'),
        ('medium', 'Moyenne - Équilibre prix/qualité'),
        ('high', 'Haute - Prix minimum privilégié')
    ], string='Sensibilité au prix', default='medium')

    # Métriques calculées automatiquement
    airline_history = fields.Binary('Historique des compagnies (ML)', attachment=True)
    time_history = fields.Binary('Historique des horaires (ML)', attachment=True)
    price_history = fields.Binary('Historique des prix (ML)', attachment=True)
    preference_model = fields.Binary('Modèle de préférence (ML)', attachment=True)
    last_update = fields.Datetime('Dernière mise à jour')

    _sql_constraints = [
        ('partner_unique', 'UNIQUE(partner_id)', 'Un client ne peut avoir qu\'un seul profil de préférences!')
    ]

    @api.model
    def create(self, vals):
        # Calculer les préférences implicites lors de la création
        rec = super(UserFlightPreference, self).create(vals)
        rec.compute_implicit_preferences()
        return rec

    def compute_implicit_preferences(self):
        """Calcule les préférences implicites basées sur l'historique des réservations"""
        for record in self:
            # Récupérer l'historique des réservations du client
            bookings = self.env['booking'].search([
                ('partner_id', '=', record.partner_id.id),
                ('state', '=', 'confirmed')
            ])

            if not bookings:
                return

            # Extraire les données d'historique
            airlines = []
            departure_times = []
            prices = []

            for booking in bookings:
                airlines.append(booking.airline)

                # Convertir l'heure de départ en catégorie
                if booking.departure_time:
                    hour = int(booking.departure_time.split(':')[0])
                    if 5 <= hour < 12:
                        departure_times.append('morning')
                    elif 12 <= hour < 18:
                        departure_times.append('afternoon')
                    elif 18 <= hour < 22:
                        departure_times.append('evening')
                    else:
                        departure_times.append('night')

                prices.append(booking.price)

            # Stocker les données pour le ML
            record.airline_history = base64.b64encode(pickle.dumps(airlines))
            record.time_history = base64.b64encode(pickle.dumps(departure_times))
            record.price_history = base64.b64encode(pickle.dumps(prices))
            record.last_update = fields.Datetime.now()

            # Créer un modèle simple basé sur les fréquences
            try:
                # Pour les compagnies aériennes
                airline_counts = {}
                for airline in airlines:
                    airline_counts[airline] = airline_counts.get(airline, 0) + 1

                # Pour les horaires
                time_counts = {}
                for time in departure_times:
                    time_counts[time] = time_counts.get(time, 0) + 1

                # Pour les prix
                avg_price = sum(prices) / len(prices) if prices else 0
                price_range = max(prices) - min(prices) if len(prices) > 1 else 0

                # Créer un modèle de préférence simple
                preference_model = {
                    'airline_counts': airline_counts,
                    'time_counts': time_counts,
                    'avg_price': avg_price,
                    'price_range': price_range
                }

                record.preference_model = base64.b64encode(pickle.dumps(preference_model))
            except Exception as e:
                _logger.error(f"Erreur lors du calcul des préférences: {str(e)}")