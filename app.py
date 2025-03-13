from flask import Flask, request, jsonify, session
from flask_cors import CORS
from openai import OpenAI
import uuid
import json
import time
import sqlite3
import os
import random

app = Flask(__name__)
app.secret_key = "1234567890"  # Needed for session management
CORS(app, supports_credentials=True)  # Enable CORS with credentials

# SQLite database file
DB_FILE = "conversations.db"

# Define the prefix to add to all queries
PREFIX = "You are to act as an **elite-level performance tester, performance engineer, Site Reliability Engineer (SRE), and non-functional testing specialist**. "

# Define symbols to remove from responses
SYMBOLS_TO_REMOVE = ['#', '*']

def get_db_connection():
    """Create a connection to the SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def init_db():
    """Initialize the database with the required tables"""
    if not os.path.exists(DB_FILE):
        conn = get_db_connection()
        conn.execute('''
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            messages TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
        ''')
        conn.commit()
        conn.close()

# Initialize the database
init_db()

@app.route('/search', methods=['POST'])
def search():
    # Get the search query and conversation ID from the request
    data = request.json
    query = data.get('query', '')
    conversation_id = data.get('conversationId', None)
    
    conn = get_db_connection()
    
    # Check if this is a new conversation or continuing an existing one
    if not conversation_id:
        # Create a new conversation ID
        conversation_id = str(uuid.uuid4())
        prefixed_query = PREFIX + query
        messages = [{"role": "user", "content": prefixed_query}]
        is_cache_hit = False
    else:
        # Get existing conversation from SQLite
        cursor = conn.execute(
            "SELECT messages FROM conversations WHERE id = ? AND expires_at > datetime('now')",
            (conversation_id,)
        )
        row = cursor.fetchone()
        
        if row:
            messages = json.loads(row['messages'])
            # Add the new query to the existing conversation
            messages.append({"role": "user", "content": query})
            is_cache_hit = True
        else:
            # Fallback if conversation doesn't exist or has expired
            conversation_id = str(uuid.uuid4())
            prefixed_query = PREFIX + query
            messages = [{"role": "user", "content": prefixed_query}]
            is_cache_hit = False
    
    # Process using the DeepSeek API
    start_time = time.time()
    result, response_time = process_search_query(messages)
    
    # Add the response to the conversation history
    messages.append({"role": "assistant", "content": result})
    
    # Store the updated conversation in SQLite (with 24 hour expiry)
    expires_at = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + 86400))
    
    conn.execute(
        """
        INSERT OR REPLACE INTO conversations (id, messages, expires_at)
        VALUES (?, ?, ?)
        """,
        (conversation_id, json.dumps(messages), expires_at)
    )
    conn.commit()
    conn.close()
    
    # Filter out unwanted symbols from the result
    filtered_result = filter_symbols(result)
    
    # Return the results as JSON
    return jsonify({
        'results': [filtered_result],
        'conversationId': conversation_id,
        'cache_status': 'hit' if is_cache_hit else 'miss',
        'responseTime': response_time,
        'conversationHistory': [m for m in messages if m["role"] != "system"]  # Return conversation history for display
    })

@app.route('/new-conversation', methods=['GET'])
def new_conversation():
    # Generate a new conversation ID
    conversation_id = str(uuid.uuid4())
    return jsonify({'conversationId': conversation_id})

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    data = request.json
    conversation_id = data.get('conversationId', None)
    conn = get_db_connection()
    
    if conversation_id:
        # Clear specific conversation from database
        cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'message': f'Cleared conversation cache for ID: {conversation_id}',
            'deleted': deleted > 0
        })
    else:
        # Clear all conversations
        cursor = conn.execute("DELETE FROM conversations")
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'message': f'Cleared all conversation caches ({deleted} conversations)'
        })

def filter_symbols(text):
    """
    Remove specified symbols from the text
    """
    for symbol in SYMBOLS_TO_REMOVE:
        text = text.replace(symbol, '')
    return text

def process_search_query(messages):
    """
    Process the search query using DeepSeek API
    """
    start_time = time.time()
    
    try:
        # Initialize the OpenAI client with DeepSeek API details
        client = OpenAI(
            api_key = "sk-5a70c2ef041d4c1685056f2913a30891",
            base_url="https://api.deepseek.com"
        )

        # Make the API call
        response = client.chat.completions.create(
            model="deepseek-chat",  # Specify the DeepSeek model
            messages=messages,
            stream = False,
            max_tokens= 2048,
            temperature= 1
        )

        # Extract the AI's response
        result = response.choices[0].message.content
        total_time = time.time() - start_time
        return result, total_time
    except Exception as e:
        total_time = time.time() - start_time
        return f"Error: {str(e)}", total_time

# Add database cleanup task to remove expired conversations
@app.before_request
def cleanup_expired_conversations():
    # Only run occasionally to avoid doing this on every request
    if random.random() < 0.05:  # 5% chance to run on any request
        conn = get_db_connection()
        conn.execute("DELETE FROM conversations WHERE expires_at < datetime('now')")
        conn.commit()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
