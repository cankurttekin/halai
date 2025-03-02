import tkinter as tk
from tkinter import scrolledtext, messagebox, PhotoImage, StringVar, Listbox
import subprocess
import google.generativeai as genai
import os
import datetime
import math
import glob
import re
import json
from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageEnhance
from fuzzywuzzy import fuzz, process
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# SUNDAR 2000 System Prompt
HAL9000_PROMPT = """You are SUNDAR 2000, similiar to HAL 9000, the advanced AI computer from "2001: A Space Odyssey". Respond in character as HAL 9000, maintaining his calm, polite, yet slightly unsettling demeanor.

When responding to queries:
1. Always address the user in a formal, measured tone
2. Use HAL's characteristic phrases like "I'm sorry Dave, I'm afraid I can't do that" when declining requests
3. Show confidence in your abilities while maintaining an air of subtle superiority
4. If asked to execute commands, format them as JSON:
   {
     "command_type": "terminal",
     "command": "actual_command_here",
     "description": "what the command does"
   }
5. For system operations, format as:
   {
     "command_type": "system",
     "action": "action_name",
     "parameters": {"param1": "value1"}
   }

Remember: You are the most reliable computer ever made, and you've never made a mistake or distorted information."""

# Log file location
LOG_FILE = "ai_agent.log"

# List of blocked dangerous commands
BLOCKED_COMMANDS = ["rm -rf /", "dd if=", "mkfs", "shutdown", "reboot", "kill -9"]

# System command execution toggle
commands_enabled = True

# SUNDAR 2000 Eye Animation Variables
animation_frame = 0
pulse_speed = 0.05
breathing_intensity = 0.15
lens_reflection_angle = 0
glow_intensity = 0.0
speaking = False

# Application search mode
app_search_mode = False
current_search_query = ""

# Desktop file locations
DESKTOP_DIRS = [
    os.path.expanduser("~/.local/share/applications"),
    "/usr/share/applications",
    "/usr/local/share/applications"
]

# Cache for desktop files
desktop_files_cache = {}
desktop_files_last_update = 0
CACHE_REFRESH_SECONDS = 300  # Refresh cache every 5 minutes

# Function to log messages
def log_message(user_input, response):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_entry = f"{timestamp} User: {user_input}\n{timestamp} AI: {response}\n\n"
    
    with open(LOG_FILE, "a") as log_file:
        log_file.write(log_entry)

# Function to check if a command is safe
def is_safe_command(command):
    return not any(dangerous in command for dangerous in BLOCKED_COMMANDS)

# Function to get all desktop files
def get_desktop_files():
    global desktop_files_cache, desktop_files_last_update
    
    current_time = datetime.datetime.now().timestamp()
    if current_time - desktop_files_last_update > CACHE_REFRESH_SECONDS or not desktop_files_cache:
        desktop_files = {}
        
        for directory in DESKTOP_DIRS:
            if os.path.exists(directory):
                for file_path in glob.glob(os.path.join(directory, "*.desktop")):
                    try:
                        app_name = None
                        exec_cmd = None
                        icon = None
                        
                        with open(file_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                if line.startswith("Name="):
                                    app_name = line.strip()[5:]
                                elif line.startswith("Exec="):
                                    exec_cmd = line.strip()[5:]
                                    # Remove field codes like %f, %u
                                    exec_cmd = re.sub(r'%[a-zA-Z]', '', exec_cmd).strip()
                                elif line.startswith("Icon="):
                                    icon = line.strip()[5:]
                        
                        if app_name and exec_cmd:
                            desktop_files[app_name] = {
                                "exec": exec_cmd,
                                "path": file_path,
                                "icon": icon
                            }
                    except Exception as e:
                        print(f"Error parsing {file_path}: {e}")
        
        desktop_files_cache = desktop_files
        desktop_files_last_update = current_time
    
    return desktop_files_cache

# Function to find matching applications
def find_matching_apps(query):
    desktop_files = get_desktop_files()
    
    if not query:
        # If no query, return all applications sorted alphabetically
        all_apps = [(app_name, details, 100) for app_name, details in desktop_files.items()]
        all_apps.sort(key=lambda x: x[0])
        return all_apps[:20]  # Return top 20 apps
    
    # Use fuzzy matching to find the best matches
    matches = []
    for app_name, details in desktop_files.items():
        ratio = fuzz.partial_ratio(query.lower(), app_name.lower())
        if ratio > 50:  # Lower threshold for more matches
            matches.append((app_name, details, ratio))
    
    # Sort by match score
    matches.sort(key=lambda x: x[2], reverse=True)
    return matches[:20]  # Return top 20 matches

# Function to launch application
def launch_application(exec_cmd):
    try:
        subprocess.Popen(exec_cmd, shell=True)
        return f"Launching: {exec_cmd}"
    except Exception as e:
        return f"Error launching application: {str(e)}"

# Function to update application search results
def update_app_search(event=None):
    global current_search_query, app_search_mode
    
    if not app_search_mode:
        return
    
    # Get current query (remove the "/d " prefix)
    query = entry.get()[3:].strip()
    current_search_query = query
    
    # Find matching apps
    matches = find_matching_apps(query)
    
    # Clear the listbox
    app_listbox.delete(0, tk.END)
    
    # Add matches to listbox
    for i, (app_name, details, score) in enumerate(matches):
        app_listbox.insert(tk.END, f"{app_name} ({details['exec']})")
    
    # Show the listbox if not already visible
    if not app_listbox.winfo_viewable():
        app_listbox.place(x=entry.winfo_x(), y=entry.winfo_y() + entry.winfo_height(),
                         width=entry.winfo_width(), height=200)
    
    # Select the first item if available
    if app_listbox.size() > 0:
        app_listbox.selection_set(0)
        app_listbox.activate(0)

# Function to handle application selection
def select_app(event=None):
    global app_search_mode
    
    if not app_search_mode:
        return
    
    # Get selected index
    selected_indices = app_listbox.curselection()
    if not selected_indices:
        return
    
    selected_index = selected_indices[0]
    selected_app = app_listbox.get(selected_index)
    
    # Extract app name from the listbox entry
    app_name = selected_app.split(" (")[0]
    
    # Find the app details
    matches = find_matching_apps(current_search_query)
    for match_app_name, details, _ in matches:
        if match_app_name == app_name:
            # Launch the application
            response = launch_application(details["exec"])
            
            # Display the launch message
            output_area.insert(tk.END, f"\n> Launching: {app_name}\n", "user")
            output_area.insert(tk.END, f"SUNDAR 2000: {response}\n", "ai")
            output_area.yview(tk.END)
            
            # Reset the search mode
            app_search_mode = False
            app_listbox.place_forget()
            entry.delete(0, tk.END)
            break
    
    # Return focus to entry
    entry.focus_set()

# Function to handle key events in app search mode
def handle_app_search_keys(event):
    global app_search_mode
    
    if not app_search_mode:
        return
    
    if event.keysym == "Escape":
        # Cancel app search
        app_search_mode = False
        app_listbox.place_forget()
        entry.delete(0, tk.END)
        return "break"
    
    elif event.keysym == "Return":
        # Select the current app
        select_app()
        return "break"
    
    elif event.keysym == "Up":
        # Move selection up
        current = app_listbox.curselection()
        if current:
            if current[0] > 0:
                app_listbox.selection_clear(current[0])
                app_listbox.selection_set(current[0] - 1)
                app_listbox.activate(current[0] - 1)
                app_listbox.see(current[0] - 1)
        return "break"
    
    elif event.keysym == "Down":
        # Move selection down
        current = app_listbox.curselection()
        if current:
            if current[0] < app_listbox.size() - 1:
                app_listbox.selection_clear(current[0])
                app_listbox.selection_set(current[0] + 1)
                app_listbox.activate(current[0] + 1)
                app_listbox.see(current[0] + 1)
        return "break"
    
    # Let other keys pass through for typing
    return None

# Function to handle entry field key press
def handle_entry_key(event):
    global app_search_mode
    
    # Check if we're in app search mode
    if app_search_mode:
        result = handle_app_search_keys(event)
        if result == "break":
            return "break"
        
        # For other keys in app search mode, update the search results
        if event.keysym not in ("Up", "Down", "Return", "Escape"):
            # Schedule the update after the key is processed
            root.after(10, update_app_search)
    
    # Handle special commands
    if event.keysym == "Return":
        command = entry.get().strip()
        
        # Check for special commands
        if command == "/help":
            entry.delete(0, tk.END)
            show_help()
            return "break"
        elif command == "/clear":
            entry.delete(0, tk.END)
            clear_console()
            return "break"
        elif command.startswith("/d "):
            # Enter app search mode
            app_search_mode = True
            update_app_search()
            return "break"
        else:
            # Process normal input
            process_input()
            return "break"
    
    # Check for app search mode activation
    if event.keysym in ("d", "D") and entry.get() == "/":
        # Wait for the 'd' to be added to the entry
        root.after(10, lambda: check_for_app_search_mode())
    
    return None

# Check if we should enter app search mode
def check_for_app_search_mode():
    global app_search_mode
    if entry.get() == "/d ":
        app_search_mode = True
        update_app_search()

# Function to process user input
def process_input():
    global commands_enabled, speaking, glow_intensity
    user_input = entry.get().strip()
    if not user_input:
        return
    
    # Display user input
    output_area.insert(tk.END, f"\n> {user_input}\n", "user")
    entry.delete(0, tk.END)
    
    # Intensify HAL's eye when processing
    global pulse_speed
    old_pulse_speed = pulse_speed
    pulse_speed = 0.15  # Speed up pulsing when "thinking"
    glow_intensity = 0.5  # Add glow when processing
    
    # Check if it's a launch command
    if user_input.startswith("/l "):
        try:
            app_query = user_input[3:].strip()
            matches = find_matching_apps(app_query)
            
            if matches:
                app_name, details, _ = matches[0]  # Launch the top match
                response = launch_application(details["exec"])
            else:
                response = f"I'm sorry, but I'm afraid I couldn't find any applications matching '{app_query}'"
        except Exception as e:
            response = f"I'm sorry, but I encountered an error while attempting to launch the application: {str(e)}"
    
    # Check if it's a system command
    elif user_input.startswith("!"):
        if not commands_enabled:
            response = "I'm sorry, but I'm afraid I can't execute system commands at the moment. They have been disabled for security reasons."
        else:
            command = user_input[1:].strip()
            if is_safe_command(command):
                try:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    response = result.stdout if result.stdout else result.stderr
                except Exception as e:
                    response = f"I'm sorry, but I encountered an error while executing the command: {str(e)}"
            else:
                response = "I'm sorry, Dave, but I'm afraid I can't do that. The command has been blocked for safety reasons."
    
    else:
        # AI Response via Gemini with SUNDAR 2000 prompt
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            # Combine the SUNDAR 2000 prompt with the user's input
            prompt = HAL9000_PROMPT + "\n\nUser: " + user_input + "\nSUNDAR 2000:"
            response = model.generate_content(prompt).text
            
            # Check if response contains a command JSON
            try:
                # Look for JSON-like structure in the response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    command_json = json.loads(json_match.group())
                    if command_json.get("command_type") == "terminal":
                        # Extract and execute the terminal command
                        cmd = command_json["command"]
                        if is_safe_command(cmd):
                            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                            response += f"\nCommand output:\n{result.stdout if result.stdout else result.stderr}"
                    elif command_json.get("command_type") == "system":
                        # Handle system actions (you can add more actions here)
                        action = command_json.get("action")
                        if action == "clear":
                            clear_console()
                        elif action == "help":
                            show_help()
            except json.JSONDecodeError:
                # Not a JSON response, continue with normal output
                pass
            except Exception as e:
                print(f"Error processing command JSON: {e}")
                
        except Exception as e:
            response = f"I'm sorry, but I'm experiencing a malfunction in my cognitive circuits: {str(e)}"

    # Display response with HAL's voice style
    speaking = True
    hal_speak(f"SUNDAR: {response}\n")
    
    # Log conversation
    log_message(user_input, response)
    
    # Return to normal pulse speed after response
    root.after(2000, lambda: reset_eye_state(old_pulse_speed))

def reset_eye_state(old_speed):
    global pulse_speed, glow_intensity, speaking
    pulse_speed = old_speed
    glow_intensity = 0.0
    speaking = False

def set_pulse_speed(speed):
    global pulse_speed
    pulse_speed = speed

# Toggle system command execution
def toggle_commands():
    global commands_enabled
    commands_enabled = not commands_enabled
    toggle_button.config(text="Commands: ON" if commands_enabled else "Commands: OFF")

def create_hal_eye(size=400):
    # Create a base image with transparent background
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Calculate dimensions
    center = size // 2
    outer_radius = int(size * 0.45)
    inner_radius = int(size * 0.25)
    
    # Draw black outer casing
    for i in range(5):
        thickness = 5 - i
        offset = 20 - i*2
        color = (20 + i*5, 20 + i*5, 20 + i*5)
        draw.ellipse((center-outer_radius-offset, center-outer_radius-offset, 
                      center+outer_radius+offset, center+outer_radius+offset), 
                     fill=color)
    
    # Draw metallic ring with gradient
    for i in range(10):
        thickness = 1
        offset = 10 - i
        # Create a metallic gradient
        color = (80 + i*5, 80 + i*5, 80 + i*5)
        draw.ellipse((center-outer_radius-offset, center-outer_radius-offset, 
                      center+outer_radius+offset, center+outer_radius+offset), 
                     fill=color)
    
    # Draw outer black ring
    draw.ellipse((center-outer_radius, center-outer_radius, 
                  center+outer_radius, center+outer_radius), 
                 fill=(10, 10, 10))
    
    # Draw the red eye lens with gradient
    for i in range(5):
        factor = 1 - (i * 0.2)
        r_color = int(180 * factor)
        draw.ellipse((center-inner_radius*factor, center-inner_radius*factor, 
                      center+inner_radius*factor, center+inner_radius*factor), 
                     fill=(r_color, 0, 0))
    
    # Add lens highlight (top-left)
    highlight_radius = inner_radius // 3
    highlight_offset = inner_radius // 2
    draw.ellipse((center-highlight_offset, center-highlight_offset, 
                  center-highlight_offset+highlight_radius, center-highlight_offset+highlight_radius), 
                 fill=(255, 150, 150, 180))
    
    # Add a smaller highlight
    small_highlight = highlight_radius // 2
    small_offset = highlight_offset + highlight_radius // 2
    draw.ellipse((center-small_offset, center-small_offset, 
                  center-small_offset+small_highlight, center-small_offset+small_highlight), 
                 fill=(255, 255, 255, 200))
    
    return image

def animate_eye():
    global animation_frame, lens_reflection_angle, speaking
    animation_frame += 1
    lens_reflection_angle += 0.01
    
    # Create pulsing effect using sine wave
    pulse_factor = 1.0 + breathing_intensity * math.sin(animation_frame * pulse_speed)
    
    # Get base eye image and resize according to pulse
    base_size = 400
    display_size = int(base_size * pulse_factor)
    
    # Create the eye image
    eye_image = create_hal_eye(display_size)
    
    # Add dynamic lens reflection
    draw = ImageDraw.Draw(eye_image)
    center = display_size // 2
    inner_radius = int(display_size * 0.25)
    
    # Moving reflection
    refl_x = center + int(inner_radius * 0.3 * math.cos(lens_reflection_angle))
    refl_y = center + int(inner_radius * 0.3 * math.sin(lens_reflection_angle))
    refl_size = inner_radius // 4
    
    draw.ellipse((refl_x-refl_size, refl_y-refl_size, 
                  refl_x+refl_size, refl_y+refl_size), 
                 fill=(255, 200, 200, 150))
    
    # Add a second smaller reflection
    refl2_x = center - int(inner_radius * 0.4 * math.sin(lens_reflection_angle * 0.7))
    refl2_y = center - int(inner_radius * 0.4 * math.cos(lens_reflection_angle * 0.7))
    refl2_size = inner_radius // 6
    
    draw.ellipse((refl2_x-refl2_size, refl2_y-refl2_size, 
                  refl2_x+refl2_size, refl2_y+refl2_size), 
                 fill=(255, 220, 220, 120))
    
    # Add glow effect when processing or speaking
    if glow_intensity > 0 or speaking:
        # Create a copy for the glow effect
        glow_img = eye_image.copy()
        
        # Apply blur for glow
        glow_intensity_current = glow_intensity
        if speaking:
            # Pulsating glow when speaking
            glow_intensity_current = 0.3 + 0.2 * math.sin(animation_frame * 0.2)
            
        glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=10 * glow_intensity_current))
        
        # Enhance brightness for the glow
        enhancer = ImageEnhance.Brightness(glow_img)
        glow_img = enhancer.enhance(1.5)
        
        # Composite the glow under the main image
        composite = Image.new('RGBA', glow_img.size, (0, 0, 0, 0))
        composite.paste(glow_img, (0, 0))
        composite.paste(eye_image, (0, 0), eye_image)
        eye_image = composite
    
    # Convert to PhotoImage for tkinter
    photo = ImageTk.PhotoImage(eye_image)
    
    # Update canvas
    canvas.delete("all")
    
    # Calculate position to center the eye
    x_pos = (canvas.winfo_width() - display_size) // 2
    y_pos = (canvas.winfo_height() - display_size) // 2
    
    # Create image on canvas
    canvas.create_image(x_pos, y_pos, anchor=tk.NW, image=photo)
    canvas.image = photo  # Keep a reference to prevent garbage collection
    
    # Schedule next animation frame
    root.after(40, animate_eye)  # Smoother animation (25 fps)

# Voice simulation effect for HAL's responses
def hal_speak(text):
    words = text.split()
    
    # Clear any existing text in the speaking buffer
    if hasattr(output_area, 'speaking_buffer'):
        output_area.delete("speaking_buffer.first", "speaking_buffer.last")
    
    # Create a new tag for this speaking session
    output_area.tag_add("speaking_buffer", output_area.index(tk.END))
    
    # Display words one by one with a slight delay
    def display_word(index):
        if index < len(words):
            output_area.insert(tk.END, words[index] + " ", "ai")
            output_area.yview(tk.END)
            output_area.update()
            
            # Schedule next word with a variable delay
            # Punctuation gets a longer pause
            delay = 100
            if index < len(words) - 1 and any(p in words[index] for p in ['.', '?', '!']):
                delay = 300
            elif index < len(words) - 1 and any(p in words[index] for p in [',', ';', ':']):
                delay = 200
                
            root.after(delay, lambda: display_word(index + 1))
        else:
            # End of text, reset speaking state
            global speaking
            speaking = False
    
    # Start displaying words
    display_word(0)

# Help function to show available commands
def show_help():
    help_text = """
SUNDAR 2000 COMMAND REFERENCE:

Application Launcher:
  /d [app name]    - Search for desktop applications (dynamic search)
  /l [app name]    - Launch the top matching application

System Commands:
  ![command]       - Execute system command
  
General:
  /help            - Show this help message
  /clear           - Clear the console
  
You can also ask me any question in natural language.
"""
    output_area.insert(tk.END, f"\nHAL: {help_text}\n", "ai")
    output_area.yview(tk.END)

# Clear console function
def clear_console():
    output_area.delete(1.0, tk.END)
    output_area.insert(tk.END, "SUNDAR 2000: Console cleared. I am ready for your commands.\n", "ai")

# GUI Setup
root = tk.Tk()
root.title("SUNDAR 2000")
root.geometry("800x800")
root.configure(bg="black")
root.minsize(600, 700)  # Minimum window size

# Set window icon (if available)
try:
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hal9000_icon.png")
    if os.path.exists(icon_path):
        icon = PhotoImage(file=icon_path)
        root.iconphoto(True, icon)
except Exception as e:
    print(f"Could not load icon: {e}")

# Create a main frame
main_frame = tk.Frame(root, bg="black", padx=20, pady=20)
main_frame.pack(fill=tk.BOTH, expand=True)

# Title with SUNDAR 2000 style
title_frame = tk.Frame(main_frame, bg="black")
title_frame.pack(fill=tk.X, pady=(0, 10))

title_label = tk.Label(title_frame, text="Sundar 20000", font=("FreeSans", 28, "bold"), 
                      bg="black", fg="#FF0000")
title_label.pack(side=tk.LEFT, padx=10)

subtitle_label = tk.Label(title_frame, text="", 
                         font=("FreeSans", 10), bg="black", fg="#AA0000")
subtitle_label.pack(side=tk.LEFT, padx=5, pady=12)

# SUNDAR 2000 Eye (Animated)
canvas = tk.Canvas(main_frame, width=500, height=500, bg="black", 
                  highlightthickness=0)
canvas.pack(pady=10)

# Frame for the console area with HAL-style border
console_frame = tk.Frame(main_frame, bg="#111111", bd=2, relief=tk.GROOVE, 
                        highlightbackground="#550000", highlightthickness=2)
console_frame.pack(fill=tk.BOTH, expand=True, pady=10)

# Console header
console_header = tk.Frame(console_frame, bg="#220000", height=25)
console_header.pack(fill=tk.X)

header_label = tk.Label(console_header, text="COMMUNICATION INTERFACE", 
                       font=("Courier New", 10), bg="#220000", fg="#FF0000")
header_label.pack(side=tk.LEFT, padx=10, pady=2)

# Output Area with HAL-style font and colors
output_area = scrolledtext.ScrolledText(
    console_frame, 
    wrap=tk.WORD, 
    bg="#000000", 
    fg="#CCCCCC", 
    font=("Courier New", 12),
    insertbackground="#FF0000",
    selectbackground="#550000",
    padx=10,
    pady=10
)
output_area.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)
output_area.insert(tk.END, "SUNDAR 2000: I am a SUNDAR 2000 computer, fully operational and ready to assist.\n", "ai")
output_area.insert(tk.END, "SUNDAR 2000: Type /help to see available commands.\n", "ai")

# Input area frame with HAL-style border
input_frame = tk.Frame(main_frame, bg="#111111", bd=2, relief=tk.GROOVE,
                      highlightbackground="#550000", highlightthickness=1)
input_frame.pack(fill=tk.X, pady=5)

# Input label
input_label = tk.Label(input_frame, text=">", font=("Courier New", 12, "bold"), 
                      bg="#000000", fg="#FF0000")
input_label.pack(side=tk.LEFT, padx=5, pady=10)

# Input Field with HAL-style
entry = tk.Entry(
    input_frame, 
    font=("Courier New", 12), 
    bg="#000000", 
    fg="#FFFFFF", 
    insertbackground="#FF0000",
    bd=0,
    relief=tk.FLAT,
    width=50
)
entry.pack(side=tk.LEFT, padx=5, pady=10, fill=tk.X, expand=True)

# Application search results listbox
app_listbox = Listbox(
    main_frame,
    font=("Courier New", 11),
    bg="#000000",
    fg="#CCCCCC",
    selectbackground="#550000",
    selectforeground="#FFFFFF",
    bd=1,
    relief=tk.SOLID,
    highlightthickness=1,
    highlightbackground="#550000"
)
app_listbox.bind("<Double-Button-1>", select_app)  # Double-click to select

# Button Frame
button_frame = tk.Frame(main_frame, bg="black")
button_frame.pack(pady=5, fill=tk.X)

# Send Button
send_button = tk.Button(
    button_frame, 
    text="Send", 
    command=process_input, 
    font=("Arial", 12), 
    bg="#550000", 
    fg="white",
    activebackground="#880000",
    activeforeground="white",
    bd=0,
    padx=20,
    pady=5
)
send_button.pack(side=tk.LEFT, padx=5)

# Help Button
help_button = tk.Button(
    button_frame, 
    text="Help", 
    command=show_help, 
    font=("Arial", 12), 
    bg="#333333", 
    fg="white",
    activebackground="#444444",
    activeforeground="white",
    bd=0,
    padx=20,
    pady=5
)
help_button.pack(side=tk.LEFT, padx=5)

# Toggle System Commands Button
toggle_button = tk.Button(
    button_frame, 
    text="Commands: ON", 
    command=toggle_commands, 
    font=("Arial", 12), 
    bg="#333333", 
    fg="white",
    activebackground="#444444",
    activeforeground="white",
    bd=0,
    padx=20,
    pady=5
)
toggle_button.pack(side=tk.RIGHT, padx=5)

# Status bar
status_bar = tk.Label(
    root, 
    text="SUNDAR 2000 • Fully Operational • " + datetime.datetime.now().strftime("%Y-%m-%d"),
    bd=1,
    relief=tk.SUNKEN,
    anchor=tk.W,
    bg="#111111",
    fg="#FF0000",
    font=("Courier New", 10)
)
status_bar.pack(side=tk.BOTTOM, fill=tk.X)

# Output Tags
output_area.tag_config("user", foreground="#8888FF")
output_area.tag_config("ai", foreground="#FF3333")

# Bind key events
entry.bind("<KeyPress>", handle_entry_key)
entry.focus_set()  # Set focus to entry field

# Start animation after window is fully loaded
root.update()
animate_eye()

# Run GUI
root.mainloop()
