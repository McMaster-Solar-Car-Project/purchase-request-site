// Address Autocomplete using Google Places API
let autocomplete;

function initAutocomplete() {
    console.log('Initializing Google Places Autocomplete...');
    
    // Check if Google Maps API is loaded
    if (typeof google === 'undefined' || typeof google.maps === 'undefined') {
        console.error('Google Maps API not loaded');
        showFallback();
        return;
    }
    
    // Check if the address input exists
    const addressInput = document.getElementById('address');
    if (!addressInput) {
        console.error('Address input field not found');
        return;
    }
    
    try {
        // Create the autocomplete object
        autocomplete = new google.maps.places.Autocomplete(
            addressInput,
            {
                types: ['address'],
                componentRestrictions: {'country': ['ca', 'us']}, // Restrict to Canada and US
                fields: ['formatted_address', 'geometry', 'address_components']
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
            addressInput.value = place.formatted_address;
            console.log('Address selected:', place.formatted_address);
            
            // Optional: You can extract individual address components
            // const addressComponents = place.address_components;
            // console.log('Address components:', addressComponents);
        });
        
        console.log('Google Places Autocomplete initialized successfully');
        
    } catch (error) {
        console.error('Error initializing autocomplete:', error);
        showFallback();
    }
}

function showFallback() {
    const helpText = document.querySelector('.address-help');
    if (helpText) {
        helpText.textContent = 'Please enter your full address manually. (Address autocomplete unavailable)';
        helpText.style.color = '#dc3545';
    }
}

// Fallback if Google Maps API fails to load within 10 seconds
window.setTimeout(function() {
    if (typeof google === 'undefined') {
        console.log('Google Maps API failed to load within 10 seconds. Address autocomplete disabled.');
        showFallback();
    }
}, 10000); 