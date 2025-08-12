function updateFileName(input, displayId) {
    const display = document.getElementById(displayId);
    if (input.files.length > 0) {
        display.textContent = `Selected: ${input.files[0].name}`;
        display.className = 'mt-2 text-sm text-green-600 font-medium';
    } else {
        display.textContent = '';
        display.className = 'mt-2 text-sm text-gray-600';
    }
}

// Password strength checker
function checkPasswordStrength() {
    const password = document.getElementById('new_password').value;
    const strengthDiv = document.getElementById('password-strength');
    const strengthBar = strengthDiv.querySelector('div');
    
    if (!password) {
        strengthBar.className = 'h-full w-0 transition-all duration-300 ease-in-out rounded-full bg-red-500';
        return;
    }
    
    let strength = 0;
    if (password.length >= 5) strength++;
    if (password.length >= 8) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^A-Za-z0-9]/.test(password)) strength++;
    
    if (strength <= 2) {
        strengthBar.className = 'h-full w-1/3 transition-all duration-300 ease-in-out rounded-full bg-red-500';
    } else if (strength <= 3) {
        strengthBar.className = 'h-full w-2/3 transition-all duration-300 ease-in-out rounded-full bg-yellow-500';
    } else {
        strengthBar.className = 'h-full w-full transition-all duration-300 ease-in-out rounded-full bg-green-500';
    }
}

// Password match checker
function checkPasswordMatch() {
    const newPassword = document.getElementById('new_password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const messageElement = document.getElementById('password-match-message');
    
    if (!confirmPassword) {
        messageElement.textContent = 'Must match new password';
        messageElement.className = 'block text-gray-600 text-sm mt-1 italic';
        return;
    }
    
    if (newPassword === confirmPassword) {
        messageElement.textContent = '✓ Passwords match';
        messageElement.className = 'block text-green-600 text-sm mt-1 font-medium';
    } else {
        messageElement.textContent = '✗ Passwords do not match';
        messageElement.className = 'block text-red-600 text-sm mt-1 font-medium';
    }
}

// Password validation
function validatePasswords() {
    const newPassword = document.getElementById('new_password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const currentPassword = document.getElementById('current_password').value;

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
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            if (!validatePasswords()) {
                e.preventDefault();
            }
        });
    }
}); 