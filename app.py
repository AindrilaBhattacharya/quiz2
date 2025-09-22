from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import pyodbc
import os
from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'supersecret'  # for flash messages

# Load environment variables
load_dotenv()
password = os.getenv('SQL_PASSWORD')

# SQL Server configuration
server = 'tcp:cse6332server.database.windows.net'
database = 'cse6332db'
username = 'aindrilab@cse6332server'
driver = '{ODBC Driver 18 for SQL Server}'

# SQL connection
def get_connection():
    return pyodbc.connect(
        f'DRIVER={driver};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password};'
        f'Encrypt=yes;'
        f'TrustServerCertificate=no;'
        f'Connection Timeout=30;'
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/insert', methods=['GET', 'POST'])
def insert():
    if request.method == 'POST':
        quake_id = request.form['id']
        time_val = request.form['time']
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        depth = request.form['depth']
        mag = request.form['mag']
        place = request.form['place']

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Earthquakes (id, time, latitude, longitude, depth, mag, place)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, quake_id, time_val, latitude, longitude, depth, mag, place)
        conn.commit()
        cursor.close()
        conn.close()
        flash('Earthquake record inserted successfully!')
        return redirect(url_for('index'))
    return render_template('insert.html')

# how to find within 500 km of Arlington, TX in the database querying:
# DECLARE @lat FLOAT = 32.7357;   -- Arlington latitude
# DECLARE @lon FLOAT = -97.1081;  -- Arlington longitude
# DECLARE @radius FLOAT = 500;    -- km

# SELECT id, time, latitude, longitude, depth, mag, place,
#        6371 * ACOS(
#            COS(RADIANS(@lat)) * COS(RADIANS(latitude)) *
#            COS(RADIANS(longitude) - RADIANS(@lon)) +
#            SIN(RADIANS(@lat)) * SIN(RADIANS(latitude))
#        ) AS distance_km
# FROM Earthquakes
# WHERE 6371 * ACOS(
#            COS(RADIANS(@lat)) * COS(RADIANS(latitude)) *
#            COS(RADIANS(longitude) - RADIANS(@lon)) +
#            SIN(RADIANS(@lat)) * SIN(RADIANS(latitude))
#        ) <= @radius;  

@app.route('/query', methods=['GET', 'POST'])
def query():
    if request.method == 'POST':
        query_type = request.form.get('query_type')
        conn = get_connection()
        if query_type == 'magnitude':
            min_mag = request.form.get('min_mag', 0)
            max_mag = request.form.get('max_mag', 10)

            query = """
                    SELECT id, time, latitude, longitude, depth, mag, place
                    FROM Earthquakes
                    WHERE mag BETWEEN ? AND ?
                    ORDER BY time DESC
                """
            df = pd.read_sql(query, conn, params=[min_mag, max_mag])
            

        elif query_type == 'location':
            center_lat = float(request.form.get('latitude'))
            center_lon = float(request.form.get('longitude'))
            radius_km = float(request.form.get('radius_km', 500))

            sql = """
                SELECT id, time, latitude, longitude, depth, mag, place,
                       6371 * ACOS(
                           COS(RADIANS(?)) * COS(RADIANS(latitude)) *
                           COS(RADIANS(longitude) - RADIANS(?)) +
                           SIN(RADIANS(?)) * SIN(RADIANS(latitude))
                       ) AS distance_km
                FROM Earthquakes
                WHERE 6371 * ACOS(
                           COS(RADIANS(?)) * COS(RADIANS(latitude)) *
                           COS(RADIANS(longitude) - RADIANS(?)) +
                           SIN(RADIANS(?)) * SIN(RADIANS(latitude))
                       ) <= ?
                ORDER BY time DESC
            """
            params = [center_lat, center_lon, center_lat,
                      center_lat, center_lon, center_lat, radius_km]
            df = pd.read_sql(sql, conn, params=params)

        conn.close()
        # Remove leading/trailing whitespace characters from string columns
        html_table = df.to_html(classes='table table-striped', index=False).replace('\n', '')
        return render_template('results.html', tables=[html_table], titles=df.columns.values)

    return render_template('query.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.csv'):
            file_path = os.path.join('static', 'uploads', file.filename)
            file.save(file_path)

            df_cleaned = pd.read_csv(file_path, skip_blank_lines=True)

            conn = get_connection()
            cursor = conn.cursor()
            for index, row in df_cleaned.iterrows():
                cursor.execute("""
                    INSERT INTO Earthquakes2 (id, time, latitude, longitude, mag, nst, net)
                    SELECT ?, ?, ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (SELECT 1 FROM Earthquakes2 WHERE id = ?)
                """,
                    row['id'],row['time'], row['lat'], row['long'],
                    row['mag'], row['nst'], row['net'], row['id']
                )
            conn.commit()
            cursor.close()
            conn.close()
            flash('CSV data uploaded successfully (skipped blank lines and ignored duplicates)!')
            return redirect(url_for('index'))
        else:
            flash('Please upload a valid CSV file.')
            return redirect(url_for('upload'))
    return render_template('upload.html')

if __name__ == '__main__':
    os.makedirs(os.path.join('static', 'uploads'), exist_ok=True)
    app.run(debug=True)