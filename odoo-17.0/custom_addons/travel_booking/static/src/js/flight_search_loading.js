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
        this._updateReturnDateVisibility();
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
            $('#loading-spinner').show();
        }

        // Continuer avec la soumission normale du formulaire
        return true;
    },

    /**
     * Gère le changement de type de voyage
     * @private
     * @param {Event} ev
     */
    _onTripTypeChange: function(ev) {
        this._updateReturnDateVisibility();
    },

    /**
     * Met à jour la visibilité du champ de date de retour
     * @private
     */
    _updateReturnDateVisibility: function() {
        const tripType = $('input[name="trip_type"]:checked').val();
        if (tripType === 'RoundTrip') {
            $('#return-date-section').show();
            $('#return_date').prop('required', true);
        } else {
            $('#return-date-section').hide();
            $('#return_date').prop('required', false);
        }
    }
});

export default {
    flightSearchWidget: publicWidget.registry.flightSearchWidget
};