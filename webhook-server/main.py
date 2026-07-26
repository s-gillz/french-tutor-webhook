import os
import json
import stripe
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

# ============ 1. INITIALIZATIONS ============
app = FastAPI()

# Stripe Setup
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Firebase Setup (We use a service account JSON for the backend)
firebase_creds_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
if firebase_creds_json:
    cred_dict = json.loads(firebase_creds_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

# ============ 2. WEBHOOK ENDPOINT ============
@app.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    
    # 1. Verify the webhook signature (Security check from Stripe)
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, webhook_secret
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 2. Handle the Checkout Session Completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_email')
        
        if customer_email:
            print(f"✅ Payment received for: {customer_email}")
            
            # 3. Find the user in Firebase by email
            users_ref = db.collection('users')
            query = users_ref.where('email', '==', customer_email).limit(1).get()
            
            if query:
                user_doc = query[0]
                user_ref = db.collection('users').document(user_doc.id)
                
                # 4. Determine which plan to assign based on the product/amount
                # (You can customize this logic based on your Stripe Product IDs)
                # For now, we default to 'pro'. You can add logic for 'ultimate' later.
                new_plan = "pro" 
                
                # 5. Update the user's plan in Firestore
                user_ref.update({
                    "plan": new_plan,
                    "subscription": "paid"
                })
                print(f"🚀 Upgraded {customer_email} to {new_plan}!")
            else:
                print(f"️ User with email {customer_email} not found in database.")

    return JSONResponse(content={"status": "success"}, status_code=200)

@app.get("/")
async def root():
    return {"message": "Stripe Webhook Server is running!"}