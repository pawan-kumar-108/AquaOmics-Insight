import os
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from api import process_omics_data
import pandas as pd

app = Flask(__name__)
CORS(app)

# Ensure upload and result directories exist
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER

@app.route('/', methods=['GET'])
def index():
    """
    Provide information about available routes and tool capabilities
    """
    return jsonify({
        'tool_name': 'AquaOmics',
        'version': '1.0.0',
        'description': 'AI-powered multi-omics data analysis tool for aquatic organisms',
        'available_routes': {
            '/': {
                'method': 'GET',
                'description': 'Get information about available routes',
                'response_type': 'JSON'
            },
            '/upload': {
                'method': 'POST',
                'description': 'Upload omics data CSV file for analysis',
                'required_params': {
                    'file': 'CSV file containing omics data'
                },
                'expected_columns': ['Gene', 'Expression', 'Condition'],
                'accepted_file_types': ['.csv']
            },
            '/download-results': {
                'method': 'GET',
                'description': 'Download generated visualization results',
                'response_type': 'ZIP file'
            },

            '/view-results':{
                'method': 'GET',
                'description': 'Call GET /view-results to see list of generated images'
            },

            '/results/<filename>': {
                'method': 'GET',
                'description': 'Call GET /results/<filename> to view a specific image'
            }
        },
        'supported_data_types': [
            'Genomics',
            'Metabolomics',
            'Proteomics'
        ],
        'visualization_types': [
            'Heatmaps',
            'Volcano Plots',
            'Network Diagrams'
        ]
    }), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Handle file upload and initiate omics data processing
    """
    # Debugging: Print request details
    app.logger.info(f"Request method: {request.method}")
    app.logger.info(f"Request content type: {request.content_type}")
    app.logger.info(f"Request files: {request.files}")

    # Check if any files are present in the request
    if not request.files:
        return jsonify({
            'error': 'No file part in the request',
            'message': 'Please upload a CSV file containing omics data.'
        }), 400
    
    # Try multiple possible file keys
    file_keys = ['csv', 'file', 'uploaded_file']
    file = None
    
    for key in file_keys:
        if key in request.files:
            file = request.files[key]
            break
    
    # If no file found
    if file is None:
        return jsonify({
            'error': 'No file found',
            'message': f'Could not find file with keys: {file_keys}',
            'available_keys': list(request.files.keys())
        }), 400
    
    # Check if filename is empty
    if file.filename == '':
        return jsonify({
            'error': 'No file selected',
            'message': 'Please select a valid CSV file to upload.'
        }), 400
    
    # Check file extension
    if not file.filename.lower().endswith('.csv'):
        return jsonify({
            'error': 'Invalid file type',
            'message': 'Please upload a CSV file. Other file formats are not supported.'
        }), 400
    
    # Save uploaded file
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    # Validate CSV file content
    try:
        df = pd.read_csv(file_path)
        #### print(df)
        # Check if CSV is empty
        if df.empty:
            os.remove(file_path)  # Remove empty file
            return jsonify({
                'error': 'Empty file',
                'message': 'The uploaded CSV file is empty. Please upload a file with data.'
            }), 400
        
        # Basic validation - check if required columns exist
        required_columns = ['Gene', 'Expression', 'Condition']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            os.remove(file_path)  # Remove invalid file
            return jsonify({
                'error': "Invalid CSV structure. Please add these columns: 'Gene', 'Expression','Condition'",
                'message': f'Missing required columns: {", ".join(missing_columns)}. Please check your file.'
            }), 400
    
    except pd.errors.EmptyDataError:
        return jsonify({
            'error': 'File reading error',
            'message': 'Unable to read the CSV file. Please check the file format.'
        }), 400
    except Exception as e:
        return jsonify({
            'error': 'File processing error',
            'message': f'An error occurred while processing the file: {str(e)}'
        }), 500
    
    # Process the uploaded file
    try:
        results = process_omics_data(file_path)
        return jsonify(results), 200
    except Exception as e:
        return jsonify({
            'error': 'Data processing error',
            'message': str(e)
        }), 500

@app.route('/download-results', methods=['GET'])
def download_results():
    """
    Download all generated visualization results
    """
    try:
        # Create a zip file of all results
        import zipfile
        
        zip_path = os.path.join(app.config['RESULTS_FOLDER'], 'omics_results.zip')
        
        # Create zip file with all result images
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(app.config['RESULTS_FOLDER']):
                for file in files:
                    if file.endswith(('.png', '.svg', '.jpg')):
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, arcname=file)
        
        return send_file(zip_path, as_attachment=True)
    except Exception as e:
        return jsonify({
            'error': 'Download error',
            'message': str(e)
        }), 500


@app.route('/view-results', methods=['GET'])
def view_results():
    """
    List and view generated visualization results
    """
    try:
        results_folder = app.config['RESULTS_FOLDER']
        image_files = [f for f in os.listdir(results_folder) if f.endswith(('.png', '.svg', '.jpg'))]
        
        if not image_files:
            return jsonify({
                'message': 'No images generated yet',
                'status': 'empty'
            }), 404
        
        return jsonify({
            'images': image_files,
            'total_images': len(image_files)
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': 'Error listing results',
            'message': str(e)
        }), 500

@app.route('/results/<filename>')
def get_result_image(filename):
    """
    Serve a specific result image
    """
    try:
        return send_file(os.path.join(app.config['RESULTS_FOLDER'], filename))
    except FileNotFoundError:
        return jsonify({
            'error': 'Image not found',
            'message': f'Image {filename} does not exist'
        }), 404
    



#adding error handlers for common HTTP errors
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested route does not exist.',
        'available_routes': [
            '/',
            '/upload',
            '/download-results'
            '/view-results'
            '/results/{filename}'
        ]
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'error': 'Method Not Allowed',
        'message': 'The method is not allowed for the requested route.'
    }), 405

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
