import os
import mysql.connector
from urllib.parse import urlparse

# Récupérer l'URL de la base de données à partir des variables d'environnement
database_url = os.environ['JAWSDB_URL']
#if database_url is None:
#print("Utilisation de la base de données locale")
    # Détails de la base de données locale
"""
username = "root"  # Remplacez par votre nom d'utilisateur
password = "root"  # Remplacez par votre mot de passe
host = "localhost"  # Utilisez "127.0.0.1" si nécessaire
database = "pandeyji_eatery"
"""

    # Analyser l'URL pour obtenir les détails de connexion
url_parts = urlparse(database_url)
username = url_parts.username
password = url_parts.password
host = url_parts.hostname
database = url_parts.path[1:]  # Supprimer le slash initial

# Se connecter à la base de données MySQL
cnx = mysql.connector.connect(
    user=username,
    password=password,
    host=host,
    database=database
)


def insert_order_item(food_item, quantity, order_id):
    try:
        cursor = cnx.cursor()

        # Calling the stored procedure
        cursor.callproc('insert_order_item', (food_item, quantity, order_id))

        # Committing the changes
        cnx.commit()

        # Closing the cursor
        cursor.close()

        print("Order item inserted successfully!")

        return 1

    except mysql.connector.Error as err:
        print(f"Error inserting order item: {err}")

        # Rollback changes if necessary
        cnx.rollback()

        return -1

    except Exception as e:
        print(f"An error occurred: {e}")
        # Rollback changes if necessary
        cnx.rollback()

        return -1

# Function to insert a record into the order_tracking table
def insert_order_tracking(order_id, status):
    cursor = cnx.cursor()

    # Inserting the record into the order_tracking table
    insert_query = "INSERT INTO order_tracking (order_id, status) VALUES (%s, %s)"
    cursor.execute(insert_query, (order_id, status))

    # Committing the changes
    cnx.commit()

    # Closing the cursor
    cursor.close()

def get_total_order_price(order_id):
    cursor = cnx.cursor()

    # Executing the SQL query to get the total order price
    query = f"SELECT get_total_order_price({order_id})"
    cursor.execute(query)

    # Fetching the result
    result = cursor.fetchone()[0]

    # Closing the cursor
    cursor.close()

    return result

# Function to get the next available order_id
def get_next_order_id():
    cursor = cnx.cursor()

    # Executing the SQL query to get the next available order_id
    query = "SELECT MAX(order_id) FROM orders"
    cursor.execute(query)

    # Fetching the result
    result = cursor.fetchone()[0]

    # Closing the cursor
    cursor.close()

    # Returning the next available order_id
    if result is None:
        return 1
    else:
        return result + 1


def get_order_status(order_number:int):

    # Création d'un curseur pour exécuter des requêtes
    cursor = cnx.cursor()

    # ID de la commande que tu veux vérifier
    order_id = order_number # Remplace par ton ID récupéré

    # Requête pour récupérer l'état de la commande
    query = """
           SELECT status 
           FROM order_tracking 
           WHERE order_id = %s
       """

    # Exécution de la requête
    cursor.execute(query, (order_id,))

    # Récupération du résultat
    result = cursor.fetchone()

    # Fermeture du curseur
    cursor.close()
    # Vérification de l'état de la commande
    if result:
        return result[0]

    else:
        return None





