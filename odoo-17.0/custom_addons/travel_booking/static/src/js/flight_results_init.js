odoo.define('travel_booking.flight_results', function (require) {
  'use strict';

  const { Component, createElement } = require('react');
  const { createRoot } = require('react-dom/client');
  const FlightResults = require('travel_booking/static/src/js/components/FlightResults');

  const mountComponent = () => {
    const element = document.getElementById('flight-results-root');
    if (element) {
      try {
        const root = createRoot(element);
        const flights = JSON.parse(element.dataset.flights || '{}');
        const searchParams = JSON.parse(element.dataset.searchParams || '{}');

        root.render(
          createElement(FlightResults, {
            searchResults: flights,
            searchParams: searchParams
          })
        );
        console.log("Composant React monté avec succès");
      } catch (error) {
        console.error("Erreur lors du montage du composant React:", error);
      }
    } else {
      console.warn("L'élément #flight-results-root n'a pas été trouvé");
    }
  };

  // Initialize on document ready
  document.addEventListener('DOMContentLoaded', mountComponent);
});