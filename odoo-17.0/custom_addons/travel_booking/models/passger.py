from odoo import api, fields, models


class BookingPassenger(models.Model):
    _name = 'booking.passenger'
    _description = 'Passager de réservation'

    booking_id = fields.Many2one('booking', string='Réservation', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Contact', required=True)

    # Champs related pour récupérer les informations du contact
    name = fields.Char(related='partner_id.name', string='Nom complet', store=True, readonly=True)
    passport = fields.Char(related='partner_id.passport_number', string='Numéro de passeport', store=True,
                           readonly=True)
    phone = fields.Char(related='partner_id.phone', string='Téléphone', store=True, readonly=True)
    birth_date = fields.Date(related='partner_id.birth_date', string='Date de naissance', store=True, readonly=True)
    gender = fields.Selection(related='partner_id.gender', string='Genre', store=True, readonly=True)

    passenger_type = fields.Selection([
        ('adult', 'Adulte'),
        ('child', 'Enfant'),
        ('infant', 'Bébé')
    ], string='Type de passager', required=True)

    seat_preference = fields.Selection([
        ('window', 'Hublot'),
        ('aisle', 'Couloir'),
        ('middle', 'Milieu'),
        ('with_parent', 'Avec parent'),
        ('bassinet', 'Berceau')
    ], string='Préférence de siège')

    meal_preference = fields.Selection([
        ('regular', 'Standard'),
        ('vegetarian', 'Végétarien'),
        ('halal', 'Halal'),
        ('kosher', 'Casher'),
        ('kids', 'Menu enfant'),
        ('baby', 'Repas bébé'),
    ], string='Préférence de repas')