from odoo import models, fields, api


class BookingTicket(models.Model):
    _name = 'booking.ticket'
    _description = 'Ticket de réservation'
    _rec_name = 'ticket_number'

    ticket_number = fields.Char('Numéro de ticket', readonly=True, copy=False)
    booking_id = fields.Many2one('booking', string='Réservation', required=True, ondelete='cascade')

    # Ajouter un lien vers le contact plutôt qu'utiliser des champs char
    partner_id = fields.Many2one('res.partner', string='Passager', required=True)

    # Utiliser des champs related pour obtenir les informations du contact
    passenger_name = fields.Char(related='partner_id.name', string='Nom du passager', store=True, readonly=True)
    passport_number = fields.Char(related='partner_id.passport_number', string='Numéro de passeport', store=True,
                                  readonly=True)
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
        ('with_parent', 'avec parent'),
    ], string='Préférence de siège', default='window')

    meal_preference = fields.Selection([
        ('regular', 'Standard'),
        ('vegetarian', 'Végétarien'),
        ('halal', 'Halal'),
        ('kosher', 'Casher'),
        ('baby', 'Nourriture pour bébé')
    ], string='Préférence de repas', default='regular')

    # Méthode pour générer automatiquement le numéro de ticket à la création
    @api.model
    def create(self, vals):
        vals['ticket_number'] = self.env['ir.sequence'].next_by_code('booking.ticket.sequence') or 'TKN00001'
        return super(BookingTicket, self).create(vals)