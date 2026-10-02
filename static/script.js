// Enhanced functionality for Rent Me application

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide flash messages after 5 seconds (not notes that are part of the page)
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });

    // Confirm delete actions
    const deleteButtons = document.querySelectorAll('form[action*="delete"] button[type="submit"]');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this property? This action cannot be undone.')) {
                e.preventDefault();
            }
        });
    });

    // Form validation enhancement
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add('is-invalid');
                    isValid = false;
                } else {
                    field.classList.remove('is-invalid');
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                alert('Please fill in all required fields.');
            }
        });
    });

    // Favorite toggle functionality
    const favoriteButtons = document.querySelectorAll('.favorite-btn');
    favoriteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const propertyId = this.dataset.propertyId;
            
            fetch(`/favorite/${propertyId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content,
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    throw new Error(data.error);
                }
                const label = data.is_favorited ? 'Remove from favorites' : 'Add to favorites';
                this.innerHTML = data.is_favorited
                    ? '<i class="fas fa-heart text-danger"></i>'
                    : '<i class="far fa-heart"></i>';
                this.title = label;
                this.setAttribute('aria-label', label);
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            });
        });
    });

    // Search functionality enhancement
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        const searchInput = document.getElementById('search-input');
        const searchSuggestions = document.getElementById('search-suggestions');
        
        if (searchInput && searchSuggestions) {
            let debounceTimer;
            
            searchInput.addEventListener('input', function() {
                const query = this.value.trim();
                
                // Clear previous timer
                clearTimeout(debounceTimer);
                
                if (query.length > 2) {
                    // Debounce API calls
                    debounceTimer = setTimeout(() => {
                        fetch(`/api/search-suggestions?q=${encodeURIComponent(query)}`)
                            .then(response => response.json())
                            .then(suggestions => {
                                if (suggestions.length > 0) {
                                    searchSuggestions.innerHTML = suggestions
                                        .map(s => `<div class="suggestion-item" onclick="selectSuggestion('${s.replace(/'/g, "\\'")}')">${s}</div>`)
                                        .join('');
                                    searchSuggestions.style.display = 'block';
                                } else {
                                    searchSuggestions.style.display = 'none';
                                }
                            })
                            .catch(error => {
                                console.error('Error fetching suggestions:', error);
                                searchSuggestions.style.display = 'none';
                            });
                    }, 300);
                } else {
                    searchSuggestions.style.display = 'none';
                }
            });
            
            // Handle keyboard navigation
            searchInput.addEventListener('keydown', function(e) {
                const suggestions = searchSuggestions.querySelectorAll('.suggestion-item');
                const activeSuggestion = searchSuggestions.querySelector('.suggestion-item.active');
                
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (activeSuggestion) {
                        activeSuggestion.classList.remove('active');
                        const next = activeSuggestion.nextElementSibling;
                        if (next) {
                            next.classList.add('active');
                        } else {
                            suggestions[0].classList.add('active');
                        }
                    } else if (suggestions.length > 0) {
                        suggestions[0].classList.add('active');
                    }
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    if (activeSuggestion) {
                        activeSuggestion.classList.remove('active');
                        const prev = activeSuggestion.previousElementSibling;
                        if (prev) {
                            prev.classList.add('active');
                        } else {
                            suggestions[suggestions.length - 1].classList.add('active');
                        }
                    } else if (suggestions.length > 0) {
                        suggestions[suggestions.length - 1].classList.add('active');
                    }
                } else if (e.key === 'Enter') {
                    if (activeSuggestion) {
                        e.preventDefault();
                        selectSuggestion(activeSuggestion.textContent);
                    }
                } else if (e.key === 'Escape') {
                    searchSuggestions.style.display = 'none';
                }
            });
        }
    }
});

function selectSuggestion(suggestion) {
    const searchInput = document.getElementById('search-input');
    const searchSuggestions = document.getElementById('search-suggestions');
    
    if (searchInput) {
        searchInput.value = suggestion;
    }
    if (searchSuggestions) {
        searchSuggestions.style.display = 'none';
    }
}

// Close suggestions when clicking outside
document.addEventListener('click', function(e) {
    const searchSuggestions = document.getElementById('search-suggestions');
    const searchInput = document.getElementById('search-input');
    
    if (searchSuggestions && searchInput && 
        !searchInput.contains(e.target) && 
        !searchSuggestions.contains(e.target)) {
        searchSuggestions.style.display = 'none';
    }
});

