// This script handles the game logic on the client side.
document.addEventListener('DOMContentLoaded', () => {
    // Centralized game state for better management
    const gameState = {
        currentQuestions: [],
        currentQuestionIndex: 0,
        questScore: 0,
        totalAnswered: 0,
        hintCount: 0 // Will be initialized from server
    };
    let readingTimerInterval = null;

    // DOM Elements
    const storySection = document.getElementById('storySection');
    const quizSection = document.getElementById('quizSection');
    const storyText = document.getElementById('storyText');
    const questionText = document.getElementById('questionText');
    const answerOptions = document.getElementById('answerOptions');
    const quizProgressBar = document.getElementById('quizProgressBar');
    const nextBtn = document.getElementById('nextBtn');
    const newQuestBtn = document.getElementById('newQuestBtn');
    const scoreBar = document.getElementById('scoreBar');
    const message = document.getElementById('message');
    const questionCounter = document.getElementById('questionCounter');
    const resultsModal = document.getElementById('resultsModal');
    const continueBtn = document.getElementById('continueBtn');
    const tryAgainBtn = document.getElementById('tryAgainBtn');
    const skipStoryBtn = document.getElementById('skipStoryBtn');
    const startQuizBtn = document.getElementById('startQuizBtn');
    const skipLevelBtn = document.getElementById('skipLevelBtn');
    const levelBadge = document.getElementById('levelBadge');
    const maxLevelSpan = document.getElementById('maxLevel');
    const genreBadge = document.getElementById('genreBadge');
    const hintBtn = document.getElementById('hintBtn');
    const hintCountSpan = document.getElementById('hintCount');

    /**
     * Initializes the UI with game information like genre and level.
     */
    function initializeUI() {
        const gameInfo = document.getElementById('gameInfo');
        const genre = gameInfo.dataset.genre;
        const level = gameInfo.dataset.level;
        const maxLevel = gameInfo.dataset.maxLevel;
        const initialHints = gameInfo.dataset.hints;

        if (genre) {
            genreBadge.textContent = genre;
            genreBadge.classList.remove('hidden');
        }

        if (level && maxLevel) {
            document.getElementById('currentLevel').textContent = level;
            maxLevelSpan.textContent = maxLevel;
            levelBadge.classList.remove('hidden');
        }

        if (initialHints) {
            gameState.hintCount = parseInt(initialHints, 10);
            updateHintDisplay();
        }
    }

    // --- Initial Setup ---
    initializeUI();
    updateHintDisplay();
    loadNewQuest();

    startQuizBtn.addEventListener('click', startQuiz);

    /**
     * Loads a new story and quiz questions.
     */
    async function loadNewQuest() {
        showMessage('Conjuring your epic tale...', 'loading');
        storyText.textContent = ''; // Clear previous story

        // Reset client-side scores for the new round
        gameState.questScore = 0;
        gameState.totalAnswered = 0;
        if (quizProgressBar) quizProgressBar.style.width = '0%';
        updateScoreDisplay();

        skipStoryBtn.classList.add('hidden');
        startQuizBtn.classList.add('hidden');
        quizSection.classList.add('hidden');
        storySection.classList.remove('hidden');

        let fullStory = '';
        try {
            // Fetch and stream the story from the backend
            const response = await fetch('/api/generate-story-stream', {
                method: 'POST',
                credentials: 'include'
            });
            if (response.status === 400) {
                const errorData = await response.json();
                showMessage(`${errorData.error} Redirecting to home...`, 'error');
                setTimeout(() => window.location.href = '/', 3000);
                return;
            }
            if (!response.ok) {
                throw new Error('Failed to start story stream.');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            // Read the streamed story chunk by chunk
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                fullStory += chunk;
                storyText.innerHTML = fullStory.replace(/\n/g, '<br>'); // Append text in real-time
            }

            // After the story is loaded, fetch the quiz questions
            const questionsLoaded = await loadQuizForStory(fullStory);

            if (questionsLoaded) {
                showMessage('Your quest is ready! Read the story carefully.', 'info');
                startQuizBtn.classList.remove('hidden');
                skipStoryBtn.classList.remove('hidden');

                // Start a reading timer for the progressive challenge mode
                const gameInfo = document.getElementById('gameInfo');
                const isLevelMode = gameInfo.dataset.level !== '';

                if (isLevelMode) {
                    // Calculate reading time appropriate for grades 6-10 and adjust by level
                    const wordCount = fullStory.trim().split(/\s+/).length;
                    const baseWPM = 195; // Average reading speed for a 6th grader
                    const levelBonusWPM = (parseInt(gameInfo.dataset.level, 10) || 1) * 2; // Increase speed expectation slightly per level
                    const effectiveWPM = baseWPM + levelBonusWPM;
                    
                    // Calculate time in seconds, with a minimum of 30 seconds
                    const readingTimeInSeconds = Math.round((wordCount / effectiveWPM) * 60);
                    startReadingTimer(Math.max(30, readingTimeInSeconds));
                } else {
                    stopReadingTimer();
                }
            } else {
                showMessage('Could not generate questions for this story. Please try a new adventure!', 'error');
                newQuestBtn.classList.remove('hidden');
            }
        } catch (error) {
            showMessage(`Quest Error: ${error.message}`, 'error');
        }
    }

    /**
     * Fetches quiz questions for the given story.
     * @param {string} story The story text.
     * @returns {boolean} Whether the questions were loaded successfully.
     */
    async function loadQuizForStory(story) {
        showMessage('Preparing your challenge...', 'loading');
        try {
            const response = await fetch('/api/generate-quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ story: story })
            });

            if (response.status === 400) {
                const errorData = await response.json();
                showMessage(`${errorData.error} Redirecting to home...`, 'error');
                setTimeout(() => { window.location.href = '/'; }, 3000);
                return false;
            }

            const data = await response.json();
            if (data.success) {
                gameState.currentQuestions = data.questions;
                gameState.currentQuestionIndex = 0;
                return true;
            } else {
                throw new Error(data.error || 'Failed to load quiz');
            }
        } catch (error) {
            showMessage(`Quiz Error: ${error.message}`, 'error');
            return false;
        }
    }

    /**
     * Starts the quiz section.
     */
    function startQuiz() {
        stopReadingTimer();

        if (!gameState.currentQuestions || gameState.currentQuestions.length === 0) {
            showMessage('Could not generate questions. Please try a new adventure!', 'error');
            newQuestBtn.classList.remove('hidden');
            return;
        }

        skipStoryBtn.classList.add('hidden');
        storySection.classList.add('hidden');
        quizSection.classList.remove('hidden');
        showCurrentQuestion();
    }

    /**
     * Displays the current question and answer options.
     */
    function showCurrentQuestion() {
        if (gameState.currentQuestionIndex >= gameState.currentQuestions.length) {
            showQuestResults();
            return;
        }

        const question = gameState.currentQuestions[gameState.currentQuestionIndex];
        questionCounter.textContent = `Question ${gameState.currentQuestionIndex + 1} of ${gameState.currentQuestions.length}`;
        questionText.innerHTML = question.question;

        // Update the quiz progress bar
        if (quizProgressBar) {
            const progressPercentage = (gameState.currentQuestionIndex / gameState.currentQuestions.length) * 100;
            quizProgressBar.style.width = `${progressPercentage}%`;
        }

        answerOptions.innerHTML = '';
        Object.entries(question.options).forEach(([key, value]) => {
            const button = document.createElement('button');
            button.className = 'option-btn';
            button.innerHTML = `<strong>${key})</strong> ${value}`;
            button.onclick = () => selectAnswer(key, button);
            answerOptions.appendChild(button);
        });

        nextBtn.classList.add('hidden');
        hintBtn.disabled = (gameState.hintCount <= 0); // Re-enable hint button if hints are available
    }

    /**
     * Handles the user's answer selection.
     * @param {string} selectedAnswer The selected answer key (A, B, C, or D).
     * @param {HTMLElement} buttonElement The button element that was clicked.
     */
    async function selectAnswer(selectedAnswer, buttonElement) {
        const question = gameState.currentQuestions[gameState.currentQuestionIndex];
        
        const allButtons = answerOptions.querySelectorAll('.option-btn');
        allButtons.forEach(btn => btn.disabled = true);

        hintBtn.disabled = true;
        const is_correct = (selectedAnswer === question.correct);

        if (is_correct) {
            buttonElement.classList.add('correct');
            gameState.questScore++;
            showMessage('Excellent! You got it right!', 'success');
        } else {
            buttonElement.classList.add('incorrect');
            buttonElement.classList.add('shake');
            allButtons.forEach(btn => {
                if (btn.innerHTML.includes(`<strong>${question.correct})</strong>`)) {
                    btn.classList.add('correct');
                }
            });
            showMessage(`Not quite! The correct answer was ${question.correct}`, 'error');
        }
        
        try {
            // Submit the answer to the server
            const response = await fetch('/api/submit-answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ is_correct: is_correct })
            });
            const result = await response.json();
            if (!result.success) {
                console.error("Failed to update score on server:", result.error);
            }
        } catch (error) {
            console.error("Error submitting score:", error.message);
        }

        gameState.totalAnswered++;
        updateScoreDisplay();

        // Show the next button immediately for a more responsive feel
        nextBtn.classList.remove('hidden');
    }

    /**
     * Shows the results of the quest in a modal.
     */
    async function showQuestResults() {
        const resultsTitle = document.getElementById('resultsTitle');
        const resultsText = document.getElementById('resultsText');
        const modalContent = resultsModal.querySelector('.modal-content');
        const gameInfo = document.getElementById('gameInfo');
        const isLevelMode = gameInfo.dataset.level !== '';

        if (quizProgressBar) {
            quizProgressBar.style.width = '100%';
        }

        continueBtn.classList.add('hidden');
        tryAgainBtn.classList.add('hidden');
        modalContent.classList.remove('failure', 'level-up');
        
        try {
            const res = await fetch('/api/check-level-up', {
                method: 'POST',
                credentials: 'include'
            });
            const data = await res.json();

            if (data.success) {
                if (data.leveled_up) {
                    resultsTitle.textContent = 'Level Up!';
                    resultsText.textContent = data.message;
                    gameState.hintCount = data.new_hints;
                    updateHintDisplay();
                    modalContent.classList.add('level-up');
                    triggerConfetti();
                    document.getElementById('currentLevel').textContent = data.new_level;
                    continueBtn.classList.remove('hidden');
                } else if (isLevelMode) {
                    resultsTitle.textContent = 'Level Failed!';
                    resultsText.textContent = `You scored ${gameState.questScore}/${gameState.currentQuestions.length}. ${data.message || ''}`;
                    modalContent.classList.add('failure');
                    tryAgainBtn.classList.remove('hidden');
                    skipLevelBtn.classList.remove('hidden');
                    skipLevelBtn.disabled = (gameState.hintCount < 2);
                } else { // Classic mode
                    resultsTitle.textContent = 'Quest Complete!';
                    const percentage = (gameState.questScore / gameState.currentQuestions.length) * 100;
                    resultsText.textContent = `You scored ${gameState.questScore}/${gameState.currentQuestions.length} (${percentage.toFixed(1)}%).`;
                    continueBtn.classList.remove('hidden');
                }
            } else {
                resultsTitle.textContent = 'Quest Complete!';
                resultsText.textContent = `You scored ${gameState.questScore}/${gameState.currentQuestions.length}.`;
                continueBtn.classList.remove('hidden');
            }
        } catch (e) {
            resultsTitle.textContent = 'Quest Complete!';
            resultsText.textContent = `You scored ${gameState.questScore}/${gameState.currentQuestions.length}.`;
        }
        
        resultsModal.classList.remove('hidden');
        recordGameResult(); // Record the game result after it's finished
    }

    /**
     * Sends the result of the completed round to the server to be recorded.
     */
    async function recordGameResult() {
        const gameInfo = document.getElementById('gameInfo');
        const payload = {
            genre: gameInfo.dataset.genre,
            game_mode: gameInfo.dataset.level ? 'levels' : 'classic',
            score: gameState.questScore,
            total_questions: gameState.currentQuestions.length,
            level: gameInfo.dataset.level ? parseInt(gameInfo.dataset.level, 10) : null
        };

        try {
            await fetch('/api/record-game', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload)
            });
        } catch (error) {
            console.error('Could not record game result:', error);
        }
    }

    // --- Event Listeners ---
    nextBtn.addEventListener('click', () => {
        gameState.currentQuestionIndex++;
        showCurrentQuestion();
        message.textContent = '';
    });

    newQuestBtn.addEventListener('click', loadNewQuest);
    hintBtn.addEventListener('click', useHint);
    skipLevelBtn.addEventListener('click', skipLevel);
    skipStoryBtn.addEventListener('click', startQuiz);
    continueBtn.addEventListener('click', () => {
        resultsModal.classList.add('hidden');
        loadNewQuest();
    });
    tryAgainBtn.addEventListener('click', () => {
        resultsModal.classList.add('hidden');
        loadNewQuest();
    });

    /**
     * Updates the score display.
     */
    function updateScoreDisplay() {
        skipLevelBtn.classList.add('hidden');
        scoreBar.textContent = `Score: ${gameState.questScore} / ${gameState.totalAnswered}`;
        scoreBar.classList.add('pop');
        setTimeout(() => {
            scoreBar.classList.remove('pop');
        }, 400);
    }

    /**
     * Updates the hint display.
     */
    function updateHintDisplay() {
        hintCountSpan.textContent = gameState.hintCount;
        hintBtn.disabled = (gameState.hintCount <= 0);
    }

    /**
     * Shows a message to the user.
     * @param {string} text The message text.
     * @param {string} type The type of message (info, success, error).
     */
    function showMessage(text, type = 'info') {
        message.textContent = text;
        message.className = `arena-message ${type}`;
    }

    /**
     * Starts the reading timer.
     * @param {number} durationInSeconds The duration of the timer.
     */
    function startReadingTimer(durationInSeconds) {
        // Ensure timer is only for level mode
        const gameInfo = document.getElementById('gameInfo');
        if (gameInfo.dataset.level === '') return;

        const timerElement = document.getElementById('readingTimer');
        const timerText = document.getElementById('timerText');
        const progressBar = document.getElementById('timerProgressBar');
        if (!timerElement || !timerText || !progressBar) return;

        stopReadingTimer();
        timerElement.classList.add('active');
        
        let timeLeft = durationInSeconds;
        progressBar.style.transition = 'none';
        progressBar.style.width = '100%';
        void progressBar.offsetWidth;
        progressBar.style.transition = `width 1s linear`;

        readingTimerInterval = setInterval(() => {
            const minutes = Math.floor(timeLeft / 60).toString().padStart(2, '0');
            const seconds = (timeLeft % 60).toString().padStart(2, '0');
            timerText.textContent = `${minutes}:${seconds}`;
            progressBar.style.width = `${(timeLeft / durationInSeconds) * 100}%`;

            if (timeLeft <= 0) {
                showMessage('Time\'s up! Let the challenge begin!', 'warning');
                startQuiz();
            }
            timeLeft--;
        }, 1000);
    }

    /**
     * Stops the reading timer.
     */
    function stopReadingTimer() {
        const timerElement = document.getElementById('readingTimer');
        if (readingTimerInterval) {
            clearInterval(readingTimerInterval);
            readingTimerInterval = null;
            if (timerElement) timerElement.classList.remove('active');
        }
    }

    /**
     * Triggers a confetti animation for level-ups.
     */
    function triggerConfetti() {
        const container = document.getElementById('confettiContainer');
        if (!container) return;

        container.innerHTML = '';
        const confettiCount = 100;
        const colors = ['#f59e0b', '#10b981', '#6366f1', '#ec4899', '#3b82f6'];

        for (let i = 0; i < confettiCount; i++) {
            const confetti = document.createElement('div');
            confetti.classList.add('confetti');
            confetti.style.left = `${Math.random() * 100}%`;
            confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
            confetti.style.animationDelay = `${Math.random() * 2}s`;
            confetti.style.transform = `rotate(${Math.random() * 360}deg)`;
            container.appendChild(confetti);
        }

        setTimeout(() => {
            container.innerHTML = '';
        }, 4000);
    }

    /**
     * Uses a hint to reveal the correct answer.
     */
    async function useHint() {
        if (gameState.hintCount <= 0 || gameState.currentQuestionIndex >= gameState.currentQuestions.length) return;

        try {
            const response = await fetch('/api/use-hint', {
                method: 'POST',
                credentials: 'include'
            });
            const data = await response.json();

            if (data.success) {
                gameState.hintCount = data.hints_remaining;
                updateHintDisplay();
                showMessage('Hint used! The correct answer is revealed.', 'info');

                const question = gameState.currentQuestions[gameState.currentQuestionIndex];
                const allButtons = answerOptions.querySelectorAll('.option-btn');
                
                allButtons.forEach(btn => {
                    const key = btn.innerHTML.match(/<strong>(.*)\)<\/strong>/)[1];
                    if (key === question.correct) {
                        selectAnswer(key, btn);
                    }
                });

            } else {
                throw new Error(data.error || 'Failed to use hint.');
            }
        } catch (error) {
            showMessage(error.message, 'error');
        }
    }

    /**
     * Skips the current level using hints.
     */
    async function skipLevel() {
        try {
            const response = await fetch('/api/skip-level', {
                method: 'POST',
                credentials: 'include'
            });
            const data = await response.json();

            if (data.success) {
                showMessage(data.message, 'success');
                gameState.hintCount = data.hints_remaining;
                updateHintDisplay();
                document.getElementById('currentLevel').textContent = data.new_level;
                resultsModal.classList.add('hidden');
                loadNewQuest();
            } else {
                throw new Error(data.error || 'Failed to skip level.');
            }
        } catch (error) {
            showMessage(error.message, 'error');
        }
    }
});