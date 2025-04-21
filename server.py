import sqlite3
import socket
import threading
import json
import redis

conn = sqlite3.connect("lms.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id TEXT,
    resource_url TEXT,
    poster_username TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    course_id TEXT,
    UNIQUE(username, course_id)
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id TEXT,
    message TEXT,
    instructor TEXT,
    timestamp TEXT
)
""")
conn.commit()


redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Register Users
def register_user(role, username, password):
    try:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                      (username, password, role))
        conn.commit()
        
        event_data = {
            "event_type": "new_user",
            "username": username,
            "role": role
        }
        redis_client.publish('system_events', json.dumps(event_data))
        
        return "Registration successful!"
    except sqlite3.IntegrityError:
        return "Error: Username already exists!"

# Login Users
def login_user(username, password):
    cursor.execute("SELECT role FROM users WHERE username=? AND password=?", 
                  (username, password))
    result = cursor.fetchone()
    if result:
        event_data = {
            "event_type": "user_login",
            "username": username,
            "role": result[0]
        }
        redis_client.publish('system_events', json.dumps(event_data))
        return f"Login successful {result[0]}"
    return "Error: Invalid credentials"

# upload course resources
def upload_course_resources(course_id, resource_url, poster_username):
    try:
        cursor.execute("INSERT INTO courses (course_id, resource_url, poster_username) VALUES (?, ?, ?)", 
                      (course_id, resource_url, poster_username))
        conn.commit()
        
        # Publish event for new resource
        event_data = {
            "event_type": "new_resource",
            "course_id": course_id,
            "resource_url": resource_url,
            "poster": poster_username
        }
        redis_client.publish(f'course:{course_id}', json.dumps(event_data))
        redis_client.publish('all_courses', json.dumps(event_data))
        
        return "Resource Added Successfully"
    except Exception as e:
        return f"Error: {str(e)}"

# fget course resources
def get_course_resource(course_id):
    try:
        cursor.execute("SELECT resource_url FROM courses WHERE course_id=?", (course_id,))
        result = cursor.fetchall()
        if not result:
            return "Error: No resources found for this course!"
        resource_urls = "|".join([row[0] for row in result])
        return resource_urls
    except Exception as e:
        return f"Error: {str(e)}"

# get all courses
def get_all_courses():
    try:
        cursor.execute("SELECT DISTINCT course_id FROM courses")
        courses = cursor.fetchall()
        if not courses:
            return "No courses available"
        return "|".join([c[0] for c in courses])
    except Exception as e:
        return f"Error: {str(e)}"

#subscribe to a course
def subscribe_to_course(username, course_id):
    try:
        cursor.execute("INSERT INTO subscriptions (username, course_id) VALUES (?, ?)", 
                      (username, course_id))
        conn.commit()
        
        # Publish subscription event
        event_data = {
            "event_type": "new_subscription",
            "username": username,
            "course_id": course_id
        }
        redis_client.publish(f'course:{course_id}', json.dumps(event_data))
        
        return f"Successfully subscribed to course {course_id}"
    except sqlite3.IntegrityError:
        return f"You are already subscribed to course {course_id}"
    except Exception as e:
        return f"Error: {str(e)}"

# unsubscribe from a course
def unsubscribe_from_course(username, course_id):
    try:
        cursor.execute("DELETE FROM subscriptions WHERE username=? AND course_id=?", 
                      (username, course_id))
        conn.commit()
        
        # Publish unsubscription event
        event_data = {
            "event_type": "unsubscription",
            "username": username,
            "course_id": course_id
        }
        redis_client.publish(f'course:{course_id}', json.dumps(event_data))
        
        return f"Successfully unsubscribed from course {course_id}"
    except Exception as e:
        return f"Error: {str(e)}"


def get_subscribed_courses(username):
    try:
        cursor.execute("SELECT course_id FROM subscriptions WHERE username=?", (username,))
        courses = cursor.fetchall()
        if not courses:
            return "You are not subscribed to any courses"
        return "|".join([c[0] for c in courses])
    except Exception as e:
        return f"Error: {str(e)}"

# Function to post an announcement
def post_announcement(course_id, message, instructor):
    try:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO announcements (course_id, message, instructor, timestamp) VALUES (?, ?, ?, ?)", 
                      (course_id, message, instructor, timestamp))
        conn.commit()
        event_data = {
            "event_type": "announcement",
            "course_id": course_id,
            "message": message,
            "instructor": instructor,
            "timestamp": timestamp
        }
        redis_client.publish(f'course:{course_id}', json.dumps(event_data))
        redis_client.publish('announcements', json.dumps(event_data))
        
        return "Announcement posted successfully"
    except Exception as e:
        return f"Error: {str(e)}"

def get_course_announcements(course_id):
    try:
        cursor.execute("SELECT message, instructor, timestamp FROM announcements WHERE course_id=? ORDER BY timestamp DESC", 
                      (course_id,))
        announcements = cursor.fetchall()
        if not announcements:
            return "No announcements for this course"
        
        formatted_announcements = []
        for message, instructor, timestamp in announcements:
            formatted_announcements.append(f"[{timestamp}] {instructor}: {message}")
        
        return "|".join(formatted_announcements)
    except Exception as e:
        return f"Error: {str(e)}"

def handle_client(client_socket):
    request = client_socket.recv(1024).decode()
    parts = request.split()
    command = parts[0]
    
    if command == "REGISTER":
        role, username, password = parts[1], parts[2], parts[3]
        response = register_user(role, username, password)
    elif command == "LOGIN":
        username, password = parts[1], parts[2]
        response = login_user(username, password)
    elif command == "GET_COURSES":
        response = get_all_courses()
    elif command == "GET_RESOURCES":
        course_id = parts[1]
        response = get_course_resource(course_id)
    elif command == "UPLOAD_RESOURCE":
        course_id, resource_url, poster_username = parts[1], parts[2], parts[3]
        response = upload_course_resources(course_id, resource_url, poster_username)
    elif command == "SUBSCRIBE":
        username, course_id = parts[1], parts[2]
        response = subscribe_to_course(username, course_id)
    elif command == "UNSUBSCRIBE":
        username, course_id = parts[1], parts[2]
        response = unsubscribe_from_course(username, course_id)
    elif command == "MY_SUBSCRIPTIONS":
        username = parts[1]
        response = get_subscribed_courses(username)
    elif command == "POST_ANNOUNCEMENT":
        course_id, instructor = parts[1], parts[2]
        message = " ".join(parts[3:])
        response = post_announcement(course_id, message, instructor)
    elif command == "GET_ANNOUNCEMENTS":
        course_id = parts[1]
        response = get_course_announcements(course_id)
    else:
        response = "Invalid request!"
    
    client_socket.send(response.encode())
    client_socket.close()

# Start Server
def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("0.0.0.0", 5000))
    server_socket.listen(5)
    print("Server is running on port 5000...")
    
    try:
        while True:
            client_sock, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(client_sock,)).start()
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()