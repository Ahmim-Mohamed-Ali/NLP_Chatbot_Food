import os
import mysql.connector
from urllib.parse import urlparse

# Récupérer l'URL de la base de données à partir des variables d'environnement
database_url = os.environ['JAWSDB_URL'] 
#database_url="mysql://vfms6u9c1z6xuj9l:hqjwhl6irlskqlb0@d6vscs19jtah8iwb.cbetxkdyhwsb.us-east-1.rds.amazonaws.com:3306/l1jbflb7xwa579ey"
# Analyser l'URL pour obtenir les détails de connexion
url_parts = urlparse(database_url)
username = url_parts.username
password = url_parts.password
host = url_parts.hostname
database = url_parts.path[1:]  # Supprimer le slash initial


def check_db_connection():
    """Check if the database connection is successful."""
    conn = connect_to_db()
    if conn:
        print("Connecté à la base de données avec succès")
        conn.close()  # Ferme la connexion après vérification
    else:
        print("Erreur de connexion à la base de données")


def connect_to_db():
    try:
        cnx = mysql.connector.connect(
            user=username,
            password=password,
            host=host,
            database=database
        )
        print("Connecté à la base de données avec succès")
        return cnx
    except mysql.connector.Error as err:
        print(f"Erreur de connexion à la base de données : {err}")
        return None

def insert_order_item(food_item, quantity, order_id):
    cnx = connect_to_db()  # Assurez-vous d'être connecté à la base de données
    if cnx is None:
        return -1  # Retourner en cas d'échec de la connexion

    try:
        cursor = cnx.cursor()
        cursor.callproc('insert_order_item', (food_item, quantity, order_id))
        cnx.commit()
        print("Order item inserted successfully!")
        return 1
    except mysql.connector.Error as err:
        print(f"Error inserting order item: {err}")
        cnx.rollback()
        return -1
    finally:
        cursor.close()  # Fermer le curseur à chaque fois
        cnx.close()  # Fermer la connexion à la base de données

def insert_order_tracking(order_id, status):
    cnx = connect_to_db()
    if cnx is None:
        return -1

    try:
        cursor = cnx.cursor()
        insert_query = "INSERT INTO order_tracking (order_id, status) VALUES (%s, %s)"
        cursor.execute(insert_query, (order_id, status))
        cnx.commit()
    except mysql.connector.Error as err:
        print(f"Error inserting order tracking: {err}")
        cnx.rollback()
        return -1
    finally:
        cursor.close()
        cnx.close()

def get_total_order_price(order_id):
    cnx = connect_to_db()
    if cnx is None:
        return -1

    try:
        cursor = cnx.cursor()
        query = f"SELECT get_total_order_price({order_id})"
        cursor.execute(query)
        result = cursor.fetchone()[0]
        return result
    except mysql.connector.Error as err:
        print(f"Error getting total order price: {err}")
        return -1
    finally:
        cursor.close()
        cnx.close()

def get_next_order_id():
    cnx = connect_to_db()
    if cnx is None:
        return -1

    try:
        cursor = cnx.cursor()
        query = "SELECT MAX(order_id) FROM orders"
        cursor.execute(query)
        result = cursor.fetchone()[0]
        return 1 if result is None else result + 1
    except mysql.connector.Error as err:
        print(f"Error getting next order ID: {err}")
        return -1
    finally:
        cursor.close()
        cnx.close()

def get_order_status(order_number: int):
    cnx = connect_to_db()
    if cnx is None:
        return -1

    try:
        cursor = cnx.cursor()
        query = "SELECT status FROM order_tracking WHERE order_id = %s"
        cursor.execute(query, (order_number,))
        result = cursor.fetchone()
        return result[0] if result else None
    except mysql.connector.Error as err:
        print(f"Error getting order status: {err}")
        return None
    finally:
        cursor.close()
        cnx.close()



