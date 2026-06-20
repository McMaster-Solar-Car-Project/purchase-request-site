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
});
