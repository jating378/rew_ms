from flask import Flask, redirect, url_for, render_template, request, session
from flask_dance.contrib.google import make_google_blueprint, google
import gspread
from google.auth import exceptions as auth_exceptions
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Modify the scope to include 'profile' and 'email'
google_bp = make_google_blueprint(
    client_id='769459084831-4a27j7uke94penoq8qtq8js6p71tbqml.apps.googleusercontent.com',
    client_secret='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',
    redirect_to='homepage'
)

app.register_blueprint(google_bp, url_prefix='/google_login')

allowed_users = {
    'admin': 'admin_pass',
    'accountant': 'accountant_pass',
    'assistant': 'assistant_pass'
}

spreadsheet_id = '1fyRwbxfQ2Utbr32HGk8BooPnmJG2NtDSqT19NzXz-ts'


def authorize(refresh_token=None):
    creds = None
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    if refresh_token:
        creds = service_account.Credentials.from_service_account_file(
            os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json'), scopes=SCOPES
        )
        creds.refresh(Request())

    return creds



def get_and_update_spreadsheet(access_token, spreadsheet_id, worksheet_name, cell_range, new_value):
    try:
        credentials = authorize(refresh_token=access_token)
        service_account_path = os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json')
        gc = gspread.service_account(filename=service_account_path)  # This line is correct
        sh = gc.open_by_key('1fyRwbxfQ2Utbr32HGk8BooPnmJG2NtDSqT19NzXz-ts')
        worksheet = sh.worksheet('Sheet1')
        # Get the existing values in the specified cell_range
        cell_values = worksheet.get(cell_range)

        # If the cell_values is empty, initialize it as a 2D list with the new_value
        if not cell_values:
            cell_values = [[new_value]]
        else:
            # Update the existing value with the new_value
            if not cell_values[0]:
                cell_values[0] = [new_value]
            else:
                cell_values[0][0] = new_value

        # Use the update method from the Google Sheets API to update the cell
        worksheet.update(cell_range, cell_values)

        return True
    except auth_exceptions.RefreshError as e:
        print(f"RefreshError: {e}")
        return False
    except gspread.exceptions.APIError as e:
        print(f"APIError: {e}")
        return False


@app.route('/')
def google_login():
    if not google.authorized:
        return redirect(url_for('google.login'))

    access_token = google_bp.session.token['access_token']
    session['access_token'] = access_token

    return redirect(url_for('homepage'))


@app.route('/homepage', methods=['GET', 'POST'])
def homepage():
    if not google.authorized:
        return redirect(url_for('google.login'))
    error_message = None

    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']

        # Check if the entered credentials are valid
        if user_id in allowed_users and password == allowed_users[user_id]:
            return redirect(url_for('welcome', user_id=user_id))
        else:
            error_message = "Invalid credentials. Please try again."

    return render_template('login.html', error_message=error_message)


@app.route('/welcome/<user_id>', methods=['GET', 'POST'])
def welcome(user_id):
    # Use the Flask-Dance signal to get the credentials after authorization
    access_token = session.get('access_token')

    return render_template('welcome.html', user_id=user_id)


@app.route('/edit_spreadsheet', methods=['GET', 'POST'])
def edit_spreadsheet():
    if 'access_token' not in session:
        return redirect(url_for('google_login'))

    spreadsheet_id = '1fyRwbxfQ2Utbr32HGk8BooPnmJG2NtDSqT19NzXz-ts'  # Replace with your actual ID
    worksheet_name = 'Sheet1'  # Adjust based on your spreadsheet
    cell_range = 'A5'  # Specify the cell to update
    message = ""

    if request.method == 'POST':
        new_value = request.form['new_value']
        print(f"Trying to update cell with value: {new_value}")

        # Ensure the value is a valid value (e.g., a string, number, etc.)
        # You might want to validate or convert the value as needed

        status = get_and_update_spreadsheet(session['access_token'], spreadsheet_id, worksheet_name, cell_range, new_value)

        if status:
            message = "Cell updated successfully!"
            print("Cell updated successfully!")
        else:
            message = "Error updating cell. Please try again."
            print("Error updating cell. Please try again.")

    return render_template('edit_spreadsheet.html', message=message)




if __name__ == '__main__':
    app.run(debug=True, port=5000)
