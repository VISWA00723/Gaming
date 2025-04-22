import stripe
import os
import sys
from dotenv import load_dotenv
from flask import jsonify, request, redirect, url_for, session

# Load environment variables from .env file
load_dotenv()

# Set recursion limit to avoid maximum recursion depth error
sys.setrecursionlimit(3000)

# Initialize Stripe with API key
stripe.api_key = os.getenv('STRIPE_API_KEY', 'sk_test_51RFbbMQSeqLmFxhC55exrrQ03OelX4tvEnUpv4pUGsdhUNb3RqgDPmb1SUAvl0kbXGt0YpAdeIznaeGvzv2PagOP00LlXK5fti')
# Set max network retries to prevent excessive recursion
stripe.max_network_retries = 2

class PaymentGateway:
    @staticmethod
    def create_checkout_session(booking_data, success_url, cancel_url):
        """Create a Stripe checkout session for a booking"""
        try:
            # Format line items for Stripe
            line_items = [{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"Turf Booking - {booking_data['date']} {booking_data['time_slot']}",
                        'description': f"Booking for {booking_data['name']} on {booking_data['date']} at {booking_data['time_slot']}",
                    },
                    'unit_amount': 5000,  # $50.00 in cents
                },
                'quantity': 1,
            }]
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'name': booking_data['name'],
                    'email': booking_data['email'],
                    'phone': booking_data['phone'],
                    'date': booking_data['date'],
                    'time_slot': booking_data['time_slot']
                }
            )
            
            return {
                'success': True,
                'session_id': checkout_session.id,
                'checkout_url': checkout_session.url
            }
            
        except stripe.error.StripeError as e:
            # Handle Stripe-specific errors
            return {
                'success': False,
                'error': f"Stripe error: {str(e)}"
            }
        except RecursionError as e:
            # Handle recursion errors specifically
            return {
                'success': False,
                'error': "System error: Maximum recursion depth exceeded. Please try again later."
            }
        except Exception as e:
            # Handle all other errors
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    @staticmethod
    def verify_payment(session_id):
        """Verify payment status for a checkout session"""
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            payment_status = checkout_session.payment_status
            
            return {
                'success': True,
                'payment_status': payment_status,
                'is_paid': payment_status == 'paid',
                'metadata': checkout_session.metadata
            }
            
        except stripe.error.StripeError as e:
            # Handle Stripe-specific errors
            return {
                'success': False,
                'error': f"Stripe error: {str(e)}"
            }
        except RecursionError as e:
            # Handle recursion errors specifically
            return {
                'success': False,
                'error': "System error: Maximum recursion depth exceeded. Please try again later."
            }
        except Exception as e:
            # Handle all other errors
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    @staticmethod
    def handle_webhook(payload, sig_header):
        """Handle Stripe webhook events"""
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_12345')
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            # Handle the event
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                
                # Extract booking details from metadata
                booking_data = {
                    'name': session.metadata.get('name'),
                    'email': session.metadata.get('email'),
                    'phone': session.metadata.get('phone'),
                    'date': session.metadata.get('date'),
                    'time_slot': session.metadata.get('time_slot'),
                    'payment_status': session.payment_status,
                    'payment_id': session.payment_intent
                }
                
                return {
                    'success': True,
                    'booking_data': booking_data
                }
                
            return {
                'success': True,
                'event_type': event['type']
            }
            
        except stripe.error.StripeError as e:
            # Handle Stripe-specific errors
            return {
                'success': False,
                'error': f"Stripe error: {str(e)}"
            }
        except RecursionError as e:
            # Handle recursion errors specifically
            return {
                'success': False,
                'error': "System error: Maximum recursion depth exceeded. Please try again later."
            }
        except Exception as e:
            # Handle all other errors
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    @staticmethod
    def get_payment_details(payment_id):
        """Get detailed information about a payment"""
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_id)
            
            return {
                'success': True,
                'amount': payment_intent.amount / 100,  # Convert cents to dollars
                'currency': payment_intent.currency,
                'status': payment_intent.status,
                'payment_method': payment_intent.payment_method,
                'created': payment_intent.created,
                'customer': payment_intent.customer
            }
            
        except stripe.error.StripeError as e:
            # Handle Stripe-specific errors
            return {
                'success': False,
                'error': f"Stripe error: {str(e)}"
            }
        except RecursionError as e:
            # Handle recursion errors specifically
            return {
                'success': False,
                'error': "System error: Maximum recursion depth exceeded. Please try again later."
            }
        except Exception as e:
            # Handle all other errors
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    @staticmethod
    def refund_payment(payment_id, amount=None):
        """Refund a payment partially or fully"""
        try:
            refund_params = {'payment_intent': payment_id}
            if amount:
                refund_params['amount'] = int(amount * 100)  # Convert dollars to cents
                
            refund = stripe.Refund.create(**refund_params)
            
            return {
                'success': True,
                'refund_id': refund.id,
                'status': refund.status,
                'amount': refund.amount / 100  # Convert cents to dollars
            }
            
        except stripe.error.StripeError as e:
            # Handle Stripe-specific errors
            return {
                'success': False,
                'error': f"Stripe error: {str(e)}"
            }
        except RecursionError as e:
            # Handle recursion errors specifically
            return {
                'success': False,
                'error': "System error: Maximum recursion depth exceeded. Please try again later."
            }
        except Exception as e:
            # Handle all other errors
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
