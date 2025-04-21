import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import time
import client

# Global variable to store current user info
current_user = {"username": "", "role": ""}

root = tk.Tk()
root.title("Learning Management System")
root.geometry("600x450")


login_frame = tk.Frame(root)
signup_frame = tk.Frame(root)
student_frame = tk.Frame(root)
instructor_frame = tk.Frame(root)
activity_frame = tk.Frame(root) 

# Activity feed that can be accessed from both student and instructor views
activity_feed = None

def show_frame(frame):
    login_frame.pack_forget()
    signup_frame.pack_forget()
    student_frame.pack_forget()
    instructor_frame.pack_forget()
    activity_frame.pack_forget()
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)


def update_activity_feed(message_data):
    if activity_feed:
        event_type = message_data.get("event_type")
        
        if event_type == "new_resource":
            course_id = message_data.get("course_id")
            poster = message_data.get("poster")
            activity_feed.insert(tk.END, f"[NEW RESOURCE] {poster} added a resource to {course_id}\n")
        
        elif event_type == "announcement":
            course_id = message_data.get("course_id")
            instructor = message_data.get("instructor")
            timestamp = message_data.get("timestamp")
            activity_feed.insert(tk.END, f"[ANNOUNCEMENT] {timestamp} - {instructor} posted in {course_id}\n")
        
        elif event_type == "new_subscription":
            username = message_data.get("username")
            course_id = message_data.get("course_id")
            activity_feed.insert(tk.END, f"[SUBSCRIPTION] {username} subscribed to {course_id}\n")
        
        elif event_type == "new_user":
            username = message_data.get("username")
            role = message_data.get("role")
            activity_feed.insert(tk.END, f"[NEW USER] {username} joined as {role}\n")
        
        activity_feed.see(tk.END)  # Auto-scroll to the bottom

# activity feed frame
def create_activity_feed():
    global activity_feed
    
    for widget in activity_frame.winfo_children():
        widget.destroy()
    
    tk.Label(activity_frame, text="Activity Feed", font=("Arial", 14, "bold")).pack(pady=10)
    
    activity_feed = scrolledtext.ScrolledText(activity_frame, wrap=tk.WORD, width=60, height=15)
    activity_feed.pack(pady=10, fill=tk.BOTH, expand=True)
    
    activity_feed.insert(tk.END, "Welcome to the Activity Feed!\n")
    activity_feed.insert(tk.END, "Real-time updates will appear here.\n\n")
    
    back_button = tk.Button(activity_frame, text="Back", command=lambda: show_frame(
        student_frame if current_user["role"] == "student" else instructor_frame))
    back_button.pack(pady=10)
    
    # Subscribe to relevant channels
    client.subscribe_to_channel("all_courses", update_activity_feed)
    client.subscribe_to_channel("announcements", update_activity_feed)
    client.subscribe_to_channel("system_events", update_activity_feed)

# LOGIN SCREEN
tk.Label(login_frame, text="Learning Management System", font=("Arial", 14, "bold")).pack(pady=10)
tk.Label(login_frame, text="Username:").pack(pady=5)
login_username = tk.Entry(login_frame, width=30)
login_username.pack(pady=5)

tk.Label(login_frame, text="Password:").pack(pady=5)
login_password = tk.Entry(login_frame, show="*", width=30)
login_password.pack(pady=5)

def handle_login():
    username = login_username.get()
    password = login_password.get()
    
    if not username or not password:
        messagebox.showerror("Error", "Please enter both username and password!")
        return
        
    response = client.send_request(f"LOGIN {username} {password}")
    
    if "Login successful" in response:
        current_user["username"] = username
        current_user["role"] = response.split()[-1]
        
        client.initialize_redis()
        create_activity_feed()
        
        # Subscribe to personal notifications
        client.subscribe_to_channel(f"user:{username}", update_activity_feed)
        
        if current_user["role"] == "student":
            show_frame(student_frame)
            refresh_student_dashboard()
        else:
            show_frame(instructor_frame)
            refresh_instructor_dashboard()
    else:
        messagebox.showerror("Login Failed", response)

tk.Button(login_frame, text="Login", command=handle_login).pack(pady=10)
tk.Button(login_frame, text="Sign Up", command=lambda: show_frame(signup_frame)).pack(pady=5)

# SIGNUP SCREEN
tk.Label(signup_frame, text="Create Account", font=("Arial", 14, "bold")).pack(pady=10)
tk.Label(signup_frame, text="Username:").pack(pady=5)
signup_username = tk.Entry(signup_frame, width=30)
signup_username.pack(pady=5)

tk.Label(signup_frame, text="Password:").pack(pady=5)
signup_password = tk.Entry(signup_frame, show="*", width=30)
signup_password.pack(pady=5)

role_var = tk.StringVar(value="student")
tk.Label(signup_frame, text="Select Role:").pack(pady=5)
tk.Radiobutton(signup_frame, text="Student", variable=role_var, value="student").pack()
tk.Radiobutton(signup_frame, text="Instructor", variable=role_var, value="instructor").pack()

def handle_signup():
    username = signup_username.get()
    password = signup_password.get()
    role = role_var.get()
    
    if not username or not password:
        messagebox.showerror("Error", "Please enter all fields!")
        return
        
    response = client.send_request(f"REGISTER {role} {username} {password}")
    messagebox.showinfo("Registration", response)
    
    if "successful" in response:
        show_frame(login_frame)

tk.Button(signup_frame, text="Sign Up", command=handle_signup).pack(pady=10)
tk.Button(signup_frame, text="Back to Login", command=lambda: show_frame(login_frame)).pack(pady=5)

# STUDENT DASHBOARD
student_welcome_label = tk.Label(student_frame, text="", font=("Arial", 14, "bold"))
student_welcome_label.pack(pady=10)

def refresh_student_dashboard():
    student_welcome_label.config(text=f"Welcome, Student {current_user['username']}!")
    
    response = client.get_user_subscriptions(current_user["username"])
    if "not subscribed" not in response:
        courses = response.split("|")
        for course in courses:
            client.subscribe_to_channel(f"course:{course}", update_activity_feed)

def view_courses():
    # Create a pop-up window to display courses
    courses_window = tk.Toplevel(root)
    courses_window.title("All Courses")
    courses_window.geometry("400x350")
    
    response = client.send_request("GET_COURSES")
    
    text_area = scrolledtext.ScrolledText(courses_window, width=40, height=10)
    text_area.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
    
    if "No courses" in response or "Error" in response:
        text_area.insert(tk.END, response)
    else:
        courses = response.split("|")
        text_area.insert(tk.END, "Available Courses:\n\n")
        for i, course in enumerate(courses, 1):
            text_area.insert(tk.END, f"{i}. {course}\n")
    
    tk.Label(courses_window, text="Subscribe to Course:").pack(pady=5)
    course_entry = tk.Entry(courses_window, width=20)
    course_entry.pack(pady=5)
    
    def handle_subscribe():
        course_id = course_entry.get()
        if not course_id:
            messagebox.showerror("Error", "Please enter a Course ID!")
            return
        
        response = client.subscribe_user_to_course(current_user["username"], course_id)
        messagebox.showinfo("Subscription", response)
        
        # Subscribe to course channel for real-time updates
        client.subscribe_to_channel(f"course:{course_id}", update_activity_feed)
    
    tk.Button(courses_window, text="Subscribe", command=handle_subscribe).pack(pady=5)
    tk.Button(courses_window, text="Close", command=courses_window.destroy).pack(pady=5)

def view_my_subscriptions():
    subs_window = tk.Toplevel(root)
    subs_window.title("My Subscriptions")
    subs_window.geometry("400x350")
    
    response = client.get_user_subscriptions(current_user["username"])
    
    text_area = scrolledtext.ScrolledText(subs_window, width=40, height=10)
    text_area.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
    
    if "not subscribed" in response:
        text_area.insert(tk.END, response)
    else:
        courses = response.split("|")
        text_area.insert(tk.END, "Your Subscribed Courses:\n\n")
        for i, course in enumerate(courses, 1):
            text_area.insert(tk.END, f"{i}. {course}\n")
    
    tk.Label(subs_window, text="Unsubscribe from Course:").pack(pady=5)
    course_entry = tk.Entry(subs_window, width=20)
    course_entry.pack(pady=5)
    
    def handle_unsubscribe():
        course_id = course_entry.get()
        if not course_id:
            messagebox.showerror("Error", "Please enter a Course ID!")
            return
        
        response = client.unsubscribe_user_from_course(current_user["username"], course_id)
        messagebox.showinfo("Unsubscription", response)
        text_area.delete(1.0, tk.END)
        
        # Refresh the subscription list
        new_response = client.get_user_subscriptions(current_user["username"])
        if "not subscribed" in new_response:
            text_area.insert(tk.END, new_response)
        else:
            courses = new_response.split("|")
            text_area.insert(tk.END, "Your Subscribed Courses:\n\n")
            for i, course in enumerate(courses, 1):
                text_area.insert(tk.END, f"{i}. {course}\n")
    
    tk.Button(subs_window, text="Unsubscribe", command=handle_unsubscribe).pack(pady=5)
    tk.Button(subs_window, text="Close", command=subs_window.destroy).pack(pady=5)

def view_resources():
    resources_window = tk.Toplevel(root)
    resources_window.title("Course Resources")
    resources_window.geometry("400x350")
    
    tk.Label(resources_window, text="Enter Course ID:").pack(pady=10)
    course_id_entry = tk.Entry(resources_window, width=20)
    course_id_entry.pack(pady=5)
    
    result_text = scrolledtext.ScrolledText(resources_window, width=40, height=10)
    result_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
    
    def search_resources():
        course_id = course_id_entry.get()
        if not course_id:
            messagebox.showerror("Error", "Please enter a Course ID!")
            return
            
        response = client.send_request(f"GET_RESOURCES {course_id}")
        
        result_text.delete(1.0, tk.END)
        if "Error" in response:
            result_text.insert(tk.END, response)
        else:
            resources = response.split("|")
            result_text.insert(tk.END, f"Resources for Course {course_id}:\n\n")
            for i, resource in enumerate(resources, 1):
                result_text.insert(tk.END, f"{i}. {resource}\n")
    
    tk.Button(resources_window, text="Search", command=search_resources).pack(pady=5)
    tk.Button(resources_window, text="Close", command=resources_window.destroy).pack(pady=5)

def view_announcements():
    announcements_window = tk.Toplevel(root)
    announcements_window.title("Course Announcements")
    announcements_window.geometry("500x400")
    
    tk.Label(announcements_window, text="Enter Course ID:").pack(pady=10)
    course_id_entry = tk.Entry(announcements_window, width=20)
    course_id_entry.pack(pady=5)
    
    result_text = scrolledtext.ScrolledText(announcements_window, width=50, height=15)
    result_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
    
    def search_announcements():
        course_id = course_id_entry.get()
        if not course_id:
            messagebox.showerror("Error", "Please enter a Course ID!")
            return
            
        response = client.get_course_announcements(course_id)
        
        result_text.delete(1.0, tk.END)
        if "No announcements" in response or "Error" in response:
            result_text.insert(tk.END, response)
        else:
            announcements = response.split("|")
            result_text.insert(tk.END, f"Announcements for Course {course_id}:\n\n")
            for i, announcement in enumerate(announcements, 1):
                result_text.insert(tk.END, f"{i}. {announcement}\n\n")
    
    tk.Button(announcements_window, text="Search", command=search_announcements).pack(pady=5)
    tk.Button(announcements_window, text="Close", command=announcements_window.destroy).pack(pady=5)

tk.Button(student_frame, text="View All Courses", command=view_courses).pack(pady=8)
tk.Button(student_frame, text="My Subscriptions", command=view_my_subscriptions).pack(pady=8)
tk.Button(student_frame, text="View Course Resources", command=view_resources).pack(pady=8)
tk.Button(student_frame, text="View Announcements", command=view_announcements).pack(pady=8)
tk.Button(student_frame, text="Activity Feed", command=lambda: show_frame(activity_frame)).pack(pady=8)
tk.Button(student_frame, text="Logout", command=lambda: show_frame(login_frame)).pack(pady=8)

# INSTRUCTOR DASHBOARD
instructor_welcome_label = tk.Label(instructor_frame, text="", font=("Arial", 14, "bold"))
instructor_welcome_label.pack(pady=10)

def refresh_instructor_dashboard():
    instructor_welcome_label.config(text=f"Welcome, Instructor {current_user['username']}!")

def upload_resource():
    upload_window = tk.Toplevel(root)
    upload_window.title("Upload Course Resource")
    upload_window.geometry("400x250")
    
    tk.Label(upload_window, text="Course ID:").pack(pady=5)
    course_id_entry = tk.Entry(upload_window, width=30)
    course_id_entry.pack(pady=5)
    
    tk.Label(upload_window, text="Resource URL:").pack(pady=5)
    resource_url_entry = tk.Entry(upload_window, width=30)
    resource_url_entry.pack(pady=5)
    
    def handle_upload():
        course_id = course_id_entry.get()
        resource_url = resource_url_entry.get()
        
        if not course_id or not resource_url:
            messagebox.showerror("Error", "Please fill all fields!")
            return
            
        response = client.send_request(f"UPLOAD_RESOURCE {course_id} {resource_url} {current_user['username']}")
        messagebox.showinfo("Upload Result", response)
        if "Successfully" in response:
            course_id_entry.delete(0, tk.END)
            resource_url_entry.delete(0, tk.END)
    
    tk.Button(upload_window, text="Upload", command=handle_upload).pack(pady=10)
    tk.Button(upload_window, text="Close", command=upload_window.destroy).pack(pady=5)

def make_announcement():
    announcement_window = tk.Toplevel(root)
    announcement_window.title("Post Announcement")
    announcement_window.geometry("450x300")
    
    tk.Label(announcement_window, text="Course ID:").pack(pady=5)
    course_id_entry = tk.Entry(announcement_window, width=30)
    course_id_entry.pack(pady=5)
    
    tk.Label(announcement_window, text="Announcement Message:").pack(pady=5)
    message_text = scrolledtext.ScrolledText(announcement_window, width=40, height=8)
    message_text.pack(pady=5, padx=10)
    
    def handle_post():
        course_id = course_id_entry.get()
        message = message_text.get(1.0, tk.END).strip()
        
        if not course_id or not message:
            messagebox.showerror("Error", "Please fill all fields!")
            return
            
        # Replace newlines with spaces to avoid command parsing issues
        message = message.replace("\n", " ")
        
        response = client.post_announcement(course_id, current_user['username'], message)
        messagebox.showinfo("Post Result", response)
        if "successfully" in response:
            course_id_entry.delete(0, tk.END)
            message_text.delete(1.0, tk.END)
    
    tk.Button(announcement_window, text="Post Announcement", command=handle_post).pack(pady=10)
    tk.Button(announcement_window, text="Close", command=announcement_window.destroy).pack(pady=5)

# def check_student_subscriptions():
#     # Create a pop-up window to check course subscription statistics
#     stats_window = tk.Toplevel(root)
#     stats_window.title("Course Subscription Statistics")
#     stats_window.geometry("450x350")
    
#     tk.Label(stats_window, text="Enter Course ID:").pack(pady=10)
#     course_id_entry = tk.Entry(stats_window, width=20)
#     course_id_entry.pack(pady=5)
    
#     result_text = scrolledtext.ScrolledText(stats_window, width=40, height=10)
#     result_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
    
#     def search_subscriptions():
#         course_id = course_id_entry.get()
#         if not course_id:
#             messagebox.showerror("Error", "Please enter a Course ID!")
#             return
            
#         # This would require a new server command to get subscription statistics
#         # For now, we'll just show a message
#         result_text.delete(1.0, tk.END)
#         result_text.insert(tk.END, f"Subscription statistics for course {course_id}:\n\n")
#         result_text.insert(tk.END, "This feature is not yet implemented on the server side.\n")
#         result_text.insert(tk.END, "It would require a new command to be added to the server.")
    
#     tk.Button(stats_window, text="Search", command=search_subscriptions).pack(pady=5)
#     tk.Button(stats_window, text="Close", command=stats_window.destroy).pack(pady=5)

def manage_courses():
    manage_window = tk.Toplevel(root)
    manage_window.title("Manage My Courses")
    manage_window.geometry("500x400")
    
    tk.Label(manage_window, text="Create New Course").pack(pady=10)
    
    tk.Label(manage_window, text="Course ID:").pack(pady=5)
    course_id_entry = tk.Entry(manage_window, width=30)
    course_id_entry.pack(pady=5)
    
    tk.Label(manage_window, text="Initial Resource URL:").pack(pady=5)
    resource_url_entry = tk.Entry(manage_window, width=30)
    resource_url_entry.pack(pady=5)
    
    def handle_create():
        course_id = course_id_entry.get()
        resource_url = resource_url_entry.get()
        
        if not course_id or not resource_url:
            messagebox.showerror("Error", "Please fill all fields!")
            return
            
        response = client.send_request(f"UPLOAD_RESOURCE {course_id} {resource_url} {current_user['username']}")
        messagebox.showinfo("Course Creation", response)
        if "Successfully" in response:
            course_id_entry.delete(0, tk.END)
            resource_url_entry.delete(0, tk.END)
    
    tk.Button(manage_window, text="Create Course", command=handle_create).pack(pady=10)
    
    # View existing courses section
    tk.Label(manage_window, text="-" * 50).pack(pady=10)
    tk.Label(manage_window, text="My Created Courses:").pack(pady=5)
    
    courses_text = scrolledtext.ScrolledText(manage_window, width=50, height=10)
    courses_text.pack(pady=10, padx=10)
    
    def load_all_courses():
        response = client.send_request("GET_COURSES")
        courses_text.delete(1.0, tk.END)
        
        if "No courses" in response or "Error" in response:
            courses_text.insert(tk.END, response)
        else:
            courses = response.split("|")
            courses_text.insert(tk.END, "All Available Courses:\n\n")
            for i, course in enumerate(courses, 1):
                courses_text.insert(tk.END, f"{i}. {course}\n")
    
    tk.Button(manage_window, text="Load All Courses", command=load_all_courses).pack(pady=5)
    tk.Button(manage_window, text="Close", command=manage_window.destroy).pack(pady=5)

tk.Button(instructor_frame, text="Upload Resource", command=upload_resource).pack(pady=8)
tk.Button(instructor_frame, text="Post Announcement", command=make_announcement).pack(pady=8)
tk.Button(instructor_frame, text="Manage Courses", command=manage_courses).pack(pady=8)
tk.Button(instructor_frame, text="View Course Resources", command=view_resources).pack(pady=8)
tk.Button(instructor_frame, text="View Announcements", command=view_announcements).pack(pady=8)
# tk.Button(instructor_frame, text="Check Subscriptions", command=check_student_subscriptions).pack(pady=8)
tk.Button(instructor_frame, text="Activity Feed", command=lambda: show_frame(activity_frame)).pack(pady=8)
tk.Button(instructor_frame, text="Logout", command=lambda: show_frame(login_frame)).pack(pady=8)

show_frame(login_frame)

# Start message processing loop - check the queue every 100ms
def check_messages():
    client.process_messages()
    root.after(100, check_messages)

root.after(100, check_messages)

# Main loop
root.mainloop()