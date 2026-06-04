import os
import numpy as np
import pandas as pd
import joblib
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

# Database connection
mydb = mysql.connector.connect(
    host='localhost',
    port=3306,
    user='root',
    passwd='',
    database='1crop_yield_prediction'
)

mycur = mydb.cursor()

def create_tables_if_not_exist():
    create_users_table = """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        address TEXT,
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    mycur.execute(create_users_table)
    mydb.commit()
    print("✅ Users table created/verified successfully")

create_tables_if_not_exist()

app = Flask(__name__)
app.secret_key = 'crop_yield_secret_key_2024'

# Initialize models and encoders
svm_model = None
scaler = None
label_encoders = {}

def load_models():
    """Load the trained model, scaler, and label encoders"""
    global svm_model, scaler, label_encoders
    
    try:
        print("🔄 Loading ML models and encoders...")
        
        # Load SVM model
        svm_model = joblib.load('crop_svm_model.pkl')
        print("✅ SVM model loaded successfully")
        
        # Load scaler (trained on 9 features)
        scaler = joblib.load('cropscaler.pkl')
        print("✅ Scaler loaded successfully")
        
        # Check scaler dimensions
        if hasattr(scaler, 'mean_'):
            print(f"✅ Scaler expects {scaler.mean_.shape[0]} features")
        
        # Load label encoders for 9 features
        categorical_columns = ['Region', 'Soil_Type', 'Crop', 'Weather_Condition', 'Fertilizer_Used', 'Irrigation_Used']
        
        for col in categorical_columns:
            encoder_file = f'{col}_label_encoder.pkl'
            if os.path.exists(encoder_file):
                label_encoders[col] = joblib.load(encoder_file)
                print(f"✅ {col} encoder loaded")
            else:
                print(f"⚠️ Warning: {encoder_file} not found")
        
        print("✅ All models and encoders loaded successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error loading models: {e}")
        return False

# Load models when app starts
print("🚀 Starting Crop Yield Prediction System...")
load_models()

# Feature descriptions for the form
feature_descriptions = {
    'Region': 'Geographic region of the farm (North, South, East, West)',
    'Soil_Type': 'Type of soil (Sandy, Clay, Loam, Silt, Peaty, Chalky)',
    'Crop': 'Type of crop to be cultivated',
    'Rainfall_mm': 'Expected rainfall in millimeters',
    'Temperature_Celsius': 'Average temperature in Celsius',
    'Fertilizer_Used': 'Whether fertilizer will be used (Yes/No)',
    'Irrigation_Used': 'Whether irrigation system will be used (Yes/No)',
    'Weather_Condition': 'Expected weather conditions during growing season',
    'Days_to_Harvest': 'Number of days from planting to expected harvest'
}

def get_yield_description(predicted_yield, crop_type):
    """Generate description based on predicted yield and crop type"""
    
    # Average yields for different crops (tons per hectare)
    avg_yields = {
        'Wheat': 3.5,
        'Rice': 4.5,
        'Maize': 5.0,
        'Cotton': 2.5,
        'Soybean': 2.8,
        'Barley': 3.0
    }
    
    # Get average for the specific crop, default to 3.0 if not found
    avg_for_crop = avg_yields.get(crop_type, 3.0)
    
    # Calculate percentage difference from average
    percent_diff = ((predicted_yield - avg_for_crop) / avg_for_crop) * 100
    
    if predicted_yield >= avg_for_crop * 1.3:
        category = "Excellent"
        color = "success"
        description = f"🎯 Exceptional yield prediction for {crop_type}! Perfect conditions for maximum productivity."
    elif predicted_yield >= avg_for_crop * 1.1:
        category = "Very Good"
        color = "info"
        description = f"✅ Above average yield prediction for {crop_type}. Good conditions for cultivation."
    elif predicted_yield >= avg_for_crop * 0.9:
        category = "Average"
        color = "warning"
        description = f"📊 Average yield prediction for {crop_type}. Consider optimizing inputs for better results."
    else:
        category = "Below Average"
        color = "danger"
        description = f"⚠️ Below average yield prediction for {crop_type}. Review soil conditions, inputs, and weather patterns."
    
    # Add recommendations based on yield
    if predicted_yield < avg_for_crop:
        description += "\n\n🔍 **Recommendations:**\n"
        description += "• Consider soil testing and nutrient management\n"
        description += "• Review irrigation practices\n"
        description += "• Check for pest/disease management\n"
        description += "• Consider crop rotation strategies"
    elif predicted_yield > avg_for_crop * 1.2:
        description += "\n\n🎯 **Optimal Conditions:**\n"
        description += "• Current conditions are excellent for this crop\n"
        description += "• Maintain current practices\n"
        description += "• Consider expanding cultivation area\n"
        description += "• Monitor for any seasonal changes"
    
    return {
        'category': category,
        'color': color,
        'description': description,
        'average_yield': avg_for_crop,
        'percent_difference': percent_diff
    }
# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('index.html')

@app.route('/registration', methods=['GET', 'POST'])
def registration():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirmpassword', '').strip()
        address = request.form.get('address', '').strip()

        if not all([name, email, password, confirm_password, address]):
            flash('All fields are required!', 'danger')
            return render_template('registration.html')

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('registration.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'danger')
            return render_template('registration.html')

        # Check if user already exists
        sql = 'SELECT * FROM users WHERE email = %s'
        val = (email,)
        mycur.execute(sql, val)
        data = mycur.fetchone()

        if data:
            flash('User already registered!', 'danger')
            return render_template('registration.html')
        else:
            hashed_password = generate_password_hash(password)
            sql = 'INSERT INTO users (name, email, password, address) VALUES (%s, %s, %s, %s)'
            val = (name, email, hashed_password, address)
            mycur.execute(sql, val)
            mydb.commit()
            flash('User registered successfully! Please login.', 'success')
            return redirect(url_for('login'))

    return render_template('registration.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Please enter both email and password!', 'danger')
            return render_template('login.html')

        sql = 'SELECT id, name, email, password, address FROM users WHERE email = %s'
        val = (email,)
        mycur.execute(sql, val)
        data = mycur.fetchone()

        if data:
            stored_password = data[3]
            if check_password_hash(stored_password, password):
                session['user_id'] = data[0]
                session['user_email'] = data[2]
                session['user_name'] = data[1]
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid email or password!', 'danger')
                return render_template('login.html')
        else:
            flash('User with this email does not exist. Please register.', 'danger')
            return redirect(url_for('registration'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('home.html', username=session.get('user_name'))

@app.route('/about')
def about():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('about.html')

@app.route('/model')
def model():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('model.html')

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if 'user_id' not in session:
        flash('Please login first.', 'danger')
        return redirect(url_for('login'))
    
    prediction_result = None
    yield_description = None
    
    # Available options for dropdowns
    region_options = ['North', 'South', 'East', 'West']
    soil_options = ['Sandy', 'Clay', 'Loam', 'Silt', 'Peaty', 'Chalky']
    crop_options = ['Wheat', 'Rice', 'Maize', 'Cotton', 'Soybean', 'Barley']
    weather_options = ['Sunny', 'Cloudy', 'Rainy']
    
    if request.method == 'POST':
        if svm_model is None or scaler is None:
            flash('Prediction model is not loaded properly. Please try again later.', 'danger')
            return render_template('predict.html',
                                 region_options=region_options,
                                 soil_options=soil_options,
                                 crop_options=crop_options,
                                 weather_options=weather_options,
                                 feature_descriptions=feature_descriptions)
        
        try:
            # Collect form data - ONLY 9 FEATURES
            region = request.form.get('Region')
            soil_type = request.form.get('Soil_Type')
            crop = request.form.get('Crop')
            rainfall = float(request.form.get('Rainfall_mm', 0))
            temperature = float(request.form.get('Temperature_Celsius', 0))
            fertilizer_used = request.form.get('Fertilizer_Used')
            irrigation_used = request.form.get('Irrigation_Used')
            weather_condition = request.form.get('Weather_Condition')
            days_to_harvest = int(request.form.get('Days_to_Harvest', 0))
            
            # Debug print
            print(f"\n=== DEBUG: Form Data Received ===")
            print(f"1. Region: {region}")
            print(f"2. Soil_Type: {soil_type}")
            print(f"3. Crop: {crop}")
            print(f"4. Rainfall_mm: {rainfall}")
            print(f"5. Temperature_Celsius: {temperature}")
            print(f"6. Fertilizer_Used: {fertilizer_used}")
            print(f"7. Irrigation_Used: {irrigation_used}")
            print(f"8. Weather_Condition: {weather_condition}")
            print(f"9. Days_to_Harvest: {days_to_harvest}")
            print("===============================\n")
            
            # Validate inputs
            if not all([region, soil_type, crop, weather_condition, fertilizer_used, irrigation_used]):
                flash('Please fill all required fields.', 'danger')
                return render_template('predict.html',
                                     region_options=region_options,
                                     soil_options=soil_options,
                                     crop_options=crop_options,
                                     weather_options=weather_options,
                                     feature_descriptions=feature_descriptions)
            
            # Prepare data for prediction - USE ONLY 9 FEATURES
            try:
                # Encode categorical variables
                region_encoded = label_encoders['Region'].transform([region])[0]
                soil_encoded = label_encoders['Soil_Type'].transform([soil_type])[0]
                crop_encoded = label_encoders['Crop'].transform([crop])[0]
                weather_encoded = label_encoders['Weather_Condition'].transform([weather_condition])[0]
                
                # Convert Yes/No to 1/0
                fertilizer_encoded = 1 if fertilizer_used == 'Yes' else 0
                irrigation_encoded = 1 if irrigation_used == 'Yes' else 0
                
                # IMPORTANT: Create input array with EXACTLY 9 features
                # The order MUST match the order your model was trained on
                # Based on your form, the order should be:
                # 1. Region, 2. Soil_Type, 3. Crop, 4. Rainfall, 5. Temperature,
                # 6. Fertilizer_Used, 7. Irrigation_Used, 8. Weather_Condition, 9. Days_to_Harvest
                
                input_data = np.array([[
                    region_encoded,
                    soil_encoded,
                    crop_encoded,
                    rainfall,
                    temperature,
                    fertilizer_encoded,
                    irrigation_encoded,
                    weather_encoded,
                    days_to_harvest
                ]])
                
                print(f"DEBUG: Input array shape: {input_data.shape}")
                print(f"DEBUG: Input array: {input_data}")
                
            except Exception as e:
                flash(f'Error encoding categorical variables: {str(e)}', 'danger')
                return render_template('predict.html',
                                     region_options=region_options,
                                     soil_options=soil_options,
                                     crop_options=crop_options,
                                     weather_options=weather_options,
                                     feature_descriptions=feature_descriptions)
            
            # Scale the input data
            input_scaled = scaler.transform(input_data)
            print(f"DEBUG: Scaled input shape: {input_scaled.shape}")
            
            # Make prediction
            predicted_yield = svm_model.predict(input_scaled)[0]
            print(f"DEBUG: Predicted yield: {predicted_yield}")
            
            # Get yield description
            yield_description = get_yield_description(predicted_yield, crop)
            
            # Prepare prediction result
            prediction_result = {
                'predicted_yield': round(predicted_yield, 6),
                'crop': crop,
                'region': region,
                'soil_type': soil_type,
                'weather_condition': weather_condition,
                'temperature': temperature,
                'rainfall': rainfall,
                'days_to_harvest': days_to_harvest,
                'fertilizer_used': 'Yes' if fertilizer_encoded == 1 else 'No',
                'irrigation_used': 'Yes' if irrigation_encoded == 1 else 'No',
                'yield_description': yield_description
            }
            
            flash('Crop yield prediction completed successfully!', 'success')
            
        except ValueError as e:
            flash(f'Invalid input values. Please check your inputs. Error: {str(e)}', 'danger')
            print(f"ERROR: ValueError - {str(e)}")
        except Exception as e:
            flash(f'An error occurred during prediction: {str(e)}', 'danger')
            print(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    return render_template('predict.html',
                         region_options=region_options,
                         soil_options=soil_options,
                         crop_options=crop_options,
                         weather_options=weather_options,
                         feature_descriptions=feature_descriptions,
                         prediction_result=prediction_result,
                         yield_description=yield_description)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)