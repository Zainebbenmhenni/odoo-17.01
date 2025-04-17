// Variables globales pour stocker les vols sélectionnés
let selectedOutboundFlight = null;
let selectedReturnFlight = null;
let tripType = '';

// Fonction exécutée au chargement de la page
document.addEventListener('DOMContentLoaded', function() {
    // Récupérer le type de voyage depuis un attribut data sur le body ou un élément spécifique
    tripType = document.getElementById('flightSearchResults').getAttribute('data-trip-type');

    // Afficher la bande de sélection
    document.getElementById('selectedFlightsBar').style.display = 'block';

    // Vérifier si c'est un aller simple
    if (tripType === 'OneWay') {
        // Masquer le conteneur du vol retour dans la bande de sélection
        document.getElementById('selectedReturnFlightContainer').classList.add('d-none');
    }
});

// Fonction pour sélectionner un vol
function selectFlight(button) {
    const flightData = {
        id: button.getAttribute('data-flight-id'),
        type: button.getAttribute('data-flight-type'),
        flightNumber: button.getAttribute('data-flight-number'),
        departureTime: button.getAttribute('data-departure-time'),
        departureDate: button.getAttribute('data-departure-date'),
        arrivalTime: button.getAttribute('data-arrival-time'),
        arrivalDate: button.getAttribute('data-arrival-date'),
        airline: button.getAttribute('data-airline'),
        price: button.getAttribute('data-price'),
        currency: button.getAttribute('data-currency'),
        baggage: button.getAttribute('data-baggage'),
        isRecommended: button.getAttribute('data-is-recommended') === 'true'
    };

    // Mettre à jour la variable correspondante selon le type de vol
    if (flightData.type === 'outbound') {
        selectedOutboundFlight = flightData;
        updateSelectedFlightDisplay('outbound', flightData);

        // Mettre à jour tous les boutons de vol aller
        updateButtonsState('outbound', flightData.id);
    } else if (flightData.type === 'return') {
        selectedReturnFlight = flightData;
        updateSelectedFlightDisplay('return', flightData);

        // Mettre à jour tous les boutons de vol retour
        updateButtonsState('return', flightData.id);
    }

    // Vérifier si tous les vols nécessaires sont sélectionnés
    checkBookingAvailability();
}

// Fonction pour mettre à jour l'affichage des vols sélectionnés
function updateSelectedFlightDisplay(flightType, flightData) {
    const containerId = flightType === 'outbound' ? 'selectedOutboundFlightContainer' : 'selectedReturnFlightContainer';
    const detailsId = flightType === 'outbound' ? 'selectedOutboundFlightDetails' : 'selectedReturnFlightDetails';

    // Afficher le conteneur
    document.getElementById(containerId).classList.remove('d-none');

    // Mettre à jour les détails
    const detailsContainer = document.getElementById(detailsId);
    detailsContainer.innerHTML = `
        <div class="row">
            <div class="col-6">
                <strong>${flightData.airline}</strong><br>
                <small>Vol: ${flightData.flightNumber}</small>
            </div>
            <div class="col-6 text-end">
                <strong>${flightData.price} ${flightData.currency}</strong>
            </div>
        </div>
        <div class="row mt-2">
            <div class="col-5">
                <div>${flightData.departureTime}</div>
                <small class="text-muted">${flightData.departureDate}</small>
            </div>
            <div class="col-2 text-center">
                <i class="fa fa-arrow-right"></i>
            </div>
            <div class="col-5 text-end">
                <div>${flightData.arrivalTime}</div>
                <small class="text-muted">${flightData.arrivalDate}</small>
            </div>
        </div>
        ${flightData.isRecommended ? '<div class="mt-2"><span class="badge bg-success"><i class="fa fa-thumbs-up me-1"></i> Recommandé</span></div>' : ''}
    `;

    // Masquer le message "aucun vol sélectionné"
    document.getElementById('noFlightsMessage').classList.add('d-none');

    // Mettre à jour les données du formulaire final
    if (flightType === 'outbound') {
        document.getElementById('outboundFlightId').value = flightData.id;
    } else {
        document.getElementById('returnFlightId').value = flightData.id;
    }
}

// Fonction pour mettre à jour l'état des boutons
function updateButtonsState(flightType, selectedId) {
    const buttons = document.querySelectorAll(`.select-flight-btn[data-flight-type="${flightType}"]`);
    buttons.forEach(button => {
        const buttonId = button.getAttribute('data-flight-id');
        if (buttonId === selectedId) {
            button.classList.remove('btn-outline-primary', 'btn-outline-secondary');
            button.classList.add(flightType === 'outbound' ? 'btn-primary' : 'btn-secondary');
            button.innerHTML = '<i class="fa fa-check-circle me-1"></i> Sélectionné';
        } else {
            button.classList.remove('btn-primary', 'btn-secondary');
            button.classList.add(flightType === 'outbound' ? 'btn-outline-primary' : 'btn-outline-secondary');
            button.innerHTML = '<i class="fa fa-check me-1"></i> Choisir';
        }
    });
}

// Fonction pour supprimer un vol sélectionné
function removeSelectedFlight(flightType) {
    if (flightType === 'outbound') {
        selectedOutboundFlight = null;
        document.getElementById('selectedOutboundFlightContainer').classList.add('d-none');
        document.getElementById('outboundFlightId').value = '';
        updateButtonsState('outbound', '');
    } else if (flightType === 'return') {
        selectedReturnFlight = null;
        document.getElementById('selectedReturnFlightContainer').classList.add('d-none');
        document.getElementById('returnFlightId').value = '';
        updateButtonsState('return', '');
    }

    // Vérifier si tous les vols sont désélectionnés
    if (!selectedOutboundFlight && !selectedReturnFlight) {
        document.getElementById('noFlightsMessage').classList.remove('d-none');
    }

    // Vérifier si tous les vols nécessaires sont sélectionnés
    checkBookingAvailability();
}

// Fonction pour vérifier si la réservation est possible
function checkBookingAvailability() {
    const bookingButtonContainer = document.getElementById('bookingButtonContainer');

    // Vérifier les conditions selon le type de voyage
    if (tripType === 'OneWay' && selectedOutboundFlight) {
        bookingButtonContainer.classList.remove('d-none');
    } else if (tripType === 'RoundTrip' && selectedOutboundFlight && selectedReturnFlight) {
        bookingButtonContainer.classList.remove('d-none');
    } else {
        bookingButtonContainer.classList.add('d-none');
    }
}