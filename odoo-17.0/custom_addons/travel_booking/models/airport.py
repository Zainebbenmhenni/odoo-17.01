from odoo import models, fields, api

class Airport(models.Model):
    _name = 'airport'
    _description = 'Airport for Travel Booking'
    _rec_name = 'display_name'

    iata = fields.Char(string='IATA')
    name = fields.Char(string='Airport Name')
    city = fields.Char(string='City')
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    @api.depends( 'city', 'iata', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.city} {record.iata} {record.name}"

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.city} {record.iata} {record.name}"
            result.append((record.id, name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', '|',
                ('city', operator, name),
                ('iata', operator, name),
                ('name', operator, name)]
        return self._search(domain + args, limit=limit, order=order)