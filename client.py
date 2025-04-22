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
    
    try:
        # Only initialize once
        if redis_client is None:
            redis_client = redis.Redis(host='localhost', port=6379, db=0)
            pubsub = redis_client.pubsub()
            
            # Start the subscriber thread only once
            if subscriber_thread is None or not subscriber_thread.is_alive():
                subscriber_thread = threading.Thread(target=subscriber_loop)
                subscriber_thread.daemon = True
                subscriber_thread.start()
            
            print("Redis client initialized successfully")
            return True
    except Exception as e:
        print(f"Redis initialization error: {str(e)}")
        return False

def subscribe_to_channel(channel, callback):
    """Subscribe to a Redis channel and register a callback"""
    global pubsub, callbacks
    
    if not redis_client:
        if not initialize_redis():
            print(f"Failed to subscribe to channel {channel}: Redis not initialized")
            return False
    
    try:
        # Convert channel to string if it's bytes
        if isinstance(channel, bytes):
            channel = channel.decode('utf-8')
            
        # Register callback
        if callback is not None:
            callbacks[channel] = callback
        
        # Subscribe to the channel
        pubsub.subscribe(channel)
        print(f"Subscribed to channel: {channel}, callback: {callback is not None}")
        return True
    except Exception as e:
        print(f"Subscribe error: {str(e)}")
        return False

def subscriber_loop():
    """Background thread to listen for Redis messages"""
    global pubsub, callbacks
    
    print("Redis subscriber thread started")
    
    try:
        for message in pubsub.listen():
            if message['type'] == 'message':
                channel = message['channel'].decode('utf-8')
                data = message['data'].decode('utf-8')
                
                try:
                    message_data = json.loads(data)
                    print(f"Received message on channel {channel}: {message_data}")
                    
                    # Add to queue for processing in main thread
                    message_queue.put((channel, message_data))
                    
                    # Call callback if registered
                    if channel in callbacks and callbacks[channel]:
                        callbacks[channel](message_data)
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {str(e)}, Data: {data}")
                except Exception as e:
                    print(f"Error processing message: {str(e)}")
    except Exception as e:
        print(f"Subscriber loop error: {str(e)}")

def process_messages():
    """Process any messages in the queue, return True if messages were processed"""
    processed = False
    
    try:
        # Process up to 10 messages at a time to prevent UI freezing
        for _ in range(10):
            if message_queue.empty():
                break
                
            channel, data = message_queue.get_nowait()
            print(f"Processing message from channel {channel}")
            
            # Call appropriate callback if registered
            if channel in callbacks and callbacks[channel]:
                callbacks[channel](data)
            
            processed = True
            message_queue.task_done()
    except Exception as e:
        print(f"Error processing messages: {str(e)}")
        
    return processed

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
    if "Successfully subscribed" in response:
        # Find an existing callback from any registered channel
        callback = None
        for ch, cb in callbacks.items():
            if cb is not None:
                callback = cb
                break
        
        # Use the existing callback or None if no callbacks are registered
        subscribe_to_channel(f"course:{course_id}", callback)
    
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

def test_publish():
    """Publish a test message to all channels to verify Redis is working"""
    if redis_client is None:
        initialize_redis()
    
    if redis_client:
        test_message = {
            "event_type": "test_message",
            "message": "This is a test message",
            "timestamp": "test_time"
        }
        redis_client.publish('all_courses', json.dumps(test_message))
        print("Test message published to all_courses channel")
        return True
    return False