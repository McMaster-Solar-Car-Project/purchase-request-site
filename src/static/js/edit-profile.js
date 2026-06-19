function updateFileName(input, displayId) {
    const display = document.getElementById(displayId);
    if (!display) return;
    if (input.files.length > 0) {
        display.textContent = `Selected: ${input.files[0].name}`;
        display.style.color = '#28a745';
    } else {
        display.textContent = '';
    }
}

function validateDefault() {
    const name = document.getElementById('name').value;
    const personalEmail = document.getElementById('personal_email').value;

    if (name === 'default_name') {
        alert('User is still using default name.');
        return false;
    } else if (personalEmail === 'default_email@gmail.com') {
        alert('User is still using default personal email.');
        return false;
    }
    return true;
}

function showAddressFallback() {
    const helpText = document.querySelector('.address-help');
    if (helpText) {
        helpText.textContent = 'Please enter your full address manually. (Address autocomplete unavailable)';
        helpText.style.color = '#ef4444';
    }
}

// Exposed on window because the Google Maps script calls it as a JSONP-style
// callback (?callback=initAutocomplete). Module-scope functions wouldn't be
// reachable from that external load.
window.initAutocomplete = function () {
    console.log('Initializing Google Places Autocomplete...');

    if (typeof google === 'undefined' || typeof google.maps === 'undefined') {
        console.error('Google Maps API not loaded');
        showAddressFallback();
        return;
    }

    const addressInput = document.getElementById('address');
    if (!addressInput) {
        console.error('Address input field not found');
        return;
    }

    try {
        const autocomplete = new google.maps.places.Autocomplete(
            addressInput,
            {
                types: ['address'],
                componentRestrictions: { country: ['ca', 'us'] },
                fields: ['formatted_address', 'geometry', 'address_components'],
            }
        );

        autocomplete.addListener('place_changed', function () {
            const place = autocomplete.getPlace();
            if (!place.geometry) {
                console.log(`No details available for input: '${place.name}'`);
                return;
            }
            addressInput.value = place.formatted_address;
            console.log('Address selected:', place.formatted_address);
        });

        console.log('Google Places Autocomplete initialized successfully');
    } catch (error) {
        console.error('Error initializing autocomplete:', error);
        showAddressFallback();
    }
};

function showUrlErrorAlerts() {
    const params = new URLSearchParams(window.location.search);
    const error = params.get('error');

    if (error === 'default_values') {
        alert('⚠️ Default values must be changed before saving your profile.');
    } else if (error === 'update_failed') {
        alert('⚠️ Could not update profile. Ensure signature is a valid image and void cheque is a valid PDF.');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    showUrlErrorAlerts();

    const form = document.querySelector('form');

    if (form) {
        form.addEventListener('submit', function (e) {
            if (!validateDefault()) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        });
    }

    document.querySelectorAll('input[type="file"][data-filename-id]').forEach(input => {
        input.addEventListener('change', () => updateFileName(input, input.dataset.filenameId));
    });

    const googleMapsEnabled = document.body.dataset.googleMapsEnabled === 'true';
    if (!googleMapsEnabled) {
        showAddressFallback();
        return;
    }

    // Safety net: if the Google Maps script fails to load within 10 seconds,
    // fall back to manual address entry instead of leaving the user with a
    // silently broken autocomplete.
    window.setTimeout(function () {
        if (typeof google === 'undefined') {
            console.log('Google Maps API failed to load within 10 seconds. Address autocomplete disabled.');
            showAddressFallback();
        }
    }, 10000);
});
