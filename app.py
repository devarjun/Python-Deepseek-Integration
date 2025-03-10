from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Define the prefix to add to all queries
PREFIX = "You are to act as an **elite-level performance tester, performance engineer, Site Reliability Engineer (SRE), and non-functional testing specialist**. "

# Define symbols to remove from responses
SYMBOLS_TO_REMOVE = ['#', '*']

@app.route('/search', methods=['POST'])
def search():
    # Get the search query from the request
    data = request.json
    query = data.get('query', '')
    
    # Add the prefix to the query
    prefixed_query = PREFIX + query
    
    # Process the query using the DeepSeek API
    result = process_search_query(prefixed_query)
    
    # Filter out unwanted symbols from the result
    filtered_result = filter_symbols(result)
    
    # Return the results as JSON
    return jsonify({'results': [filtered_result]})

def filter_symbols(text):
    """
    Remove specified symbols from the text
    """
    for symbol in SYMBOLS_TO_REMOVE:
        text = text.replace(symbol, '')
    return text

def process_search_query(prompt):
    """
    Process the search query using DeepSeek API
    """
    try:
        # Initialize the OpenAI client with DeepSeek API details
        client = OpenAI(
            api_key = "sk-5a70c2ef041d4c1685056f2913a30891",
            base_url="https://api.deepseek.com"
        )

        # Make the API call
        response = client.chat.completions.create(
            model="deepseek-chat",  # Specify the DeepSeek model
            messages=[{"role": "user", "content": prompt}],
            stream = False,
            max_tokens= 2048,
            temperature= 1
        )

        # Extract the AI's response
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, port=5000)