import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64

class BookingPredictor:
    def __init__(self):
        self.model_path = 'instance/booking_predictor.joblib'
        self.scaler_path = 'instance/booking_scaler.joblib'
        self.model = None
        self.scaler = None
        
        # Try to load existing model
        if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
            self.load_model()
        else:
            # Initialize new model
            self.model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.scaler = StandardScaler()
    
    def load_model(self):
        """Load the trained model and scaler from disk"""
        try:
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False
    
    def save_model(self):
        """Save the trained model and scaler to disk"""
        try:
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            return True
        except Exception as e:
            print(f"Error saving model: {e}")
            return False
    
    def prepare_data(self, bookings):
        """Convert booking data to features for prediction"""
        if not bookings:
            return None, None
        
        # Convert bookings to DataFrame
        data = []
        for booking in bookings:
            booking_date = datetime.strptime(booking['date'], '%Y-%m-%d')
            booking_time = booking['time_slot'].split(' - ')[0]
            hour = int(booking_time.split(':')[0])
            
            # Extract features
            day_of_week = booking_date.weekday()
            month = booking_date.month
            day = booking_date.day
            
            data.append({
                'day_of_week': day_of_week,
                'month': month,
                'day': day,
                'hour': hour,
                'booking_count': 1  # Each row represents one booking
            })
        
        df = pd.DataFrame(data)
        
        # Aggregate by date and hour
        features_df = df.groupby(['day_of_week', 'month', 'day', 'hour']).sum().reset_index()
        
        X = features_df[['day_of_week', 'month', 'day', 'hour']]
        y = features_df['booking_count']
        
        return X, y
    
    def train(self, bookings):
        """Train the model with booking data"""
        X, y = self.prepare_data(bookings)
        if X is None or len(X) < 5:  # Need minimum data to train
            return False
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model.fit(X_scaled, y)
        
        # Save model
        self.save_model()
        return True
    
    def predict_future_bookings(self, days=14):
        """Predict bookings for the next N days"""
        if self.model is None:
            return None
        
        # Generate future dates
        future_dates = []
        today = datetime.now()
        
        # Create feature set for prediction
        future_X = []
        for i in range(days):
            future_date = today + timedelta(days=i)
            for hour in range(6, 23):  # 6 AM to 10 PM
                future_X.append([
                    future_date.weekday(),  # day of week
                    future_date.month,      # month
                    future_date.day,        # day
                    hour                    # hour
                ])
                future_dates.append(future_date.strftime('%Y-%m-%d') + f" {hour}:00")
        
        future_X = np.array(future_X)
        
        # Scale features
        future_X_scaled = self.scaler.transform(future_X)
        
        # Make predictions
        predictions = self.model.predict(future_X_scaled)
        
        # Round predictions and ensure non-negative
        predictions = np.round(predictions).astype(int)
        predictions = np.maximum(predictions, 0)
        
        # Create result dictionary
        result = {
            'dates': future_dates,
            'predictions': predictions.tolist()
        }
        
        return result
    
    def generate_heatmap(self, days=7):
        """Generate a heatmap of predicted bookings"""
        predictions = self.predict_future_bookings(days)
        if not predictions:
            return None
        
        # Reshape data for heatmap
        dates = [d.split(' ')[0] for d in predictions['dates']]
        hours = [int(d.split(' ')[1].split(':')[0]) for d in predictions['dates']]
        
        unique_dates = sorted(list(set(dates)))
        unique_hours = sorted(list(set(hours)))
        
        # Create matrix for heatmap
        heatmap_data = np.zeros((len(unique_hours), len(unique_dates)))
        
        for i, (date, hour, pred) in enumerate(zip(dates, hours, predictions['predictions'])):
            date_idx = unique_dates.index(date)
            hour_idx = unique_hours.index(hour)
            heatmap_data[hour_idx, date_idx] = pred
        
        # Generate plot
        plt.figure(figsize=(12, 8))
        sns.heatmap(heatmap_data, annot=True, fmt='d', cmap='YlGnBu',
                   xticklabels=[d.split('-')[2] + '/' + d.split('-')[1] for d in unique_dates],
                   yticklabels=[f"{h}:00" for h in unique_hours])
        plt.title('Predicted Booking Heatmap')
        plt.xlabel('Date')
        plt.ylabel('Hour')
        plt.tight_layout()
        
        # Convert plot to base64 for embedding in HTML
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        
        graphic = base64.b64encode(image_png).decode('utf-8')
        return graphic
    
    def get_popular_times(self):
        """Identify the most popular booking times"""
        predictions = self.predict_future_bookings()
        if not predictions:
            return None
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame({
            'date': predictions['dates'],
            'prediction': predictions['predictions']
        })
        
        # Extract day of week and hour
        df['date_obj'] = pd.to_datetime(df['date'].str.split(' ').str[0])
        df['hour'] = df['date'].str.split(' ').str[1].str.split(':').str[0].astype(int)
        df['day_of_week'] = df['date_obj'].dt.dayofweek
        
        # Get average bookings by day of week
        day_avg = df.groupby('day_of_week')['prediction'].mean().reset_index()
        day_avg = day_avg.sort_values('prediction', ascending=False)
        
        # Get average bookings by hour
        hour_avg = df.groupby('hour')['prediction'].mean().reset_index()
        hour_avg = hour_avg.sort_values('prediction', ascending=False)
        
        # Map day of week to name
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_avg['day_name'] = day_avg['day_of_week'].apply(lambda x: day_names[x])
        
        return {
            'popular_days': day_avg[['day_name', 'prediction']].head(3).to_dict('records'),
            'popular_hours': hour_avg[['hour', 'prediction']].head(3).to_dict('records')
        }

class RevenuePredictor:
    def __init__(self):
        self.model_path = 'instance/revenue_predictor.joblib'
        self.model = None
        
        # Try to load existing model
        if os.path.exists(self.model_path):
            self.load_model()
        else:
            # Initialize new model
            self.model = LinearRegression()
    
    def load_model(self):
        """Load the trained model from disk"""
        try:
            self.model = joblib.load(self.model_path)
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False
    
    def save_model(self):
        """Save the trained model to disk"""
        try:
            joblib.dump(self.model, self.model_path)
            return True
        except Exception as e:
            print(f"Error saving model: {e}")
            return False
    
    def prepare_data(self, bookings, booking_price=50):
        """Convert booking data to features for prediction"""
        if not bookings:
            return None, None
        
        # Convert bookings to DataFrame
        data = []
        for booking in bookings:
            booking_date = datetime.strptime(booking['date'], '%Y-%m-%d')
            
            # Extract features
            day_of_week = booking_date.weekday()
            month = booking_date.month
            
            data.append({
                'day_of_week': day_of_week,
                'month': month,
                'revenue': booking_price  # Each booking contributes to revenue
            })
        
        df = pd.DataFrame(data)
        
        # Aggregate by date
        df['date_key'] = df['month'].astype(str) + '_' + df['day_of_week'].astype(str)
        revenue_by_date = df.groupby('date_key').agg({
            'day_of_week': 'first',
            'month': 'first',
            'revenue': 'sum'
        }).reset_index()
        
        X = revenue_by_date[['day_of_week', 'month']]
        y = revenue_by_date['revenue']
        
        return X, y
    
    def train(self, bookings, booking_price=50):
        """Train the model with booking data"""
        X, y = self.prepare_data(bookings, booking_price)
        if X is None or len(X) < 5:  # Need minimum data to train
            return False
        
        # Train model
        self.model.fit(X, y)
        
        # Save model
        self.save_model()
        return True
    
    def predict_future_revenue(self, days=30, booking_price=50):
        """Predict revenue for the next N days"""
        if self.model is None:
            return None
        
        # Generate future dates
        future_dates = []
        future_X = []
        today = datetime.now()
        
        for i in range(days):
            future_date = today + timedelta(days=i)
            future_dates.append(future_date.strftime('%Y-%m-%d'))
            future_X.append([
                future_date.weekday(),  # day of week
                future_date.month       # month
            ])
        
        future_X = np.array(future_X)
        
        # Make predictions
        predictions = self.model.predict(future_X)
        
        # Ensure non-negative
        predictions = np.maximum(predictions, 0)
        
        # Create result dictionary
        result = {
            'dates': future_dates,
            'predictions': predictions.tolist()
        }
        
        return result
    
    def generate_revenue_chart(self, days=30, booking_price=50):
        """Generate a chart of predicted revenue"""
        predictions = self.predict_future_revenue(days, booking_price)
        if not predictions:
            return None
        
        # Generate plot
        plt.figure(figsize=(12, 6))
        plt.plot(range(len(predictions['dates'])), predictions['predictions'], marker='o')
        plt.title('Predicted Revenue for Next 30 Days')
        plt.xlabel('Days from Now')
        plt.ylabel('Predicted Revenue ($)')
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Add date labels for every 5th day
        tick_indices = range(0, len(predictions['dates']), 5)
        plt.xticks(tick_indices, [predictions['dates'][i] for i in tick_indices], rotation=45)
        
        plt.tight_layout()
        
        # Convert plot to base64 for embedding in HTML
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        
        graphic = base64.b64encode(image_png).decode('utf-8')
        return graphic
