from flask import Flask, redirect, url_for, render_template, request, session, jsonify
from flask_dance.contrib.google import make_google_blueprint, google
import gspread
from google.auth import exceptions as auth_exceptions
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import os
from collections import defaultdict
from datetime import datetime , timedelta
from collections import Counter
from functools import wraps


#  AUTHORIZATION PART WITH GOOGLE


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
worksheet_name = 'Sheet1'


def authorize_and_get_worksheet(worksheet_name):
    access_token = session.get('access_token')
    credentials = authorize(refresh_token=access_token)
    service_account_path = os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json')
    gc = gspread.service_account(filename=service_account_path)
    sh = gc.open_by_key(spreadsheet_id)
    worksheet = sh.worksheet(worksheet_name)
    return worksheet


def authorize(refresh_token=None):
    creds = None
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    if refresh_token:
        creds = service_account.Credentials.from_service_account_file(
            os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json'), scopes=SCOPES
        )
        creds.refresh(Request())

    return creds



#   LOGIN PART


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('homepage'))
        return f(*args, **kwargs)
    return decorated_function

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
            # After successful login
            session['user_id'] = user_id

            return redirect(url_for('welcome', user_id=user_id))
        else:
            error_message = "Invalid credentials. Please try again."

    return render_template('login.html', error_message=error_message , user_id = None)


# SPREADSHEET MAIN CALL FUNCTION FOR CRUD

def get_and_update_spreadsheet(access_token, spreadsheet_id, worksheet_name, new_values):
    try:
        credentials = authorize(refresh_token=access_token)
        service_account_path = os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json')
        gc = gspread.service_account(filename=service_account_path)
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet(worksheet_name)

        # Find the first empty row in the worksheet
        next_row = len(worksheet.get_all_values()) + 1

        print(f"Next available row: {next_row}")

        # Set the order_id for the new entry
        new_values.insert(0, 1)

        # Add the new values to the spreadsheet
        worksheet.insert_row(new_values, 2)

        # Update order_id numbering for existing rows
        existing_data = worksheet.get_all_values()[1:]  # Exclude header row and new entry
        updated_order_ids = [[str(i + 1)] for i in range(len(existing_data))]
        cell_list = worksheet.range(f'A2:A{len(existing_data) + 1}')  # Adjust the range based on the number of existing rows

        for cell, value in zip(cell_list, updated_order_ids):
            cell.value = value[0]

        worksheet.update_cells(cell_list)

        print("Data updated successfully.")

        return True
    except auth_exceptions.RefreshError as e:
        print(f"RefreshError: {e}")
        return False
    except gspread.exceptions.APIError as e:
        print(f"APIError: {e}")
        return False

# WELCOME PAGE

@app.route('/welcome', methods=['GET', 'POST'])
@login_required
def welcome():

    access_token = session.get('access_token')
    user_id = session.get('user_id')

    if request.method == 'POST':
        # Get form ID
        form_id = request.form.get('form_id')

        if form_id == 'order_form':
            # Process order form data
            order_client_type = request.form.get('orderClientType')
            if order_client_type == 'other':
                order_client_type = request.form.get('customClientName')

            item_type = request.form.get('itemType')
            total_amount = request.form.get('totalAmount')
            due_date = request.form.get('dueDate')
            po_number = request.form.get('poNumber')

            # Add the data to the spreadsheet
            new_values = [order_client_type, item_type, total_amount, due_date, po_number]

            # Assuming you have spreadsheet_id, worksheet_name defined
            spreadsheet_id = '1fyRwbxfQ2Utbr32HGk8BooPnmJG2NtDSqT19NzXz-ts'
            worksheet_name = 'Sheet1'

            # Call the function to get and update the spreadsheet
            success = get_and_update_spreadsheet(access_token, spreadsheet_id, worksheet_name, new_values)

            if success:
                print("Order data updated successfully.")
            else:
                print("Failed to update order data.")

        elif form_id == 'item_form':
            # Process item form data
            item_type = request.form.get('ItemType')
            if item_type == 'other':
                item_type = request.form.get('customItemName')

            quantity = request.form.get('Quantity')
            last_ordered = request.form.get('LastOrdered')
            cost = request.form.get('Cost')

            # Add the data to the spreadsheet for the item form
            new_values_item = [item_type, quantity, last_ordered, cost]

            # Assuming you have spreadsheet_id, worksheet_name defined
            spreadsheet_id_item = '1fyRwbxfQ2Utbr32HGk8BooPnmJG2NtDSqT19NzXz-ts'
            worksheet_name_item = 'Sheet2'  # Adjust the worksheet name for the item form

            # Call the function to get and update the spreadsheet for the item form data
            success_item = get_and_update_spreadsheet(access_token, spreadsheet_id_item, worksheet_name_item, new_values_item)

            if success_item:
                print("Item data updated successfully.")
            else:
                print("Failed to update item data.")

        elif form_id == 'buyer_form':
            # Process buyer form data
            buyer = request.form.get('buyer')

            service = request.form.get('service')
            outstanding = request.form.get('outstanding')


            # Add the data to the spreadsheet for the item form
            new_values_item = [buyer, service, outstanding]

            # Assuming you have spreadsheet_id, worksheet_name defined
            spreadsheet_id_item = '1fyRwbxfQ2Utbr32HGk8BooPnmJG2NtDSqT19NzXz-ts'
            worksheet_name_item = 'Sheet3'  # Adjust the worksheet name for the item form

            # Call the function to get and update the spreadsheet for the item form data
            success_item = get_and_update_spreadsheet(access_token, spreadsheet_id_item, worksheet_name_item, new_values_item)

            if success_item:
                print("buyer data updated successfully.")
            else:
                print("Failed to update item data.")


        return redirect(url_for('welcome', user_id=user_id))


    try:
        # Assuming you have spreadsheet_id, worksheet_name defined
        spreadsheet_id = '1fyRwbxfQ2Utbr32HGk8BooPnmJG2NtDSqT19NzXz-ts'
        worksheet_name = 'Sheet1'

        # Call the function to authorize and get the worksheet
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Get all values from Sheet1
        values_sheet1 = worksheet.get_all_values()

        # Extract header and rows for Sheet1
        header_sheet1 = values_sheet1[0]
        rows_sheet1 = values_sheet1[1:]

        # Find the index of the 'Order Client Type' and 'Due Date' columns for Sheet1
        order_client_type_index_sheet1 = header_sheet1.index('Client_name')
        due_date_index_sheet1 = header_sheet1.index('Due_date')

        # Filter orders for this month
        today = datetime.now()
        end_of_month = today.replace(day=28) + timedelta(days=4)
        end_of_month = end_of_month - timedelta(days=end_of_month.day)

        orders_this_month = [
            {'Client_name': row[order_client_type_index_sheet1], 'Due_date': row[due_date_index_sheet1]}
            for row in rows_sheet1
            if row[due_date_index_sheet1] and datetime.strptime(row[due_date_index_sheet1], '%Y-%m-%d').date() <= end_of_month.date()
        ]

        return render_template('welcome.html', user_id=user_id, orders_this_month=orders_this_month)

    except Exception as e:
        print(f"Error fetching orders: {e}")
        return render_template('error.html', message="Failed to fetch orders.")

    return render_template('welcome.html', user_id=user_id)

# GETTING CLIENTS AND SHOWING


def get_client_names():
    try:
        service_account_path = os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json')
        gc = gspread.service_account(filename=service_account_path)

        # Replace 'your-spreadsheet-key' with the key of your Google Sheets document
        sh = gc.open_by_key('1fyRwbxfQ2Utbr32HGk8BooPnmJG2NtDSqT19NzXz-ts')

        # Replace 'Sheet1' with the name of your worksheet
        worksheet = sh.worksheet('Sheet1')

        # Retrieve client names from the 'Client_name' column (column B)
        client_names = worksheet.col_values(2)

        # Exclude the header if present
        if client_names and client_names[0] == 'Client_name':
            client_names = client_names[1:]

        # Use a set to keep track of unique client names
        unique_client_names = set(client_names)

        # Convert the set back to a list
        new_client_names = list(unique_client_names)

        # Debug statements
        print(f"Worksheet Name: {worksheet.title}")
        print(f"Number of Rows: {worksheet.row_count}")
        print(f"Client Names: {client_names}")

        return new_client_names
    except Exception as e:
        print(f"Error fetching client names: {e}")
        return []


@app.route('/get_client_names')
@login_required
def get_client_names_endpoint():
    # Call the function to fetch client names
    client_names = get_client_names()

    # Return the client names as JSON
    return jsonify(client_names)


@app.route('/clients')
@login_required
def clients():
    # Call the function to fetch client names
    client_names = get_client_names()

    # Render the 'clients.html' template and pass the client_names to it
    return render_template('client.html', client_names=client_names)




#GETTING ITEMS AND SHOWING

def get_item_names():
    try:
        service_account_path = os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json')
        gc = gspread.service_account(filename=service_account_path)

        # Replace 'your-spreadsheet-key' with the key of your Google Sheets document
        sh = gc.open_by_key('1fyRwbxfQ2Utbr32HGk8BooPnmJG2NtDSqT19NzXz-ts')

        # Replace 'Sheet1' with the name of your worksheet
        worksheet = sh.worksheet('Sheet2')

        # Retrieve client names from the 'Client_name' column (column B)
        item_names = worksheet.col_values(2)

        # Exclude the header if present
        if item_names and item_names[0] == 'Item_name':
            item_names = item_names[1:]


        # Use a set to keep track of unique client names
        unique_item_names = set(item_names)

        # Convert the set back to a list
        new_item_names = list(unique_item_names)


        return new_item_names
    except Exception as e:
        print(f"Error fetching item names: {e}")
        return []

@app.route('/get_item_names')
@login_required
def get_item_names_endpoint():
    # Call the function to fetch client names
    item_names = get_item_names()

    # Return the client names as JSON
    return jsonify(item_names)

# CRUD OPERATIONS ON ORDERS


@app.route('/orders')
@login_required
def orders():
    if not google.authorized:
        return redirect(url_for('google.login'))
    try:
        access_token = session.get('access_token')
        credentials = authorize(refresh_token=access_token)
        service_account_path = os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json')
        gc = gspread.service_account(filename=service_account_path)
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet(worksheet_name)

        # Get all values from the worksheet
        values = worksheet.get_all_values()

        # Extract header and rows
        header = values[0]
        rows = values[1:]

        return render_template('orders.html', header=header, rows=rows)

    except Exception as e:
        print(f"Error fetching orders: {e}")
        return render_template('error.html', message="Failed to fetch orders.")


from flask import flash, redirect, url_for

@app.route('/delete_order/<row_id>', methods=['GET', 'POST'])
@login_required
def delete_order(row_id):
    try:
        # Get the worksheet
        worksheet_name = "Sheet1"
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Move this block to ensure 'rows' is defined before the try block
        values = worksheet.get_all_values()
        header = values[0]
        rows = values[1:]

        # Find the index of the row with the specified ID
        index = -1
        for i, row in enumerate(rows):
            if row[0] == row_id:
                index = i
                break

        if index == -1:
            flash("Order not found.", "error")
            return redirect(url_for('orders'))

        # Perform delete logic here
        worksheet.delete_rows(index + 2)  # Add 2 to account for header row

        # Get the first column 'A' values starting from row 2
        order_ids = worksheet.col_values(1)[1:]

        # Update the order_id in column 'A'
        for i in range(index, len(order_ids)):
            worksheet.update_cell(i + 2, 1, str(i + 1))  # Start from 1


        flash(f"Deleted row {row_id} successfully.", "success")


    except Exception as e:
        print(f"Error deleting order: {e}")
        flash("Failed to delete order.", "error")

    return redirect(url_for('orders'))


# Add this route to your Flask application
@app.route('/edit_order/<row_id>', methods=['GET','POST'])
@login_required
def edit_order(row_id):
    try:

        worksheet_name = "Sheet1"
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Fetch all values from the worksheet
        values = worksheet.get_all_values()

        # Find the header and rows
        header = values[0]
        rows = values[1:]

        # Find the row with the specified ID
        order = None
        for row in rows:
            if row[0] == row_id:
                order = dict(zip(header, row))
                break

        if order:
            return render_template('edit_order.html', row_id=row_id, order=order)
        else:
            flash("Order not found.", "error")
            return redirect(url_for('orders'))

    except Exception as e:
        print(f"Error fetching order data: {e}")
        flash("Failed to fetch order data.", "error")
        return redirect(url_for('orders'))

@app.route('/update_order/<row_id>', methods=['GET','POST'])
@login_required
def update_order(row_id):
    try:

        worksheet_name = "Sheet1"
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Fetch all values from the worksheet
        values = worksheet.get_all_values()

        # Find the header and rows
        header = values[0]
        rows = values[1:]

        # Find the index of the row with the specified ID
        index = -1
        for i, row in enumerate(rows):
            if row[0] == row_id:
                index = i
                break

        if index == -1:
            flash("Order not found.", "error")
            return redirect(url_for('orders'))

        # Get the existing values in the row
        existing_values = rows[index]

        # Get the new values from the form, use existing values if not provided
        Client_name = request.form.get('clientName', existing_values[1])
        Item_type = request.form.get('itemType', existing_values[2])
        Amount = request.form.get('amount', existing_values[3])
        Due_date = request.form.get('dueDate', existing_values[4])
        Po_number = request.form.get('ponumber', existing_values[5])

        # Convert Amount to int
        Amount = int(Amount) if Amount else existing_values[3]

        updated_values = [existing_values[0], Client_name, Item_type, Amount, Due_date, Po_number]
        print(f"Updating values for row {row_id}: {updated_values}")
        worksheet.update(f'A{index + 2}', [list(map(str, updated_values))])


        # Flash a success message
        flash(f"Order {row_id} updated successfully.", "success")

        return redirect(url_for('orders'))

    except Exception as e:
        print(f"Error updating order: {e}")
        flash("Failed to update order.", "error")
        return redirect(url_for('orders'))



# CRUD OPERATIONS ON ITEMS


@app.route('/inventory')
@login_required
def inventory():
    if not google.authorized:
        return redirect(url_for('google.login'))
    try:
        access_token = session.get('access_token')
        credentials = authorize(refresh_token=access_token)
        service_account_path = os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json')
        gc = gspread.service_account(filename=service_account_path)
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet('Sheet2')

        # Get all values from the worksheet
        values = worksheet.get_all_values()

        # Extract header and rows
        header = values[0]
        rows = values[1:]

        return render_template('inventory.html', header=header, rows=rows)

    except Exception as e:
        print(f"Error fetching orders: {e}")
        return render_template('error.html', message="Failed to fetch orders.")

# Add this route to your Flask application




@app.route('/delete_item/<row_id>', methods=['GET', 'POST'])
@login_required
def delete_item(row_id):
    try:

        worksheet_name = "Sheet2"
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Move this block to ensure 'rows' is defined before the try block
        values = worksheet.get_all_values()
        header = values[0]
        rows = values[1:]

        # Find the index of the row with the specified ID
        index = -1
        for i, row in enumerate(rows):
            if row[0] == row_id:
                index = i
                break

        if index == -1:
            flash("Itemr not found.", "error")
            return redirect(url_for('orders'))

        # Perform delete logic here
        worksheet.delete_rows(index + 2)  # Add 2 to account for header row

        # Get the first column 'A' values starting from row 2
        item_ids = worksheet.col_values(1)[1:]

        # Update the order_id in column 'A'
        for i in range(index, len(item_ids)):
            worksheet.update_cell(i + 2, 1, str(i + 1))  # Start from 1


        flash(f"Deleted row {row_id} successfully.", "success")


    except Exception as e:
        print(f"Error deleting Item Row: {e}")
        flash("Failed to delete .", "error")

    return redirect(url_for('inventory'))





@app.route('/edit_item/<row_id>', methods=['GET','POST'])
@login_required
def edit_item(row_id):
    try:

        worksheet_name = "Sheet2"
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Fetch all values from the worksheet
        values = worksheet.get_all_values()

        # Find the header and rows
        header = values[0]
        rows = values[1:]

        # Find the row with the specified ID
        item = None
        for row in rows:
            if row[0] == row_id:
                item = dict(zip(header, row))
                break

        if item:
            return render_template('edit_item.html', row_id=row_id, item=item)
        else:
            flash("Item not found.", "error")
            return redirect(url_for('inventory'))

    except Exception as e:
        print(f"Error fetching item data: {e}")
        flash("Failed to fetch item data.", "error")
        return redirect(url_for('inventory'))





@app.route('/update_item/<row_id>', methods=['GET','POST'])
@login_required
def update_item(row_id):
    try:

        worksheet_name = "Sheet2"
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Fetch all values from the worksheet
        values = worksheet.get_all_values()

        # Find the header and rows
        header = values[0]
        rows = values[1:]

        # Find the index of the row with the specified ID
        index = -1
        for i, row in enumerate(rows):
            if row[0] == row_id:
                index = i
                break

        if index == -1:
            flash("item not found.", "error")
            return redirect(url_for('inventory'))

        # Get the existing values in the row
        existing_values = rows[index]

        # Get the new values from the form, use existing values if not provided
        Item_name = request.form.get('ItemType', existing_values[1])
        Quantity = request.form.get('quantity', existing_values[2])
        Last_ordered = request.form.get('lastordered', existing_values[3])
        Amount = request.form.get('amount', existing_values[4])
        # Convert Quantity and Amount to int if applicable
        Quantity = int(Quantity) if Quantity else existing_values[2]
        Amount = int(Amount) if Amount else existing_values[4]


        updated_values = [existing_values[0], Item_name, Quantity, Last_ordered, Amount]
        print(f"Updating values for row {row_id}: {updated_values}")
        worksheet.update(f'A{index + 2}', [list(map(str, updated_values))])


        # Flash a success message
        flash(f"Item {row_id} updated successfully.", "success")

        return redirect(url_for('inventory'))

    except Exception as e:
        print(f"Error updating item: {e}")
        flash("Failed to update item.", "error")
        return redirect(url_for('inventory'))


# CRUD OPERATIONS ON Buyers


@app.route('/buyers')
@login_required
def buyers():
    if not google.authorized:
        return redirect(url_for('google.login'))
    try:
        access_token = session.get('access_token')
        credentials = authorize(refresh_token=access_token)
        service_account_path = os.path.join(os.path.dirname(__file__), 'credentials', 'secret_key01.json')
        gc = gspread.service_account(filename=service_account_path)
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet('Sheet3')

        # Get all values from the worksheet
        values = worksheet.get_all_values()

        # Extract header and rows
        header = values[0]
        rows = values[1:]

        return render_template('buyers.html', header=header, rows=rows)

    except Exception as e:
        print(f"Error fetching buyers: {e}")
        return render_template('error.html', message="Failed to fetch orders.")

# Add this route to your Flask application




@app.route('/delete_buyer/<row_id>', methods=['GET', 'POST'])
@login_required
def delete_buyer(row_id):
    try:

        worksheet_name = "Sheet3"
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Move this block to ensure 'rows' is defined before the try block
        values = worksheet.get_all_values()
        header = values[0]
        rows = values[1:]

        # Find the index of the row with the specified ID
        index = -1
        for i, row in enumerate(rows):
            if row[0] == row_id:
                index = i
                break

        if index == -1:
            flash("Buyer not found.", "error")
            return redirect(url_for('buyers'))

        # Perform delete logic here
        worksheet.delete_rows(index + 2)  # Add 2 to account for header row

        # Get the first column 'A' values starting from row 2
        buyer_ids = worksheet.col_values(1)[1:]

        # Update the order_id in column 'A'
        for i in range(index, len(buyer_ids)):
            worksheet.update_cell(i + 2, 1, str(i + 1))  # Start from 1


        flash(f"Deleted row {row_id} successfully.", "success")


    except Exception as e:
        print(f"Error deleting Buyer Row: {e}")
        flash("Failed to delete .", "error")

    return redirect(url_for('buyers'))





@app.route('/edit_buyer/<row_id>', methods=['GET','POST'])
@login_required
def edit_buyer(row_id):
    try:

        worksheet_name = "Sheet3"
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Fetch all values from the worksheet
        values = worksheet.get_all_values()

        # Find the header and rows
        header = values[0]
        rows = values[1:]

        # Find the row with the specified ID
        buyer = None
        for row in rows:
            if row[0] == row_id:
                buyer = dict(zip(header, row))
                break

        if buyer:
            return render_template('edit_buyer.html', row_id=row_id, buyer=buyer)
        else:
            flash("Buyer not found.", "error")
            return redirect(url_for('buyers'))

    except Exception as e:
        print(f"Error fetching buyer data: {e}")
        flash("Failed to fetch buyer data.", "error")
        return redirect(url_for('buyers'))





@app.route('/update_buyer/<row_id>', methods=['GET','POST'])
@login_required
def update_buyer(row_id):
    try:

        worksheet_name = "Sheet3"
        worksheet = authorize_and_get_worksheet(worksheet_name)

        # Fetch all values from the worksheet
        values = worksheet.get_all_values()

        # Find the header and rows
        header = values[0]
        rows = values[1:]

        # Find the index of the row with the specified ID
        index = -1
        for i, row in enumerate(rows):
            if row[0] == row_id:
                index = i
                break

        if index == -1:
            flash("buyer not found.", "error")
            return redirect(url_for('buyers'))

        # Get the existing values in the row
        existing_values = rows[index]

        # Get the new values from the form, use existing values if not provided
        Buyer_name = request.form.get('buyer', existing_values[1])
        Service = request.form.get('service', existing_values[2])
        Outstanding = request.form.get('outstanding', existing_values[3])



        Outstanding = int(Outstanding) if Outstanding else existing_values[3]


        updated_values = [existing_values[0], Buyer_name, Service, Outstanding]
        print(f"Updating values for row {row_id}: {updated_values}")
        worksheet.update(f'A{index + 2}', [list(map(str, updated_values))])


        # Flash a success message
        flash(f"Item {row_id} updated successfully.", "success")

        return redirect(url_for('buyers'))

    except Exception as e:
        print(f"Error updating buyer: {e}")
        flash("Failed to update buyer", "error")
        return redirect(url_for('buyers'))




# ANALYSIS PART


@app.route('/analysis')
@login_required
def analysis():
    try:

        if session.get('user_id') != 'admin':
            return redirect(url_for('homepage'))

        # Analysis for Sheet1
        worksheet_name_sheet1 = "Sheet1"
        worksheet_sheet1 = authorize_and_get_worksheet(worksheet_name_sheet1)

        # Get all values from Sheet1
        values_sheet1 = worksheet_sheet1.get_all_values()

        # Extract header and rows for Sheet1
        header_sheet1 = values_sheet1[0]
        rows_sheet1 = values_sheet1[1:]

        # Find the index of the 'Item_type' and 'Amount' columns for Sheet1
        item_type_index_sheet1 = header_sheet1.index('Item_type')
        amount_index_sheet1 = header_sheet1.index('Amount')
        due_date_index_sheet1 = header_sheet1.index('Due_date')


        # Calculate the sum of amounts for each category for Sheet1
        category_totals_sheet1 = defaultdict(float)
        total_sales_all_categories_sheet1 = 0.0
        upcoming_due_dates_sheet1 = []

        for row in rows_sheet1:
            item_type = row[item_type_index_sheet1]
            amount = float(row[amount_index_sheet1])
            category_totals_sheet1[item_type] += amount
            total_sales_all_categories_sheet1 += amount


            # Due date analysis
            due_date_str = row[due_date_index_sheet1]
            if due_date_str:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                if due_date >= datetime.now().date():
                    upcoming_due_dates_sheet1.append(due_date.strftime('%Y-%m-%d'))
         # Count the number of orders per month for due date analysis
        orders_per_month_sheet1 = Counter([due_date.split('-')[1] for due_date in upcoming_due_dates_sheet1])

        total_orders_sheet1 = len(rows_sheet1)


        # Analysis for Sheet2
        worksheet_name_sheet2 = "Sheet2"
        worksheet_sheet2 = authorize_and_get_worksheet(worksheet_name_sheet2)

        # Get all values from Sheet2
        values_sheet2 = worksheet_sheet2.get_all_values()

        # Extract header and rows for Sheet2
        header_sheet2 = values_sheet2[0]
        rows_sheet2 = values_sheet2[1:]

        # Find the index of the 'Item_type' and 'Quantity' columns for Sheet2
        item_type_index_sheet2 = header_sheet2.index('Item_name')
        quantity_index_sheet2 = header_sheet2.index('Quantity')

        # Calculate the sum of quantities for each category for Sheet2
        category_totals_sheet2 = defaultdict(float)

        for row in rows_sheet2:
            item_type = row[item_type_index_sheet2]
            quantity = float(row[quantity_index_sheet2])
            category_totals_sheet2[item_type] += quantity



        worksheet_name_sheet3 = "Sheet3"
        worksheet_sheet3 = authorize_and_get_worksheet(worksheet_name_sheet3)

        # Get all values from Sheet1
        values_sheet3 = worksheet_sheet3.get_all_values()

        # Extract header and rows for Sheet1
        header_sheet3 = values_sheet3[0]
        rows_sheet3 = values_sheet3[1:]


        buyer_name_index_sheet3 = header_sheet3.index('Buyer_name')
        outstanding_sheet3 = header_sheet3.index('Outstanding')



        # Calculate the sum of amounts for each category for Sheet1
        category_totals_sheet3 = defaultdict(float)
        total_outstanding_all_categories_sheet3 = 0.0


        for row in rows_sheet3:
            buyer_name = row[buyer_name_index_sheet3]
            outstanding = float(row[outstanding_sheet3])
            category_totals_sheet3[buyer_name] += outstanding
            total_outstanding_all_categories_sheet3 += outstanding




        total_orders_sheet3 = len(rows_sheet3)



        # Render a template or return JSON with the analysis results
        return render_template('analysis.html',
                               category_totals_sheet1=category_totals_sheet1,
                               total_sales_all_categories_sheet1=total_sales_all_categories_sheet1,
                                 total_orders_sheet1=total_orders_sheet1,
                               orders_per_month_sheet1=orders_per_month_sheet1,
                               category_totals_sheet2=category_totals_sheet2,
                               category_totals_sheet3=category_totals_sheet3,
                               total_outstanding_all_categories_sheet3=total_outstanding_all_categories_sheet3)

    except Exception as e:
        print(f"Error performing analysis: {e}")
        return render_template('error.html', message="Failed to perform analysis.")








#SIGNOUT PART


@app.route('/signout', methods=['POST'])
def sign_out():
    # Clear the session
    session.clear()
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
