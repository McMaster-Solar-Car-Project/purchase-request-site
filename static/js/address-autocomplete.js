// Address Autocomplete using Google Places API
let autocomplete;

function initAutocomplete() {
    // Create the autocomplete object
    autocomplete = new google.maps.places.Autocomplete(
        document.getElementById('address'),
        {
            types: ['address'],
            componentRestrictions: {'country': ['ca', 'us']}, // Restrict to Canada and US
        }
    );
    
    // When the user selects an address from the dropdown, populate the address field
    autocomplete.addListener('place_changed', function() {
        const place = autocomplete.getPlace();
        
        if (!place.geometry) {
            // User entered the name of a Place that was not suggested and
            // pressed the Enter key, or the Place Details request failed.
            console.log("No details available for input: '" + place.name + "'");
            return;
        }
        
        // Get the formatted address
        document.getElementById('address').value = place.formatted_address;
        
        // Optional: You can extract individual address components
        // const addressComponents = place.address_components;
        // console.log('Address components:', addressComponents);
    });
}

// Fallback if Google Maps API fails to load
window.setTimeout(function() {
    if (typeof google === 'undefined') {
        console.log('Google Maps API failed to load. Address autocomplete disabled.');
        const helpText = document.querySelector('.address-help');
        if (helpText) {
            helpText.textContent = 'Please enter your full address manually.';
            helpText.style.color = '#dc3545';
        }
    }
}, 5000); 