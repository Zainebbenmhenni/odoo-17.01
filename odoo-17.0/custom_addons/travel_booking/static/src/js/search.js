/** @odoo-module **/

import { registry } from '@web/core/registry';
import publicWidget from '@web/legacy/js/public/public_widget';

const { Component, useState, onWillStart } = owl;

publicWidget.registry.FlightSearchForm = publicWidget.Widget.extend({
    selector: '#flight-search-form',
    events: {
        'change input[name="trip_type"]': '_onChangeTripType',
        'click #add-segment': '_onAddSegment',
        'click .remove-segment': '_onRemoveSegment',
        'submit': '_onFormSubmit'
    },

    start: function () {
        var def = this._super.apply(this, arguments);
        this.segmentCount = 1;
        return def;
    },

    _onChangeTripType: function (ev) {
        var tripType = $(ev.currentTarget).val();

        if (tripType === 'MultiCity') {
            $('#standard-form').hide();
            $('#multi-city-form').show();
            $('#date-selection').hide();
            $('.return-date-container').hide();
        } else {
            $('#standard-form').show();
            $('#multi-city-form').hide();
            $('#date-selection').show();

            if (tripType === 'RoundTrip') {
                $('.return-date-container').show();
                $('#return_date').prop('required', true);
            } else {
                $('.return-date-container').hide();
                $('#return_date').prop('required', false);
            }
        }
    },

    _onAddSegment: function () {
        this.segmentCount++;

        // Récupérer toutes les options d'aéroport depuis le premier select
        var airportOptions = $('#departure').html();

        var newSegment = `
            <div class="multi-city-segment mb-3">
                <div class="row mb-2">
                    <div class="col-md-5">
                        <label class="form-label">Départ</label>
                        <select class="form-select" name="segment_origin_${this.segmentCount}" required="required">
                            ${airportOptions}
                        </select>
                    </div>
                    <div class="col-md-5">
                        <label class="form-label">Destination</label>
                        <select class="form-select" name="segment_destination_${this.segmentCount}" required="required">
                            ${airportOptions}
                        </select>
                    </div>
                    <div class="col-md-2">
                        <label class="form-label">Date</label>
                        <input type="date" class="form-control" name="segment_date_${this.segmentCount}" required="required"/>
                    </div>
                </div>
                <button type="button" class="btn btn-sm btn-danger remove-segment">Supprimer</button>
            </div>
        `;
        $('#multi-city-segments').append(newSegment);
    },

    _onRemoveSegment: function (ev) {
        $(ev.currentTarget).closest('.multi-city-segment').remove();
    },

    _onFormSubmit: function () {
        $('#search-flights-btn').prop('disabled', true);
        $('#loading-spinner').show();
    }
});

export default publicWidget.registry.FlightSearchForm;