from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse,HTMLResponse
from backend import generic_helper
from backend import db_helper
import os
import logging
import redis,json

# Configuration du logging pour afficher dans la console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

# Connexion à Redis en utilisant l'URL
#redis_url = os.getenv('REDIS_URL', 'rediss://:p9278aa16bc31d9abb9ba61c4048c79694a7e6eda94cc40f07075f0940b8a58a8@ec2-44-221-1-111.compute-1.amazonaws.com:30850')  # Utiliser l'URL de Redis sur Heroku
redis_url='rediss://:p9278aa16bc31d9abb9ba61c4048c79694a7e6eda94cc40f07075f0940b8a58a8@ec2-44-221-1-111.compute-1.amazonaws.com:30850'
r = redis.StrictRedis.from_url(
    redis_url,
ssl_cert_reqs=None )

try:
    r.ping()  # Vérifie la connexion
    print("Connecté à Redis avec succès")
except redis.exceptions.ConnectionError as e:
    print(f"Erreur de connexion : {e}")





db_helper.check_db_connection()  # Appel de la fonction lors du démarrage
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), '../frontend'))
app = FastAPI()

# Monter le dossier statique pour accéder aux fichiers CSS et images
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), '../frontend')), name="static")

inprogress_orders={}

@app.get("/", response_class=HTMLResponse)  # Endpoint pour la page d'accueil
async def get_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})



@app.post("/")  # Utilisez POST car Dialogflow envoie des données via POST
async def root(request: Request):
    # Retrieve the JSON data from the request
    payload = await request.json()



    # Extract the necessary information from the payload
    # based on the structure of the WebhookRequest from Dialogflow
    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult']['outputContexts']

    session_id= generic_helper.extract_session_id(output_contexts[0]["name"])

    intent_handler_dict = {
        'order.add context:ongoing-order': add_to_order,
        'order.remove - context:ongoing-order': remove_from_order,
        'order.complete - context: ongoing-order': complete_order,
        'track.order-context:ongoing-tracking': track_order
    }
    print("recu intent",intent)
    return intent_handler_dict[intent](parameters,session_id)




def track_order(parameters:dict,session_id:str):
    id = parameters["number"]
    status = db_helper.get_order_status(id)
    print(f"Order Status: {status}")

    if status==-1:
        fulfillment_text = f"There was an issue connecting to the database. Please try again later."
    elif status is not None:
        fulfillment_text=f" Votre Commande Numéroe {id} est actuellement : {status}"
    else:
        fulfillment_text = f" Votre Commande Numéroe {id} n'a pas été trouvée"

    print(f"Fulfillment Text: {fulfillment_text}")
    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
        # "outputContexts": output_contexts  # Echoing back the output contexts if needed
    })


def add_to_order(parameters: dict, session_id: str):
    logger.info(f"Ajout d'articles à la commande pour la session {session_id}: {parameters}")

    food_items = parameters["food-items"]
    quantities = parameters["number"]

    if len(food_items) != len(quantities):
        fulfillment_text = "Sorry I didn't understand. Can you please specify food items and quantities clearly?"
        logger.warning("Nombre d'articles et de quantités ne correspond pas.")
    else:
        new_food_dict = dict(zip(food_items, quantities))

        # Récupérer la commande en cours depuis Redis
        existing_order = r.get(session_id)

        if existing_order:
            existing_order = json.loads(existing_order)
            existing_order.update(new_food_dict)
            logger.info(f"Commande existante mise à jour: {existing_order}")
        else:
            existing_order = new_food_dict
            logger.info("Création d'une nouvelle commande.")

        r.set(session_id, json.dumps(existing_order))
        result = generic_helper.get_str_from_food_dict(existing_order)
        fulfillment_text = f"So Far you have this order {result}. Do You need Anything Else ?"

    logger.info(f"Réponse à l'utilisateur: {fulfillment_text}")
    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


def remove_from_order(parameters: dict, session_id: str):
    # Récupérer la commande en cours depuis Redis
    existing_order = r.get(session_id)

    # Si aucune commande n'existe pour cette session
    if not existing_order:
        return JSONResponse(content={
            "fulfillmentText": "I'm having trouble finding your order. Sorry! Can you place a new order please?"
        })

    # Charger la commande à partir de Redis (elle est stockée en tant que chaîne JSON)
    current_order = json.loads(existing_order)

    food_items = parameters["food-items"]

    removed_items = []
    no_such_items = []

    # Parcourir les articles à supprimer
    for item in food_items:
        if item not in current_order:
            no_such_items.append(item)
        else:
            removed_items.append(item)
            del current_order[item]

    fulfillment_text = ""
    if len(removed_items) > 0:
        fulfillment_text = f'Removed {", ".join(removed_items)} from your order!'

    if len(no_such_items) > 0:
        fulfillment_text += f' Your current order does not have {", ".join(no_such_items)}'

    # Vérifier si la commande est maintenant vide
    if len(current_order) == 0:
        fulfillment_text += " Your order is empty!"
        # Supprimer la commande de Redis si elle est vide
        r.delete(session_id)
    else:
        # Si la commande n'est pas vide, mettre à jour la commande dans Redis
        r.set(session_id, json.dumps(current_order))
        order_str = generic_helper.get_str_from_food_dict(current_order)
        fulfillment_text += f" Here is what is left in your order: {order_str}"

    return JSONResponse(content={"fulfillmentText": fulfillment_text})


def complete_order(parameters: dict, session_id: str):
    existing_order = r.get(session_id)

    if not existing_order:
        fulfillment_text = "I'm having trouble finding your order. Can you place a new order?"
    else:
        order = json.loads(existing_order)
        order_id = save_to_db(order)

        if order_id == -1:
            fulfillment_text = "Sorry, I couldn't place your order. Please try again."
        else:
            order_total = db_helper.get_total_order_price(order_id)
            if order_total == -1:
                fulfillment_text = "There was an issue connecting to the database. Please try again later."
            else:
                fulfillment_text = f"Awesome! Your order ID is #{order_id}. The total is {order_total}."

            # Supprimer la commande après l'avoir complétée
            r.delete(session_id)

    return JSONResponse(content={"fulfillmentText": fulfillment_text})


def save_to_db(order: dict):
    next_order_id = db_helper.get_next_order_id()

    # Si l'ID de commande suivant ne peut pas être obtenu, échouer immédiatement
    if next_order_id == -1:
        return -1

    try:
        # Insérer chaque élément de la commande
        for food_item, quantity in order.items():
            rcode = db_helper.insert_order_item(
                food_item,
                quantity,
                next_order_id
            )

            if rcode == -1:
                return -1  # Retourne une erreur si l'insertion échoue

        # Maintenant insérer le statut de suivi de commande
        rcode2=db_helper.insert_order_tracking(next_order_id, "in progress")
        if rcode2==-1:
            return -1

        return next_order_id
    except Exception as e:
        print(f"Error saving order to database: {e}")
        return -1
