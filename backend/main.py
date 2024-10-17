from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse,HTMLResponse
import os
from backend import generic_helper
from backend import db_helper
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

    return intent_handler_dict[intent](parameters,session_id)




def track_order(parameters:dict,session_id:str):
    id = parameters["number"]
    status = db_helper.get_order_status(id)
    print(f"Order Status: {status}")

    if status:
        fulfillment_text=f" Votre Commande Numéroe {id} est actuellement : {status}"
    else:
        fulfillment_text = f" Votre Commande Numéroe {id} n'a pas été trouvée"

    print(f"Fulfillment Text: {fulfillment_text}")
    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
        # "outputContexts": output_contexts  # Echoing back the output contexts if needed
    })

def add_to_order(paramaters:dict,session_id:str):
    food_items = paramaters["food-items"]
    quantities = paramaters["number"]

    if len(food_items) != len(quantities):
        fulfillment_text = "Sorry I didn't understand. Can you please specify food items and quantities clearly?"
    else:
        new_food_dict=dict(zip(food_items,quantities))
        if session_id in inprogress_orders:
            inprogress_orders[session_id].update(new_food_dict)
        else:
            inprogress_orders[session_id]=new_food_dict
        result= generic_helper.get_str_from_food_dict(inprogress_orders[session_id])
        fulfillment_text = f"So Far you have this order {result}. Do You need Anything Else ?"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
        # "outputContexts": output_contexts  # Echoing back the output contexts if needed
    })


def remove_from_order(parameters:dict,session_id:str):
    if session_id not in inprogress_orders:
        return JSONResponse(content={
            "fulfillmentText": "I'm having a trouble finding your order. Sorry! Can you place a new order please?"
        })

    food_items = parameters["food-items"]
    current_order = inprogress_orders[session_id]

    removed_items = []
    no_such_items = []

    for item in food_items:
        if item not in current_order:
            no_such_items.append(item)
        else:
            removed_items.append(item)
            del current_order[item]

    fulfillment_text=""
    if len(removed_items) > 0:
        fulfillment_text = f'Removed {",".join(removed_items)} from your order!'

    if len(no_such_items) > 0:
        fulfillment_text = f' Your current order does not have {",".join(no_such_items)}'

    if len(current_order.keys()) == 0:
        fulfillment_text += " Your order is empty!"
    else:
        order_str = generic_helper.get_str_from_food_dict(current_order)
        fulfillment_text += f" Here is what is left in your order: {order_str}"

    return JSONResponse(content={
        "fulfillmentText": fulfillment_text
    })


def complete_order(parameters:dict,session_id:str):
    if session_id not in inprogress_orders:
        fulfillment_text="I'm having a trouble finding your order. Sorry Can you place an other"
    else:
        order=inprogress_orders[session_id]
        order_id=save_to_db(order)
        print(order_id)
        if order_id==-1:
            fulfillment_text = "Sorry I Couldn't place your order . PlEASE TRY AGAIN"
        else:
            order_total= db_helper.get_total_order_price(order_id)
            fulfillment_text = f"Awesome. We have placed your order. " \
                               f"Here is your order id # {order_id}. " \
                               f"Your order total is {order_total} which you can pay at the time of delivery!"
            del inprogress_orders[session_id]

    return JSONResponse(content={
            "fulfillmentText": fulfillment_text
    })


def save_to_db(order: dict):
    next_order_id = db_helper.get_next_order_id()

    # Insert individual items along with quantity in orders table
    for food_item, quantity in order.items():
        rcode = db_helper.insert_order_item(
            food_item,
            quantity,
            next_order_id
        )

        if rcode == -1:
            return -1

    # Now insert order tracking status
    db_helper.insert_order_tracking(next_order_id, "in progress")

    return next_order_id