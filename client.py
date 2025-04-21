import socket
import json
import threading
import redis
from queue import Queue

# Message queue for received redis messages
message_queue = Queue()

# Dictionary to store callback functions for different channels
callbacks = {}

redis_client = None
pubsub = None
subscriber_thread = None

def initialize_redis():
    """Initialize the Redis connection and subscriber thread"""
    global redis_client, pubsub, subscriber_thread
 
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    pubsub = redis_client.pubsub()
  
    subscriber_thread = threading.Thread(target=subscriber_loop)
    subscriber_thread.daemon = True
    subscriber_thread.start()

def subscribe_to_channel(channel, callback):
    """Subscribe to a Redis channel and register a callback"""
    global pubsub, callbacks
    
    if not redis_client:
        initialize_redis()
    
    # Register callback
    callbacks[channel] = callback

    pubsub.subscribe(channel)

def subscriber_loop():
    """Background thread to listen for Redis messages"""
    global pubsub, callbacks
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            channel = message['channel'].decode('utf-8')
            data = message['data'].decode('utf-8')
            
            try:
                message_data = json.loads(data)
                
                message_queue.put((channel, message_data))
                
                # Call callback if registered
                if channel in callbacks and callbacks[channel]:
                    callbacks[channel](message_data)
            except json.JSONDecodeError:
                pass 

def process_messages():
    """Process any messages in the queue, return True if messages were processed"""
    if message_queue.empty():
        return False
    
    while not message_queue.empty():
        channel, data = message_queue.get()
        # This is where you could handle messages globally
    
    return True

def send_request(request):
    """Send a request to the server and return the response"""
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect(("localhost", 5000))
        client_socket.send(request.encode())
        response = client_socket.recv(1024).decode()
        return response
    except ConnectionRefusedError:
        return "Error: Could not connect to server."
    finally:
        client_socket.close()

def subscribe_user_to_course(username, course_id):
    """Subscribe a user to receive updates about a course"""
    response = send_request(f"SUBSCRIBE {username} {course_id}")
    
    # Also subscribe to the Redis channel for this course
    subscribe_to_channel(f"course:{course_id}", None)  # You can add a callback later
    
    return response

def unsubscribe_user_from_course(username, course_id):
    """Unsubscribe a user from course updates"""
    response = send_request(f"UNSUBSCRIBE {username} {course_id}")
    return response

def get_user_subscriptions(username):
    """Get all courses a user is subscribed to"""
    response = send_request(f"MY_SUBSCRIPTIONS {username}")
    return response

def post_announcement(course_id, instructor, message):
    """Post an announcement to a course"""
    response = send_request(f"POST_ANNOUNCEMENT {course_id} {instructor} {message}")
    return response

def get_course_announcements(course_id):
    """Get all announcements for a course"""
    response = send_request(f"GET_ANNOUNCEMENTS {course_id}")
    return response