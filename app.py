"""
Flask Web Application for AI Story Quiz Game
This application serves the web interface for the quiz game,
handles user authentication, game sessions, and communication with the game logic.
"""
from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for
import json
import random
from typing import Dict, List, Optional
import time
import secrets
import logging
import sys
from flask_mysqldb import MySQL, MySQLdb
import hashlib
import re
import os  # Import the os library
from dotenv import load_dotenv  # Import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import the game classes from game.py
from game import OllamaStoryQuizGame, OllamaStoryQuizGameWithLevels

# Configure logging to output information to the console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Secret key for session management
app.config['DEBUG'] = True

# MySQL configurations - securely loaded from environment variables
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB')


# Initialize MySQL
mysql = MySQL(app)

# Global dictionary to store active game instances
games = {}

# --- ALL OTHER FUNCTIONS REMAIN THE SAME ---
@app.context_processor
def inject_version():
    """Injects a version number into templates to prevent browser caching of static files."""
    return dict(version=int(time.time()))

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler to catch and log any unhandled errors."""
    error_id = secrets.token_hex(4)
    logger.error(f"ERROR [{error_id}]: {str(e)}")
    return jsonify({
        'success': False,
        'error': f"Server error [{error_id}]: {str(e)}",
        'error_id': error_id
    }), 500

@app.route('/')
def index():
    """Serves the home page, which is the login/register page or the game start page."""
    return render_template('index.html') # This template now handles both logged-in and out states

@app.route('/login', methods=['POST'])
def login():
    """Handles user login."""
    if 'username' in request.form and 'password' in request.form:
        username = request.form['username']

        try:
            # RECTIFIED: Added a check to ensure the database connection is alive.
            if not mysql or not hasattr(mysql, 'connection') or not mysql.connection:
                logger.error("Database connection not available during login.")
                return render_template('index.html', msg='Error: Could not connect to the database.')

            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor) # type: ignore
            cursor.execute('SELECT * FROM accounts WHERE username = %s', (username,))
            account = cursor.fetchone()

            if account:
                # Create session data upon successful login
                session['loggedin'] = True
                session['id'] = account['id']
                session['username'] = account['username']
                return redirect(url_for('index'))
            elif re.match(r'^[A-Za-z0-9_]+$', username):
                # If account doesn't exist, create a new one (no password/email)
                # Initialize stats for the new user.
                cursor.execute('INSERT INTO accounts (username, password, email, total_questions_answered, total_correct_answers) VALUES (%s, %s, %s, 0, 0)', (username, '', ''))
                mysql.connection.commit()
                
                # Log the new user in
                cursor.execute('SELECT * FROM accounts WHERE username = %s', (username,))
                new_account = cursor.fetchone()
                session['loggedin'] = True
                session['id'] = new_account['id'] # type: ignore
                session['username'] = new_account['username'] # type: ignore
                return redirect(url_for('index'))
            else:
                return render_template('index.html', msg='Username must contain only letters, numbers, and underscores!')
        except MySQLdb.OperationalError as e:
            logger.error(f"Database connection error: {e}")
            return render_template('index.html', msg='Error: Could not connect to the database. Please ensure the MySQL server (e.g., in XAMPP) is running and the credentials in your .env file are correct.')
        except Exception as e:
            logger.error(f"Database error during login: {e}")
            return render_template('index.html', msg=f'An unexpected database error occurred: {e}')
            
    return render_template('index.html', msg='Please fill out the form!')


@app.route('/logout')
def logout():
    """Logs the user out by clearing the session."""
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/leaderboard')
def leaderboard():
    """Serves the leaderboard page, showing top players."""
    if 'loggedin' not in session:
        return redirect(url_for('index'))

    try:
        # RECTIFIED: Added a check to ensure the database connection is alive.
        if not mysql or not hasattr(mysql, 'connection') or not mysql.connection:
            logger.error("Database connection not available for leaderboard.")
            return render_template('error.html', error="Database connection is currently unavailable.")

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor) # type: ignore
        # This query finds the maximum level for each user and joins with the accounts table
        # to get their username, then orders them to find the top 10.
        query = """
            SELECT
                a.username,
                MAX(up.level) AS highest_level
            FROM
                user_progress up
            JOIN
                accounts a ON up.user_id = a.id
            GROUP BY
                up.user_id, a.username
            ORDER BY
                highest_level DESC
            LIMIT 10;
        """
        cursor.execute(query)
        leaderboard_data = cursor.fetchall()
        return render_template('leaderboard.html', leaderboard_data=leaderboard_data)
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        return render_template('error.html', error="Could not fetch the leaderboard data.")

@app.route('/profile')
def profile():
    """Serves the user's profile page with their stats."""
    if 'loggedin' not in session:
        return redirect(url_for('index'))

    try:
        # RECTIFIED: Added a check to ensure the database connection is alive.
        if not mysql or not hasattr(mysql, 'connection') or not mysql.connection:
            logger.error("Database connection not available for profile page.")
            return render_template('error.html', error="Database connection is currently unavailable.")

        user_id = session['id']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor) # type: ignore

        # Get highest level from user_progress
        cursor.execute('SELECT MAX(level) AS highest_level FROM user_progress WHERE user_id = %s', (user_id,))
        progress = cursor.fetchone()
        highest_level = progress['highest_level'] if progress and progress['highest_level'] is not None else 0

        # Get total questions and correct answers from accounts
        cursor.execute('SELECT total_questions_answered, total_correct_answers FROM accounts WHERE id = %s', (user_id,))
        account_stats = cursor.fetchone()

        stats = {
            'username': session['username'],
            'highest_level': highest_level,
            'total_questions_answered': account_stats['total_questions_answered'] if account_stats else 0,
            'total_correct_answers': account_stats['total_correct_answers'] if account_stats else 0,
        }

        # Calculate accuracy
        if stats['total_questions_answered'] > 0:
            stats['accuracy'] = round((stats['total_correct_answers'] / stats['total_questions_answered']) * 100, 1)
        else:
            stats['accuracy'] = 0

        # Get last 5 games from game_history
        cursor.execute("""
            SELECT genre, game_mode, score, total_questions, level, played_at
            FROM game_history
            WHERE user_id = %s
            ORDER BY played_at DESC
            LIMIT 5
        """, (user_id,))
        game_history = cursor.fetchall()

        # Format the game history for display
        formatted_history = []
        for game in game_history:
            game['score_text'] = f"{game['score']}/{game['total_questions']}"
            game['mode_text'] = "Progressive" if game['game_mode'] == 'levels' else "Classic"
            game['played_date'] = game['played_at'].strftime('%b %d, %Y')
            formatted_history.append(game)

        return render_template('profile.html',
                               stats=stats,
                               game_history=formatted_history)
    except Exception as e:
        logger.error(f"Error fetching profile data: {e}")
        return render_template('error.html', error="Could not fetch your profile data.")

@app.route('/api/start-game', methods=['POST'])
def start_game():
    """API endpoint to start a new game session."""
    if 'loggedin' not in session:
        return jsonify({'success': False, 'error': 'User not logged in'}), 401
    try:
        logger.info("Starting new game session")
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        genre = data.get('genre', 'adventure')
        game_mode = data.get('game_mode', 'classic')
        
        # Generate a unique session ID for this game instance
        session_id = secrets.token_hex(8)
        session['session_id'] = session_id

        user_id = session['id']
        level = 1
        if game_mode != 'classic':
            # Fetch the user's progress if in advanced mode
            if not mysql or not hasattr(mysql, 'connection') or not mysql.connection:
                logger.error("DB connection failed when starting a 'levels' game.")
                return jsonify({'success': False, 'error': 'Database connection is currently unavailable.'}), 503
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT level FROM user_progress WHERE user_id = %s ORDER BY level DESC LIMIT 1', (user_id,))
            progress = cursor.fetchone()
            if progress:
                level = progress['level'] + 1
        
        # Create the appropriate game instance based on the selected mode
        if game_mode == 'classic':
            game = OllamaStoryQuizGame("gemma:2b", genre=genre)
        else:
            game = OllamaStoryQuizGameWithLevels("gemma:2b", genre=genre, start_level=level)
        
        # Store the game instance in the global dictionary
        games[session_id] = game
        
        # Check the connection to Ollama before starting the game
        ollama_connected = game.check_ollama_connection()
        logger.info(f"Ollama connection: {ollama_connected}")

        if not ollama_connected:
            logger.error("Ollama connection failed. Cannot start game.")
            del games[session_id]  # Clean up the created game instance
            return jsonify({'success': False, 'error': 'Cannot connect to the AI service (Ollama). Please ensure it is running.'}), 503
        
        game_url = url_for('game_page', session_id=session_id, _external=True)

        return jsonify({
            'success': True,
            'session_id': session_id,
            'genre': genre,
            'game_mode': game_mode,
            'game_url': game_url,
            'hints': getattr(game, 'hints', 0),
            'message': 'Game started!'
        })
        
    except Exception as e:
        logger.error(f"Error starting game: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/new-round', methods=['POST'])
def new_round():
    """API endpoint to generate a new story and quiz for a round."""
    try:
        session_id = session.get('session_id')
        logger.info(f"New round for session: {session_id}")
        
        if not session_id or session_id not in games:
            return jsonify({'success': False, 'error': 'No active game session'}), 400
        
        game = games[session_id]
        
        # Generate the story
        story = game.generate_story()
        
        if not story:
            logger.error("Failed to generate story")
            return jsonify({'success': False, 'error': 'Failed to generate story'}), 500
        
        # Generate quiz questions based on the story
        questions = game.generate_quiz_questions(story)
        
        if not questions:
            logger.error("Failed to generate questions")
            return jsonify({'success': False, 'error': 'Failed to generate questions'}), 500
        
        return jsonify({
            'success': True,
            'story': story,
            'questions': questions,
            'word_count': len(story.split()),
            'ollama_connected': game.check_ollama_connection()
        })
        
    except Exception as e:
        logger.error(f"Error in new round: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-story-stream', methods=['POST'])
def generate_story_stream():
    """API endpoint to stream a newly generated story to the client."""
    try:
        session_id = session.get('session_id')
        if not session_id or session_id not in games:
            return jsonify({'success': False, 'error': 'No active game session'}), 400
        
        game = games[session_id]
        word_count = getattr(game, 'story_word_limit', 150)
        prompt = f"Write a complete story of about {word_count} words in the '{game.genre}' genre."
        
        # Return a streaming response
        return Response(game.generate_story_stream(prompt, word_count + 100), mimetype='text/plain')

    except Exception as e:
        logger.error(f"Error in story stream: {str(e)}")
        return Response(f"Error generating story: {str(e)}", status=500, mimetype='text/plain')

@app.route('/api/generate-story', methods=['POST'])
def generate_story():
    """API endpoint to generate just a story."""
    try:
        session_id = session.get('session_id')
        
        if not session_id or session_id not in games:
            return jsonify({'success': False, 'error': 'No active game session'}), 400
        
        game = games[session_id]
        story = game.generate_story()
        
        return jsonify({
            'success': True,
            'story': story,
            'word_count': len(story.split()),
        })
        
    except Exception as e:
        logger.error(f"Error generating story: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-quiz', methods=['POST'])
def generate_quiz():
    """API endpoint to generate quiz questions for a given story."""
    try:
        session_id = session.get('session_id')
        
        if not session_id or session_id not in games:
            return jsonify({'success': False, 'error': 'No active game session'}), 400
        
        data = request.get_json()
        story = data.get('story', '') if data else ''
        
        if not story:
            return jsonify({'success': False, 'error': 'No story provided'}), 400
        
        game = games[session_id]
        questions = game.generate_quiz_questions(story)
        
        return jsonify({
            'success': True,
            'questions': questions,
        })
        
    except Exception as e:
        logger.error(f"Error generating quiz: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/submit-answer', methods=['POST'])
def submit_answer():
    """API endpoint to submit an answer and update the score."""
    try:
        session_id = session.get('session_id')
        
        if not session_id or session_id not in games:
            return jsonify({'success': False, 'error': 'No active game session'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        game = games[session_id]
        is_correct = data.get('is_correct', False)
        user_id = session['id']
        
        # RECTIFIED: Added a check to ensure the database connection is alive.
        if not mysql or not hasattr(mysql, 'connection') or not mysql.connection:
            logger.error("Database connection not available for submitting answer.")
            return jsonify({'success': False, 'error': 'Database connection is currently unavailable.'}), 503

        cursor = mysql.connection.cursor()
        # Update scores
        if is_correct:
            game.score += 1
            if isinstance(game, OllamaStoryQuizGameWithLevels):
                game.level_score += 1
            # Update total correct answers in the database
            cursor.execute('UPDATE accounts SET total_correct_answers = total_correct_answers + 1 WHERE id = %s', (user_id,))

        # Update total questions answered in the database
        cursor.execute('UPDATE accounts SET total_questions_answered = total_questions_answered + 1 WHERE id = %s', (user_id,))
        mysql.connection.commit()
        
        game.questions_answered += 1
        
        return jsonify({
            'success': True,
            'score': game.score,
            'questions_answered': game.questions_answered,
            'level': getattr(game, 'level', None),
            'level_score': getattr(game, 'level_score', None)
        })
        
    except Exception as e:
        logger.error(f"Error processing answer: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-score', methods=['GET'])
def get_score():
    """API endpoint to get the current game score and statistics."""
    try:
        session_id = session.get('session_id')
        
        if not session_id or session_id not in games:
            return jsonify({'success': False, 'error': 'No active game session'}), 400
        
        game = games[session_id]
        accuracy = (game.score / game.questions_answered) * 100 if game.questions_answered > 0 else 0
        
        return jsonify({
            'success': True,
            'score': game.score,
            'level': getattr(game, 'level', None),
            'level_score': getattr(game, 'level_score', None),
            'questions_answered': game.questions_answered,
            'accuracy': round(accuracy, 1)
        })
        
    except Exception as e:
        logger.error(f"Error getting score: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check-level-up', methods=['POST'])
def check_level_up():
    """API endpoint to check if the player should level up in advanced mode."""
    if 'loggedin' not in session:
        return jsonify({'success': False, 'error': 'User not logged in'}), 401
    try:
        session_id = session.get('session_id')
        
        if not session_id or session_id not in games:
            return jsonify({'success': False, 'error': 'No active game session'}), 400
        
        game = games[session_id]
        
        if not isinstance(game, OllamaStoryQuizGameWithLevels):
            return jsonify({'success': True, 'leveled_up': False})
        
        leveled_up = False
        message = ""
        hint_awarded = False
        previous_level = game.level
        
        # Level up if the player answers at least 2 questions correctly
        if game.level_score >= 2:
            leveled_up = True
            user_id = session['id']

            # Save progress to the database
            if not mysql or not hasattr(mysql, 'connection') or not mysql.connection:
                logger.error("DB connection failed during level-up check.")
                return jsonify({'success': False, 'error': 'Database connection is currently unavailable.'}), 503

            cursor = mysql.connection.cursor()
            cursor.execute('INSERT INTO user_progress (user_id, level) VALUES (%s, %s)', (user_id, previous_level))
            mysql.connection.commit()
            
            hint_awarded = game.advance_level()
            message = f"🎉 LEVEL UP! Welcome to Level {game.level}!"
            if hint_awarded: message += " You earned a new hint!"
            logger.info(f"Player advanced from level {previous_level} to {game.level}")
        else:
            remaining = 2 - game.level_score
            message = f"Need {remaining} more correct answer(s) to advance to the next level."
        
        return jsonify({
            'success': True,
            'leveled_up': leveled_up,
            'message': message,
            'hint_awarded': hint_awarded,
            'new_level': game.level,
            'new_hints': game.hints,
            'level_score': game.level_score,
            'story_word_limit': getattr(game, 'story_word_limit', None),
            'questions_per_round': getattr(game, 'num_questions_per_round', 3)
        })
        
    except Exception as e:
        logger.error(f"Error checking level-up: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/use-hint', methods=['POST'])
def use_hint():
    """API endpoint to use a hint."""
    try:
        session_id = session.get('session_id')
        if not session_id or session_id not in games:
            return jsonify({'success': False, 'error': 'No active game session'}), 400
        
        game = games[session_id]
        
        if hasattr(game, 'hints') and game.hints > 0:
            game.hints -= 1
            return jsonify({
                'success': True,
                'hints_remaining': game.hints
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'No hints remaining!'
            })
        
    except Exception as e:
        logger.error(f"Error using hint: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/skip-level', methods=['POST'])
def skip_level():
    """API endpoint to skip the current level using hints."""
    try:
        session_id = session.get('session_id')
        if not session_id or session_id not in games:
            return jsonify({'success': False, 'error': 'No active game session'}), 400
        
        game = games[session_id]
        
        if not isinstance(game, OllamaStoryQuizGameWithLevels):
            return jsonify({'success': False, 'error': 'Skip level is only available in Progressive Challenge mode.'}), 400
        
        if game.hints >= 2:
            game.hints -= 2
            hint_awarded_on_skip = game.advance_level()
            
            message = f"Level skipped! Welcome to Level {game.level}."
            if hint_awarded_on_skip:
                message += " You earned 1 hint back!"

            return jsonify({
                'success': True,
                'message': message,
                'new_level': game.level,
                'hints_remaining': game.hints
            })
        else:
            return jsonify({'success': False, 'error': 'Not enough hints to skip level! (Requires 2)'}), 400

    except Exception as e:
        logger.error(f"Error skipping level: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/record-game', methods=['POST'])
def record_game():
    """API endpoint to record the result of a completed game round."""
    if 'loggedin' not in session or 'id' not in session:
        return jsonify({'success': False, 'error': 'User not logged in'}), 401

    try:
        # RECTIFIED: Added a check to ensure the database connection is alive.
        if not mysql or not hasattr(mysql, 'connection') or not mysql.connection:
            logger.error("Database connection not available for recording game.")
            return jsonify({'success': False, 'error': 'Database connection is currently unavailable.'}), 503

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        user_id = session['id']
        genre = data.get('genre')
        game_mode = data.get('game_mode')
        score = data.get('score')
        total_questions = data.get('total_questions')
        level = data.get('level') # This will be None for classic mode

        if not all([genre, game_mode, score is not None, total_questions is not None]):
            return jsonify({'success': False, 'error': 'Missing required game data'}), 400

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO game_history (user_id, genre, game_mode, score, total_questions, level)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, genre, game_mode, score, total_questions, level))
        mysql.connection.commit()

        return jsonify({'success': True, 'message': 'Game recorded.'})
    except Exception as e:
        logger.error(f"Error recording game: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reset-game', methods=['POST'])
def reset_game():
    """API endpoint to reset the current game state."""
    try:
        session_id = session.get('session_id')
        
        if session_id and session_id in games:
            game = games[session_id]
            
            # Reset game state to initial values
            game.score = 0
            game.questions_answered = 0
            game.used_stories.clear()
            
            if hasattr(game, 'level'):
                game.level = 1
                game.level_score = 0
                game.story_word_limit = 100
                game.num_questions_per_round = 3
        
        return jsonify({
            'success': True,
            'message': 'Game reset!'
        })
        
    except Exception as e:
        logger.error(f"Error resetting game: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/game')
@app.route('/game/<session_id>')
def game_page(session_id=None):
    """Serves the main game interface page."""
    if 'loggedin' not in session:
        return redirect(url_for('index'))

    session['session_id'] = session_id # Ensure session is aware of the ID from the URL
    
    if not session_id or session_id not in games:
        return render_template('error.html', 
                             error="No active game session. Please start a new game.")
    
    game = games[session_id]
    
    return render_template('game.html', game=game)

@app.route('/api/health', methods=['GET'])
def health_check():
    """A simple health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'active_sessions': len(games),
    })

@app.route('/debug-questions')
def debug_questions():
    """A debug endpoint to test the question generation logic."""
    if not app.config['DEBUG']:
        return jsonify({'error': 'Debug mode disabled'}), 403
    
    test_game = OllamaStoryQuizGame()
    test_story = "Alice found a mysterious golden key in her grandmother's garden. She used it to open an old wooden chest buried under the rose bush. Inside, she discovered a map leading to a hidden treasure cave in the nearby mountains."
    elements = test_game.extract_story_elements(test_story)
    questions = test_game.generate_unique_questions(test_story, elements)
    
    return jsonify({
        'test_story': test_story,
        'extracted_elements': elements,
        'unique_questions': questions,
        'question_count': len(questions)
    })

if __name__ == '__main__':
    logger.info("🚀 Starting Flask app!")
    app.run(debug=True, host='0.0.0.0', port=5000)