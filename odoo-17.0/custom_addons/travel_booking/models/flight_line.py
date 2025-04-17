from odoo import models, fields, api
from datetime import datetime, timedelta


class FlightLine(models.Model):
    _name = 'flight.booking.line'
    _description = 'Flight Booking Line'

    booking_id = fields.Many2one('flight.booking', string='Réservation', ondelete='cascade')
    airline = fields.Char(string='Compagnie')
    flight_number = fields.Char(string='Numéro de vol')
    departure_date = fields.Datetime(string='Date de départ')
    arrival_date = fields.Datetime(string='Date d\'arrivée')
    duration = fields.Char(string='Durée')
    price = fields.Float(string='Prix')
    currency = fields.Char(string='Devise', default='BDT')
    baggage = fields.Char(string='Bagages')
    recommendation_score = fields.Float(string='Score de recommandation', default=0.0)
    is_recommended = fields.Boolean(string='Recommandé', default=False)
    travel_class = fields.Selection([
        ('Economy', 'Economy'),
        ('Business', 'Affaires')
    ], string='Classe')
    is_return = fields.Boolean(string="Vol retour", default=False)