from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Champs spécifiques pour les voyageurs
    passport_number = fields.Char('Numéro de passeport')
    birth_date = fields.Date('Date de naissance')
    gender = fields.Selection([
        ('M', 'Masculin'),
        ('F', 'Féminin')
    ], string='Genre')

    # Relations inverses pour faciliter la navigation
    booking_passenger_ids = fields.One2many('booking.passenger', 'partner_id', string='Participations aux voyages')
    booking_ticket_ids = fields.One2many('booking.ticket', 'partner_id', string='Tickets de voyage')