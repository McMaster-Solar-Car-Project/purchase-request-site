function updateFileName(input, displayId) {
    const display = document.getElementById(displayId);
    if (input.files.length > 0) {
        display.textContent = `Selected: ${input.files[0].name}`;
        display.style.color = '#28a745';
    } else {
        display.textContent = '';
    }
}

// Password strength checker
function checkPasswordStrength() {
    const password = document.getElementById('new_password').value;
    const strengthDiv = document.getElementById('password-strength');
    
    if (!password) {
        strengthDiv.className = 'password-strength';
        return;
    }
    
    let strength = 0;
    if (password.length >= 5) strength++;
    if (password.length >= 8) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^A-Za-z0-9]/.test(password)) strength++;
    
    if (strength <= 2) {
        strengthDiv.className = 'password-strength password-strength-weak';
    } else if (strength <= 3) {
        strengthDiv.className = 'password-strength password-strength-medium';
    } else {
        strengthDiv.className = 'password-strength password-strength-strong';
    }
}

// Password match checker
function checkPasswordMatch() {
    const newPassword = document.getElementById('new_password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const messageElement = document.getElementById('password-match-message');
    
    if (!confirmPassword) {
        messageElement.textContent = 'Must match new password';
        messageElement.style.color = '#6c757d';
        return;
    }
    
    if (newPassword === confirmPassword) {
        messageElement.textContent = '✓ Passwords match';
        messageElement.style.color = '#28a745';
    } else {
        messageElement.textContent = '✗ Passwords do not match';
        messageElement.style.color = '#dc3545';
    }
}

// Default Check
function validateDefault(){
    const name = document.getElementById('name').value;
    const personalEmail = document.getElementById('personal_email').value;
    const currentPassword = document.getElementById('current_password').value;
    
    //console.log("Default");

    if (name == "default_name"){
        alert('User is still using default name.');
        return false;
    } else if (personalEmail == "default_email@gmail.com"){
        alert('User is still using default personal email.');
        return false;
    } else if (currentPassword == "default_password123"){
        alert('User is still using default password.');
        return false;
    }
    return true;
}

// Password validation
function validatePasswords() {
    const newPassword = document.getElementById('new_password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const currentPassword = document.getElementById('current_password').value;
    
    //console.log("Password validate")

    // If any password field is filled, validate all
    if (newPassword || confirmPassword || currentPassword) {
        if (!currentPassword) {
            alert('Current password is required to change password');
            return false;
        }
        if (!newPassword) {
            alert('New password cannot be empty');
            return false;
        }
        if (newPassword.length < 5) {
            alert('New password must be at least 5 characters');
            return false;
        }
        if (newPassword !== confirmPassword) {
            alert('New password and confirmation do not match');
            return false;
        }
    }
    return true;
}

// Initialize form validation when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log("hi");
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const passwordsOk = validatePasswords();
            const defaultsOk = validateDefault();

            // Block form if any validation fails
            if (!passwordsOk || !defaultsOk) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        });
    }
}); 