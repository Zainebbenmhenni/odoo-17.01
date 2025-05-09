# Dans un nouveau fichier booking_ml.py
from odoo import models, fields, api
import numpy as np
import logging
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
import base64
import io
import pickle

_logger = logging.getLogger(__name__)


class BookingSalesPrediction(models.Model):
    _name = 'booking.sales.prediction'
    _description = 'Prédictions de ventes par compagnie aérienne'

    airline = fields.Char('Compagnie aérienne', required=True)
    period = fields.Char('Période de prédiction', required=True)
    predicted_sales = fields.Float('Ventes prédites', required=True)
    actual_sales = fields.Float('Ventes réelles', default=0.0)
    prediction_date = fields.Date('Date de prédiction', default=fields.Date.today)
    model_version = fields.Char('Version du modèle', default='1.0')
    confidence = fields.Float('Indice de confiance (%)', default=0.0)

    # Pour stocker le modèle ML
    ml_model = fields.Binary('Modèle ML sérialisé', attachment=True)

    @api.model
    def train_model(self):
        """Entraîner un modèle ML pour chaque compagnie aérienne"""
        try:
            # Récupérer les données des réservations
            bookings = self.env['booking'].search([
                ('state', '=', 'confirmed'),
                ('airline', '!=', False),
                ('payment_date', '!=', False),
                ('price', '>', 0)
            ])

            # Regrouper par compagnie aérienne
            airlines = {}
            for booking in bookings:
                airline = booking.airline
                if not airline in airlines:
                    airlines[airline] = []

                # Format: [year, month, day_of_week, price]
                payment_date = booking.payment_date or booking.create_date
                airlines[airline].append([
                    payment_date.year,
                    payment_date.month,
                    payment_date.weekday(),
                    booking.price
                ])

            # Pour chaque compagnie, entraîner un modèle
            for airline, data in airlines.items():
                if len(data) < 10:  # Besoin d'assez de données
                    _logger.info(f"Pas assez de données pour {airline}: {len(data)} entrées")
                    continue

                X = np.array([d[:-1] for d in data])  # Features
                y = np.array([d[-1] for d in data])  # Target (price)

                # Entraînement d'un modèle simple
                model = LinearRegression()
                model.fit(X, y)

                # Sérialiser le modèle
                model_bytes = io.BytesIO()
                pickle.dump(model, model_bytes)
                model_base64 = base64.b64encode(model_bytes.getvalue())

                # Calculer le score (confiance)
                score = model.score(X, y) * 100

                # Générer des prédictions pour les 3 prochains mois
                today = datetime.today()
                for i in range(1, 4):
                    next_month = today + timedelta(days=30 * i)
                    period = f"{next_month.strftime('%B %Y')}"

                    # Prédire pour différents jours du mois et faire une moyenne
                    predictions = []
                    for day in range(1, 29):
                        # [year, month, day_of_week]
                        next_date = next_month.replace(day=day)
                        features = np.array([[
                            next_date.year,
                            next_date.month,
                            next_date.weekday()
                        ]])
                        pred = model.predict(features)[0]
                        predictions.append(pred)

                    avg_prediction = sum(predictions) / len(predictions)

                    # Enregistrer la prédiction
                    self.create({
                        'airline': airline,
                        'period': period,
                        'predicted_sales': avg_prediction,
                        'prediction_date': fields.Date.today(),
                        'ml_model': model_base64,
                        'confidence': score
                    })

            return True
        except Exception as e:
            _logger.error(f"Erreur lors de l'entraînement du modèle: {str(e)}")
            return False

    @api.model
    def get_predictions_data(self):
        """Récupérer les données de prédiction pour le dashboard"""
        predictions = self.search_read(
            [('prediction_date', '>=', fields.Date.today() - timedelta(days=7))],
            ['airline', 'period', 'predicted_sales', 'confidence']
        )

        # Organiser par compagnie aérienne
        result = {}
        for pred in predictions:
            airline = pred['airline']
            if airline not in result:
                result[airline] = {
                    'name': airline,
                    'predictions': []
                }

            result[airline]['predictions'].append({
                'period': pred['period'],
                'value': round(pred['predicted_sales'], 2),
                'confidence': round(pred['confidence'], 1)
            })

        return list(result.values())