document.addEventListener('DOMContentLoaded', function() {
    // Récupérer le nombre de passagers depuis l'URL ou la valeur par défaut
    const urlParams = new URLSearchParams(window.location.search);
    const passengerCount = parseInt(urlParams.get('passengers')) || 1;
    
    // Ajouter un champ caché pour stocker le nombre de passagers
    const form = document.querySelector('.o_website_form');
    const hiddenPassengersField = document.createElement('input');
    hiddenPassengersField.type = 'hidden';
    hiddenPassengersField.name = 'passengers';
    hiddenPassengersField.value = passengerCount;
    form.appendChild(hiddenPassengersField);
    
    // Sélectionner le container où ajouter les formulaires de passagers
    const passengersContainer = document.createElement('div');
    passengersContainer.className = 'passengers-container mt-4';
    
    // Trouver l'endroit où insérer le container (avant le bouton de confirmation)
    const submitBtn = form.querySelector('[name="submit_to_payment"]').parentNode;
    form.insertBefore(passengersContainer, submitBtn);
    
    // Générer les formulaires pour chaque passager
    for (let i = 1; i <= passengerCount; i++) {
        const passengerForm = createPassengerForm(i, i === 1);
        passengersContainer.appendChild(passengerForm);
    }
});

function createPassengerForm(index, isMainPassenger) {
    const passengerDiv = document.createElement('div');
    passengerDiv.className = 'passenger-form mb-4 p-3 border rounded';
    
    // Titre du formulaire passager
    const title = document.createElement('h4');
    title.textContent = isMainPassenger ? 'Passager principal' : `Passager ${index}`;
    passengerDiv.appendChild(title);
    
    // Créer la structure en ligne
    const row = document.createElement('div');
    row.className = 'row';
    
    // Première colonne - Informations personnelles
    const col1 = document.createElement('div');
    col1.className = 'col-md-6';
    
    col1.innerHTML = `
        <div class="mb-3">
            <label class="form-label" for="name_${index}">Nom complet *</label>
            <input type="text" class="form-control" name="name_${index}" required="1"/>
        </div>
        <div class="mb-3">
            <label class="form-label" for="email_${index}">Email ${isMainPassenger ? '*' : ''}</label>
            <input type="email" class="form-control" name="email_${index}" ${isMainPassenger ? 'required="1"' : ''}/>
        </div>
        <div class="mb-3">
            <label class="form-label" for="phone_${index}">Téléphone ${isMainPassenger ? '*' : ''}</label>
            <input type="tel" class="form-control" name="phone_${index}" ${isMainPassenger ? 'required="1"' : ''}/>
        </div>
        <div class="mb-3">
            <label class="form-label" for="passport_${index}">Numéro de passeport *</label>
            <input type="text" class="form-control" name="passport_${index}" required="1"/>
        </div>
    `;
    
    // Deuxième colonne - Préférences (seulement si c'est un passager)
    const col2 = document.createElement('div');
    col2.className = 'col-md-6';
    
    col2.innerHTML = `
        <div class="mb-3">
            <label class="form-label" for="seat_preference_${index}">Préférence de siège</label>
            <select class="form-select" name="seat_preference_${index}">
                <option value="window">Hublot</option>
                <option value="aisle">Couloir</option>
                <option value="middle">Milieu</option>
            </select>
        </div>
        <div class="mb-3">
            <label class="form-label" for="meal_preference_${index}">Préférence de repas</label>
            <select class="form-select" name="meal_preference_${index}">
                <option value="regular">Standard</option>
                <option value="vegetarian">Végétarien</option>
                <option value="halal">Halal</option>
                <option value="kosher">Casher</option>
            </select>
        </div>
    `;
    
    row.appendChild(col1);
    row.appendChild(col2);
    passengerDiv.appendChild(row);
    
    return passengerDiv;
}