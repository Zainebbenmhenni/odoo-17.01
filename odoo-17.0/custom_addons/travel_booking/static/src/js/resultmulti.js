/** @odoo-module **/
import publicWidget from 'web.public.widget';

publicWidget.registry.flightSearchWidget = publicWidget.Widget.extend({
    selector: '#wrap',
    events: {
        'submit #flight-search-form': '_onFormSubmit',
        'change input[name="trip_type"]': '_onTripTypeChange'
    },

    /**
     * @override
     */
    start: function() {
        console.log("Widget de recherche de vol initialisé");
        this._onTripTypeChange(); // Initialiser l'affichage au chargement
        return this._super.apply(this, arguments);
    },

    /**
     * Gère la soumission du formulaire
     * @private
     * @param {Event} ev
     */
    _onFormSubmit: function(ev) {
        console.log("Soumission du formulaire détectée par le widget");

        // Vérifier que les champs requis sont remplis
        if (ev.currentTarget.checkValidity()) {
            console.log("Formulaire valide, affichage de l'écran de chargement");

            // Activer l'overlay de chargement
            $('#loading-overlay').addClass('active');
        }

        // Continuer avec la soumission normale du formulaire
        return true;
    },

    /**
     * Gère le changement de type de voyage
     * @private
     */
    _onTripTypeChange: function() {
        const tripType = $('input[name="trip_type"]:checked').val();

        // Afficher/masquer la date de retour selon le type de voyage
        if (tripType === 'RoundTrip') {
            $('#return-date-section').show();
            $('#return_date').prop('required', true);
        } else {
            $('#return-date-section').hide();
            $('#return_date').prop('required', false);
        }

        // Pour MultiCity, on pourrait ajouter d'autres champs ici
        if (tripType === 'MultiCity') {
            // Afficher des champs supplémentaires pour les trajets multiples
            // Cette fonctionnalité nécessiterait un développement plus complexe
        }
    }
});

export default {
    flightSearchWidget: publicWidget.registry.flightSearchWidget
};