from odoo import models, fields, api
import json
from datetime import datetime
import logging
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

class FlightBookingSegment(models.Model):
    _name = 'flight.booking.segment'
    _description = 'Flight Booking Segment for Multi-City'
    _order = 'sequence, id'

    booking_id = fields.Many2one('flight.booking', string='Réservation', ondelete='cascade')
    sequence = fields.Integer(string='Séquence', default=10)
    origin = fields.Char(string='Origine', required=True)
    destination = fields.Char(string='Destination', required=True)
    departure_date = fields.Date(string='Date de départ', required=True)