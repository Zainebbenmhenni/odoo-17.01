import base64
from odoo import models, fields, api
from datetime import datetime, timedelta
import logging
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class TravelBooking(models.Model):
    _name = 'booking'
    _description = 'Réservation de vol'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'booking_reference'

    # Remplacer le champ name par un lien vers le contact principal
    partner_id = fields.Many2one('res.partner', string='Passager principal', required=True, tracking=True)

    # Remplacer les champs simples par des related fields
    name = fields.Char(related='partner_id.name', string='Nom du passager', store=True, readonly=False, tracking=True)
    email = fields.Char(related='partner_id.email', string='Email', store=True, readonly=False, tracking=True)
    phone = fields.Char(related='partner_id.phone', string='Téléphone', store=True, readonly=False, tracking=True)
    passport = fields.Char(related='partner_id.passport_number', string='Numéro de passeport', store=True,
                           readonly=False, tracking=True)
    birth_date = fields.Date(related='partner_id.birth_date', string='Date de naissance', store=True, readonly=False)
    gender = fields.Selection(related='partner_id.gender', string='Genre', store=True, readonly=False)

    sale_order_id = fields.Many2one('sale.order', string='Devis associé', readonly=True)

    # les informations du vol
    flight_number = fields.Char('Numéro de vol', required=True, tracking=True)
    airline = fields.Char('Compagnie aérienne', tracking=True)
    departure_date = fields.Date('Date de départ', required=True, tracking=True)
    departure_time = fields.Char('Heure de départ', tracking=True)
    arrival_date = fields.Date('Date arrivée', required=True, tracking=True)
    arrival_time = fields.Char('Heure arrivée', tracking=True)
    seat_preference = fields.Selection([
        ('window', 'Hublot'),
        ('aisle', 'Couloir'),
        ('middle', 'Milieu')
    ], string='Préférence de siège', default='window', tracking=True)
    meal_preference = fields.Selection([
        ('regular', 'Standard'),
        ('vegetarian', 'Végétarien'),
        ('halal', 'Halal'),
        ('kosher', 'Casher')
    ], string='Préférence de repas', default='regular', tracking=True)
    # Informations de prix
    price = fields.Float('Prix', required=True, tracking=True)
    currency = fields.Char('Devise', default='BDT', tracking=True)
    # État de la réservation
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('en attente de paiement', 'en attente de paiement'),
        ('confirmed', 'Confirmée'),
        ('cancelled', 'Annulée')
    ], string='État', default='draft', tracking=True)
    booking_reference = fields.Char('Référence de réservation', readonly=True, copy=False)
    sale_order_count = fields.Integer(string='Nombre de devis', compute='_compute_sale_order_count')
    payment_method = fields.Selection([
        ('stripe', 'Stripe'),
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
    ], string="Payment Method")
    payment_date = fields.Datetime(string="Payment Date")
    ticket_ids = fields.One2many('booking.ticket', 'booking_id', string='Tickets')
    ticket_count = fields.Integer(string='Nombre de tickets', compute='_compute_ticket_count')
    passenger_count = fields.Integer('Nombre de passagers', default=1, tracking=True)
    passengers = fields.Integer(string='Nombre de passagers', default=1)
    # Dans votre modèle booking
    adult_count = fields.Integer(string="adult_count", default=1)
    child_count = fields.Integer(string="child_count", default=0)
    infant_count = fields.Integer(string="infant_count", default=0)
    passenger_ids = fields.One2many('booking.passenger', 'booking_id', string='Passagers additionnels')

    @api.depends('sale_order_id')
    def _compute_sale_order_count(self):
        for booking in self:
            booking.sale_order_count = 1 if booking.sale_order_id else 0

    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'Devis',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
            'target': 'current',
        }



    @api.model
    def create(self, vals):
        # Si un partenaire est déjà spécifié directement, on l'utilise
        if vals.get('partner_id'):
            pass  # Rien à faire, le partenaire est déjà défini
        else:
            # Construire un domaine de recherche pour trouver un partenaire existant
            domain = []

            # Ajouter les critères de recherche disponibles
            if vals.get('email') and vals.get('email').strip():
                domain.append(('email', '=', vals.get('email').strip()))

            if vals.get('passport') and vals.get('passport').strip():
                domain.append(('passport_number', '=', vals.get('passport').strip()))

            if vals.get('phone') and vals.get('phone').strip():
                domain.append(('phone', '=', vals.get('phone').strip()))

            if vals.get('name') and vals.get('name').strip():
                domain.append(('name', 'ilike', vals.get('name').strip()))

            # Si nous avons au moins un critère de recherche
            if domain:
                # Rechercher avec une combinaison OR des critères
                existing_partner = False
                if len(domain) > 1:
                    # Si plusieurs critères, on les combine avec OR
                    existing_partner = self.env['res.partner'].search(['|' * (len(domain) - 1)] + domain, limit=1)
                else:
                    # Si un seul critère
                    existing_partner = self.env['res.partner'].search(domain, limit=1)

                if existing_partner:
                    # Mettre à jour le partenaire existant avec les nouvelles informations
                    partner_vals = {}
                    if vals.get('name') and vals.get('name').strip():
                        partner_vals['name'] = vals.get('name')
                    if vals.get('email') and vals.get('email').strip():
                        partner_vals['email'] = vals.get('email')
                    if vals.get('phone') and vals.get('phone').strip():
                        partner_vals['phone'] = vals.get('phone')
                    if vals.get('passport') and vals.get('passport').strip():
                        partner_vals['passport_number'] = vals.get('passport')
                    if vals.get('birth_date'):
                        partner_vals['birth_date'] = vals.get('birth_date')
                    if vals.get('gender'):
                        partner_vals['gender'] = vals.get('gender')

                    if partner_vals:
                        existing_partner.write(partner_vals)

                    vals['partner_id'] = existing_partner.id
                else:
                    # Création d'un nouveau contact
                    partner_vals = {
                        'name': vals.get('name', 'Passager inconnu'),
                        'email': vals.get('email', False),
                        'phone': vals.get('phone', False),
                        'type': 'contact',
                        'passport_number': vals.get('passport', False),
                        'birth_date': vals.get('birth_date', False),
                        'gender': vals.get('gender', False)
                    }
                    new_partner = self.env['res.partner'].create(partner_vals)
                    vals['partner_id'] = new_partner.id
            else:
                # Si aucun critère de recherche valide, créer un nouveau partenaire
                partner_vals = {
                    'name': vals.get('name', 'Passager inconnu'),
                    'email': vals.get('email', False),
                    'phone': vals.get('phone', False),
                    'type': 'contact',
                    'passport_number': vals.get('passport', False),
                    'birth_date': vals.get('birth_date', False),
                    'gender': vals.get('gender', False)
                }
                new_partner = self.env['res.partner'].create(partner_vals)
                vals['partner_id'] = new_partner.id

        # Générer la référence de réservation
        vals['booking_reference'] = self.env['ir.sequence'].next_by_code('booking.sequence')

        return super(TravelBooking, self).create(vals)

    def action_view_partner_bookings(self):
        """Afficher toutes les réservations d'un même partenaire"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Réservations de {self.partner_id.name}',
            'res_model': 'booking',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {'default_partner_id': self.partner_id.id},
            'target': 'current',
        }

    def _compute_booking_count(self):
        """Compter le nombre de réservations par partenaire"""
        booking_data = self.env['booking'].read_group(
            [('partner_id', 'in', self.ids)],
            ['partner_id'], ['partner_id']
        )
        mapped_data = {data['partner_id'][0]: data['partner_id_count'] for data in booking_data}
        for partner in self:
            partner.booking_count = mapped_data.get(partner.id, 0)

    booking_count = fields.Integer(string='Nombre de réservations', compute='_compute_booking_count')

    def write(self, vals):
        # Mettre à jour le contact associé si les informations changent
        if any(field in vals for field in ['name', 'email', 'phone', 'passport', 'birth_date', 'gender']):
            for record in self:
                if record.partner_id:
                    partner_vals = {}
                    if 'name' in vals:
                        partner_vals['name'] = vals['name']
                    if 'email' in vals:
                        partner_vals['email'] = vals['email']
                    if 'phone' in vals:
                        partner_vals['phone'] = vals['phone']
                    # Ajout des champs supplémentaires
                    if 'passport' in vals:
                        partner_vals['passport_number'] = vals['passport']
                    if 'birth_date' in vals:
                        partner_vals['birth_date'] = vals['birth_date']
                    if 'gender' in vals:
                        partner_vals['gender'] = vals['gender']

                    record.partner_id.write(partner_vals)

        return super(TravelBooking, self).write(vals)

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_confirm(self):
        for record in self:
            # Création du devis de vente (partie existante)
            sale_order_vals = {
                'partner_id': record.partner_id.id,
                'date_order': fields.Datetime.now(),
                'state': 'draft',
                'user_id': self.env.user.id,
            }

            # Création de la ligne de devis (partie existante)
            order_line_vals = [(0, 0, {
                'name': f'Réservation de vol - {record.flight_number}',
                'product_uom_qty': 1.0,
                'price_unit': record.price,
                'product_id': self.env.ref('travel_booking.product_flight').id,
            })]

            sale_order_vals['order_line'] = order_line_vals
            sale_order = self.env['sale.order'].create(sale_order_vals)

            # Liaison du devis avec la réservation
            record.write({
                'sale_order_id': sale_order.id,
                'state': 'en attente de paiement'
            })

            # Utilisation directe de la fonction mail_send
            try:
                email_to = record.email
                subject = f"En attent de paiement de billet de vol - {record.booking_reference}"
                departure_date = record.departure_date.strftime('%d/%m/%Y') if record.departure_date else ''
                arrival_date = record.arrival_date.strftime('%d/%m/%Y') if record.arrival_date else ''
                body_html = f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                        <h2 style="color: #2c3e50;">Votre réservation est en attente de paiement pour quelle soit confirmer</h2>
                        <p>Bonjour <strong>{record.name}</strong>,</p>
                        <p>Votre réservation de vol est en attente de paiement</p>

                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                            <h3 style="margin-top: 0; color: #3498db;">Détails de la réservation</h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Référence</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{record.booking_reference}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Vol</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{record.flight_number} ({record.airline or ''})</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Départ</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{departure_date} à {record.departure_time or ''}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Arrivée</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{arrival_date} à {record.arrival_time or ''}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Siège</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{dict(self._fields['seat_preference'].selection).get(record.seat_preference)}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Repas</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{dict(self._fields['meal_preference'].selection).get(record.meal_preference)}</td>
                                </tr>
                            </table>
                        </div>

                        <p>Nous vous remercions pour votre confiance et vous souhaitons un excellent voyage.</p>
                        <p style="color: #7f8c8d; font-size: 0.9em;">Ce message est généré automatiquement, merci de ne pas y répondre.</p>
                    </div>
                """
                # Création et envoi du mail en utilisant le modèle mail.mail
                mail_values = {
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': email_to,
                    'email_from': 'benmhennizaineb@gmail.com',
                    'auto_delete': True,
                }

                # Création et envoi direct (sans attachement au record)
                mail = self.env['mail.mail'].sudo().create(mail_values)
                mail.sudo().send(raise_exception=False)

                # Journalisation du succès
                _logger.info(f"Email envoyé avec succès à {email_to} pour la réservation {record.booking_reference}")

                # créer une note dans le chatter
                record.message_post(
                    body=f"Email d'attent de paiement de billet de vol envoyé à {email_to}",
                    subject="Envoi d'attent de paiement de billet de vol"
                )

            except Exception as e:
                _logger.error(f"Erreur lors de l'envoi de l'email: {str(e)}")
                record.message_post(
                    body=f"Erreur lors de l'envoi de l'email: {str(e)}",
                    subject="Erreur d'envoi"
                )

    def action_confirm1(self):
        for record in self:
            record.generate_tickets()

            # Mise à jour du contact existant pour le passager principal avec les informations supplémentaires
            if record.partner_id and record.birth_date and record.passport:
                record.partner_id.write({
                    'passport_number': record.passport,
                    'birth_date': record.birth_date,
                    'gender': record.gender
                })

            # Création de contacts pour les passagers additionnels
            for passenger in record.passenger_ids:
                # Vérifier si un contact existe déjà pour ce passager
                existing_partner = self.env['res.partner'].search([
                    ('passport_number', '=', passenger.passport),
                    ('name', '=', passenger.name)
                ], limit=1)

                if existing_partner:
                    # Mettre à jour le contact existant si nécessaire
                    existing_partner.write({
                        'birth_date': passenger.birth_date,
                        'gender': passenger.gender
                    })
                    # Associer ce contact au passager
                    passenger.write({'partner_id': existing_partner.id})
                else:
                    # Créer un nouveau contact pour le passager (sans relation parent_id)
                    partner_vals = {
                        'name': passenger.name,
                        'passport_number': passenger.passport,
                        'birth_date': passenger.birth_date,
                        'gender': passenger.gender,
                        'type': 'contact'
                        # Suppression de la ligne qui créait la relation parent_id
                    }
                    new_partner = self.env['res.partner'].create(partner_vals)
                    # Associer ce nouveau contact au passager
                    passenger.write({'partner_id': new_partner.id})

            # Reste du code original pour la création/confirmation de commande, facture, etc.
            if not record.sale_order_id:
                sale_order_vals = {
                    'partner_id': record.partner_id.id,
                    'date_order': fields.Datetime.now(),
                    'state': 'draft',
                    'user_id': self.env.user.id,
                    'user_id': self.env.user.id,
                }
                order_line_vals = [(0, 0, {
                    'name': f'Réservation de vol - {record.flight_number}',
                    'product_uom_qty': 1.0,
                    'price_unit': record.price,
                    'product_id': self.env.ref('travel_booking.product_flight').id,
                })]

                sale_order_vals['order_line'] = order_line_vals
                sale_order = self.env['sale.order'].create(sale_order_vals)
                record.sale_order_id = sale_order.id
            # Confirmation de la commande uniquement si elle est en état brouillon
            if record.sale_order_id.state == 'draft':
                record.sale_order_id.action_confirm()

            # Création de la facture si elle n'existe pas déjà
            if record.sale_order_id.invoice_status == 'to invoice':
                # Utilisation de la méthode standard de création de facture depuis la commande
                invoice_wizard = self.env['sale.advance.payment.inv'].with_context(
                    active_model='sale.order',
                    active_ids=[record.sale_order_id.id],
                    active_id=record.sale_order_id.id
                ).create({
                    'advance_payment_method': 'delivered'
                })

                # Correction ici: nous passons explicitement l'argument sale_orders
                invoice_wizard._create_invoices(sale_orders=record.sale_order_id)

                # Récupération de la facture créée
                invoice = record.sale_order_id.invoice_ids.filtered(lambda inv: inv.state == 'draft')

                if invoice:
                    # Validation de la facture
                    invoice.action_post()

                    # Enregistrement du paiement si nécessaire
                    if invoice.amount_residual > 0:
                        # Récupération du journal de paiement
                        payment_journal = self.env['account.journal'].search([
                            ('type', '=', 'bank'),
                            ('name', 'ilike', 'en ligne')
                        ], limit=1) or self.env['account.journal'].search([('type', '=', 'bank')], limit=1)

                        try:
                            # Création du paiement via le wizard standard
                            payment_register = self.env['account.payment.register'].with_context(
                                active_model='account.move',
                                active_ids=invoice.ids
                            ).create({
                                'journal_id': payment_journal.id,
                                'amount': invoice.amount_residual,
                                'payment_date': fields.Date.today(),
                            })

                            # Création et validation du paiement
                            payment = payment_register._create_payments()

                            record.sale_order_id.message_post(
                                body=f"Facture {invoice.name} créée, validée et payée automatiquement suite à la confirmation de la réservation {record.booking_reference}",
                                subject="Création et paiement de facture automatique"
                            )
                        except Exception as e:
                            _logger.error(f"Erreur lors de l'enregistrement du paiement: {str(e)}")
                    else:
                        record.sale_order_id.message_post(
                            body=f"Facture {invoice.name} créée et validée automatiquement suite à la confirmation de la réservation {record.booking_reference}",
                            subject="Création de facture automatique"
                        )

            # Mise à jour de l'état de la réservation
            record.write({'state': 'confirmed'})

            # Envoi de l'email de confirmation
            try:
                # Préparation du contenu du mail
                email_to = record.email
                subject = f"Confirmation de réservation - {record.booking_reference}"

                # Formatage des dates pour l'affichage
                departure_date = record.departure_date.strftime('%d/%m/%Y') if record.departure_date else ''
                arrival_date = record.arrival_date.strftime('%d/%m/%Y') if record.arrival_date else ''

                # Création du corps de l'email
                body_html = f"""
                                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                                        <h2 style="color: #2c3e50;">Confirmation de votre réservation</h2>
                                        <p>Bonjour <strong>{record.name}</strong>,</p>
                                        <p>Nous avons le plaisir de vous confirmer votre réservation de vol.</p>

                                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                                            <h3 style="margin-top: 0; color: #3498db;">Détails de la réservation</h3>
                                            <table style="width: 100%; border-collapse: collapse;">
                                                <tr>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Référence</strong></td>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{record.booking_reference}</td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Vol</strong></td>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{record.flight_number} ({record.airline or ''})</td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Départ</strong></td>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{departure_date} à {record.departure_time or ''}</td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Arrivée</strong></td>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{arrival_date} à {record.arrival_time or ''}</td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Siège</strong></td>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{dict(self._fields['seat_preference'].selection).get(record.seat_preference)}</td>
                                                </tr>
                                                <tr>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Repas</strong></td>
                                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{dict(self._fields['meal_preference'].selection).get(record.meal_preference)}</td>
                                                </tr>
                                            </table>
                                        </div>

                                        <p>Nous vous remercions pour votre confiance et vous souhaitons un excellent voyage.</p>
                                        <p>Veuillez trouver en pièce jointe votre billet de réservation.</p>
                                        <p style="color: #7f8c8d; font-size: 0.9em;">Ce message est généré automatiquement, merci de ne pas y répondre.</p>
                                    </div>
                                """

                # Générer le PDF du billet - Méthode corrigée pour Odoo 17
                try:
                    # Méthode 1 - Recommandée pour Odoo 17
                    report = self.env.ref('travel_booking.report_booking_ticket')
                    pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(report, [record.id])
                except Exception as pdf_error:
                    _logger.error(f"Erreur avec la première méthode de génération PDF: {str(pdf_error)}")
                    try:
                        # Méthode 2 - Alternative
                        from odoo.tools.pdf import merge_pdf
                        report = self.env.ref('travel_booking.report_booking_ticket')
                        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(report.id, [record.id])
                    except Exception as pdf_error2:
                        _logger.error(f"Erreur avec la deuxième méthode de génération PDF: {str(pdf_error2)}")
                        try:
                            # Méthode 3 - Fallback
                            report = self.env.ref('travel_booking.report_booking_ticket')
                            pdf_content = report.with_context(lang=self.env.user.lang).get_pdf([record.id])
                        except Exception as pdf_error3:
                            _logger.error(f"Toutes les méthodes de génération PDF ont échoué: {str(pdf_error3)}")
                            # En cas d'échec de toutes les méthodes, on continue sans pièce jointe
                            pdf_content = None

                # Nom du fichier PDF
                pdf_name = f"Billet_Reservation_{record.booking_reference}.pdf"

                # Création et envoi du mail en utilisant le modèle mail.mail
                mail_values = {
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': email_to,
                    'email_from': 'benmhennizaineb@gmail.com',
                    'auto_delete': True,
                }

                # Ajouter la pièce jointe seulement si le PDF a été généré
                if pdf_content:
                    mail_values['attachment_ids'] = [(0, 0, {
                        'name': pdf_name,
                        'datas': base64.b64encode(pdf_content),
                        'mimetype': 'application/pdf',
                    })]

                # Création et envoi direct
                mail = self.env['mail.mail'].sudo().create(mail_values)
                mail.sudo().send(raise_exception=False)

                message = f"Email de confirmation"
                if pdf_content:
                    message += " avec billet PDF"
                message += f" envoyé avec succès à {email_to} pour la réservation {record.booking_reference}"

                _logger.info(message)
                record.message_post(
                    body=f"Email de confirmation envoyé à {email_to}",
                    subject="Envoi de confirmation"
                )
            except Exception as e:
                _logger.error(f"Erreur lors de l'envoi de l'email: {str(e)}")
                record.message_post(
                    body=f"Erreur lors de l'envoi de l'email: {str(e)}",
                    subject="Erreur d'envoi"
                )
    @api.model
    def _cron_cancel_unpaid_bookings(self):
        # Calculer la date limite (24 heures avant maintenant)
        limit_datetime = fields.Datetime.now() - timedelta(hours=24)
        # Rechercher les réservations en attente de paiement créées il y a plus de 24h
        bookings_to_cancel = self.search([
            ('state', '=', 'en attente de paiement'),
            ('create_date', '<', limit_datetime)
        ])
        for booking in bookings_to_cancel:
            booking.write({
                'state': 'cancelled'
            })
            try:
                email_to = booking.email
                subject = f"Annulation de votre réservation - {booking.booking_reference}"
                departure_date = booking.departure_date.strftime('%d/%m/%Y') if booking.departure_date else ''
                arrival_date = booking.arrival_date.strftime('%d/%m/%Y') if booking.arrival_date else ''
                body_html = f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                        <h2 style="color: #e74c3c;">Annulation de votre réservation</h2>
                        <p>Bonjour <strong>{booking.name}</strong>,</p>
                        <p>Nous vous informons que votre réservation de vol a été <strong>automatiquement annulée</strong> après 24 heures sans paiement.</p>

                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                            <h3 style="margin-top: 0; color: #3498db;">Détails de la réservation annulée</h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Référence</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{booking.booking_reference}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Vol</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{booking.flight_number} ({booking.airline or ''})</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Départ</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{departure_date} à {booking.departure_time or ''}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Arrivée</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{arrival_date} à {booking.arrival_time or ''}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;"><strong>Prix</strong></td>
                                    <td style="padding: 8px 0; border-bottom: 1px solid #ddd;">{booking.price} {booking.currency}</td>
                                </tr>
                            </table>
                        </div>

                        <p>Si vous souhaitez toujours effectuer ce voyage, nous vous invitons à créer une nouvelle réservation via notre plateforme.</p>
                        <p>Nous restons à votre disposition pour toute information complémentaire.</p>
                        <p style="color: #7f8c8d; font-size: 0.9em;">Ce message est généré automatiquement, merci de ne pas y répondre.</p>
                    </div>
                """
                mail_values = {
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': email_to,
                    'email_from': 'benmhennizaineb@gmail.com',
                    'auto_delete': True,
                }
                mail = self.env['mail.mail'].sudo().create(mail_values)
                mail.sudo().send(raise_exception=False)
                _logger.info(
                    f"Email d'annulation envoyé avec succès à {email_to} pour la réservation {booking.booking_reference}")
                booking.message_post(
                    body=f"Cette réservation a été automatiquement annulée après 24 heures sans paiement. Email de notification envoyé à {email_to}.",
                    subject="Annulation automatique"
                )
            except Exception as e:
                _logger.error(f"Erreur lors de l'envoi de l'email d'annulation: {str(e)}")
                booking.message_post(
                    body=f"Cette réservation a été automatiquement annulée après 24 heures sans paiement. Erreur lors de l'envoi de l'email: {str(e)}",
                    subject="Annulation automatique"
                )

        _logger.info(f"Annulation automatique: {len(bookings_to_cancel)} réservations annulées")

    # Méthode pour calculer le nombre de tickets
    @api.depends('ticket_ids')
    def _compute_ticket_count(self):
        for booking in self:
            booking.ticket_count = len(booking.ticket_ids)

    # Ajouter cette méthode pour créer les tickets pour chaque passager
    def generate_tickets(self):
        self.ensure_one()
        # Supprimer les tickets existants pour éviter les doublons
        self.ticket_ids.unlink()

        # Créer un ticket pour le passager principal (le titulaire de la réservation)
        self.env['booking.ticket'].create({
            'booking_id': self.id,
            'partner_id': self.partner_id.id,
            'passenger_type': 'adult',
            'seat_preference': self.seat_preference,
            'meal_preference': self.meal_preference,
        })

        # Compteurs pour les passagers additionnels
        adult_count = 1  # Car nous avons déjà créé un ticket pour le passager principal
        child_count = 0
        infant_count = 0

        # Créer un ticket pour chaque passager additionnel
        for passenger in self.passenger_ids:
            passenger_type = passenger.passenger_type

            if passenger_type == 'adult':
                adult_count += 1
                count = adult_count
            elif passenger_type == 'child':
                child_count += 1
                count = child_count
            else:  # infant
                infant_count += 1
                count = infant_count

            self.env['booking.ticket'].create({
                'booking_id': self.id,
                'partner_id': passenger.partner_id.id,
                'passenger_type': passenger_type,
                'seat_preference': passenger.seat_preference,
                'meal_preference': passenger.meal_preference,
            })

        return True

    def action_view_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tickets',
            'res_model': 'booking.ticket',
            'view_mode': 'tree,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {'default_booking_id': self.id},
            'target': 'current',
        }

    @api.model
    def get_passenger_types(self):
        passenger_types = [
            {
                'name': 'Adults',
                'value': self.search_count([('adult_count', '>', 0)])
            },
            {
                'name': 'Children',
                'value': self.search_count([('child_count', '>', 0)])
            },
            {
                'name': 'Infants',
                'value': self.search_count([('infant_count', '>', 0)])
            }
        ]
        return passenger_types

    @api.model
    def get_ticket_types(self):
        ticket_types = [
            {
                'name': 'Economy',
                'count': self.search_count([('ticket_type', '=', 'economy')])
            },
            {
                'name': 'Business',
                'count': self.search_count([('ticket_type', '=', 'business')])
            },
            {
                'name': 'First Class',
                'count': self.search_count([('ticket_type', '=', 'first_class')])
            }
        ]
        return ticket_types
    @api.model
    def get_dashboard_data(self):
        # Ajoutez des vérifications de sécurité
        try:
            # Récupération des données de base
            data = {
                'total': self.search_count([]),
                'confirmed': self.search_count([('state', '=', 'confirmed')]),
                'pending': self.search_count([('state', '=', 'en attente de paiement')]),
                'cancelled': self.search_count([('state', '=', 'cancelled')]),
            }

            # Récupération des réservations récentes
            recent_bookings = self.search_read(
                [],
                ['id', 'name', 'flight_number', 'departure_date', 'state'],
                limit=10,
                order='payment_date desc'
            )
            data['recent_bookings'] = recent_bookings or []

            # Distribution par genre
            gender_records = self.search_read([('gender', '!=', False)], ['gender'])
            gender_counts = {}
            for record in gender_records:
                gender = record.get('gender', 'Unspecified')
                gender_counts[gender] = gender_counts.get(gender, 0) + 1
            data['gender_distribution'] = [{'name': k, 'value': v} for k, v in gender_counts.items()]

            # Distribution par compagnie aérienne
            airline_records = self.search_read([], ['airline'])
            airline_counts = {}
            for record in airline_records:
                airline = record.get('airline', 'Unspecified')
                airline_counts[airline] = airline_counts.get(airline, 0) + 1
            data['airline_distribution'] = [{'name': k, 'value': v} for k, v in airline_counts.items()]

            return data
        except Exception as e:
            _logger.error("Error in get_dashboard_data: %s", str(e))
            return {
                'total': 0,
                'confirmed': 0,
                'pending': 0,
                'cancelled': 0,
                'recent_bookings': [],
                'gender_distribution': [],
                'airline_distribution': []
            }