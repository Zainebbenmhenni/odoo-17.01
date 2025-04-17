from odoo import models, api


class PreferenceUpdateCron(models.Model):
    _name = 'preference.update.cron'
    _description = 'Cron pour mettre à jour les préférences utilisateur'

    @api.model
    def update_all_preferences(self):
        """Met à jour les préférences de tous les utilisateurs"""
        preferences = self.env['user.flight.preference'].search([])
        for pref in preferences:
            pref._compute_implicit_preferences()

        return True