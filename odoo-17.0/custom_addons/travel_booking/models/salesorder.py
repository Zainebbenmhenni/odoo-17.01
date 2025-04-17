from odoo import models, fields, api
from datetime import datetime
import logging
from odoo.tools import format_date

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    booking_id = fields.Many2one('booking', string='Réservation associée')

    @api.model
    def _confirm_booking_after_payment(self, sale_order):
        """Méthode appelée après le paiement réussi"""
        if sale_order.booking_id:
            sale_order.booking_id.write({'state': 'confirmed'})
            sale_order.booking_id.action_confirm()
        return True
