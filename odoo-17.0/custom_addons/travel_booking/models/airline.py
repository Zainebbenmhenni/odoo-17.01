from odoo import models, fields


class ResAirline(models.Model):
    _name = 'res.airline'
    _description = 'Airlines'

    name = fields.Char('Nom complet', required=True)
    code = fields.Char('Code IATA', size=2, required=True)
    active = fields.Boolean('Actif', default=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Le code IATA doit être unique!')
    ]