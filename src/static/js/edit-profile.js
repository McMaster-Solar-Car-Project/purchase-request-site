function updateFileName(input, displayId) {
    const display = document.getElementById(displayId);
    if (input.files.length > 0) {
        display.textContent = `Selected: ${input.files[0].name}`;
        display.style.color = '#28a745';
    } else {
        display.textContent = '';
    }
}

// Default Check
function validateDefault(){
    const name = document.getElementById('name').value;
    const personalEmail = document.getElementById('personal_email').value;

    if (name == "default_name"){
        alert('User is still using default name.');
        return false;
    } else if (personalEmail == "default_email@gmail.com"){
        alert('User is still using default personal email.');
        return false;
    } 
    return true;
}

// Initialize form validation when page loads
document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    const backLink = document.getElementById('back-link');
    if (backLink) {
        backLink.addEventListener('click', function(e) {
            const defaultsOk = validateDefault();
            if (!defaultsOk) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
            return true;
        });
    }
    if (form) {
        form.addEventListener('submit', function(e) {
            const defaultsOk = validateDefault();

            // Block form if validation fails
            if (!defaultsOk) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        });
    }
}); 
