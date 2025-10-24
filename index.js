// This script handles the logic for the start game page.
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('startForm');
    const message = document.getElementById('message');
    const startButton = document.getElementById('startButton');
    const leaderboardButton = document.getElementById('leaderboardBtn');

    if (leaderboardButton) {
        leaderboardButton.addEventListener('click', () => {
            window.location.href = '/leaderboard';
        });
    }

    // Only add the event listener if the form exists (i.e., user is logged in)
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Show loading state on the button
            startButton.innerHTML = '<span class="btn-text">Preparing Quest...</span>';
            startButton.disabled = true;
            
            message.textContent = 'Initializing your magical adventure...';
            message.className = 'quest-message';

            const formData = new FormData(form);
            const data = {
                genre: formData.get('genre'),
                game_mode: formData.get('gameMode')
            };

            try {
                // Send a request to the backend to start the game
                const response = await fetch('/api/start-game', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include', // Ensure session cookie is sent
                    body: JSON.stringify(data)
                });

                const result = await response.json();
                
                if (response.ok && result.success) {
                    message.textContent = 'Quest initialized! Teleporting to the arena...';
                    message.className = 'quest-message success';
                    
                    // Add a fade-out effect before redirecting
                    document.body.style.transition = 'opacity 0.5s ease';
                    document.body.style.opacity = '0';
                    
                    setTimeout(() => {
                        window.location.href = result.game_url; // Use the URL provided by the server
                    }, 1000);
                } else {
                    throw new Error(result.error || 'Quest initialization failed');
                }
            } catch (error) {
                message.textContent = `Quest Error: ${error.message}`;
                message.className = 'quest-message error';
                
                // Reset the button to its original state
                startButton.innerHTML = '<span class="btn-text">Begin Quest</span>';
                startButton.disabled = false;
            }
        });
    }
});