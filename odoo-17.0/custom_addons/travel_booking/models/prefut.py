from odoo import models, api
import json
import io
import base64
import pickle
import matplotlib.pyplot as plt
import numpy as np


class UserPreferenceReport(models.AbstractModel):
    _name = 'report.travel_booking.user_preference_report'
    _description = 'Rapport sur les préférences de vol'

    @api.model
    def _get_report_values(self, docids, data=None):
        preferences = self.env['user.flight.preference'].browse(docids)

        result = []
        for pref in preferences:
            preference_data = {
                'partner': pref.partner_id.name,
                'charts': {}
            }

            # Générer les graphiques si des données sont présentes
            if pref.preference_model:
                try:
                    model = pickle.loads(base64.b64decode(pref.preference_model))

                    # Graphique pour les compagnies aériennes
                    if model.get('airline_counts'):
                        airlines = list(model['airline_counts'].keys())
                        counts = list(model['airline_counts'].values())

                        plt.figure(figsize=(10, 6))
                        plt.bar(airlines, counts)
                        plt.title(f'Compagnies aériennes préférées de {pref.partner_id.name}')
                        plt.xlabel('Compagnie')
                        plt.ylabel('Nombre de vols')
                        plt.xticks(rotation=45)

                        buf = io.BytesIO()
                        plt.savefig(buf, format='png')
                        buf.seek(0)

                        preference_data['charts']['airlines'] = base64.b64encode(buf.read()).decode('utf-8')
                        plt.close()

                    # Graphique pour les heures de départ
                    if model.get('time_counts'):
                        times = list(model['time_counts'].keys())
                        counts = list(model['time_counts'].values())

                        plt.figure(figsize=(10, 6))
                        plt.bar(times, counts)
                        plt.title(f'Heures de départ préférées de {pref.partner_id.name}')
                        plt.xlabel('Période de la journée')
                        plt.ylabel('Nombre de vols')

                        buf = io.BytesIO()
                        plt.savefig(buf, format='png')
                        buf.seek(0)

                        preference_data['charts']['times'] = base64.b64encode(buf.read()).decode('utf-8')
                        plt.close()

                except Exception as e:
                    preference_data['error'] = str(e)

            result.append(preference_data)

        return {
            'docs': preferences,
            'data': result
        }