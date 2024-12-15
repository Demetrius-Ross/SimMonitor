import tkinter as tk
import time
import serial
import sys
import os
from tkinter import PhotoImage
from PIL import Image, ImageTk

#creates a buffer for serial data reading
cwd = os.getcwd()


#Manual set screen resolution
#screenx = 1920
#screeny = 1080
# Initial Coordinates for images
print("Hello and welcome to Sim Monitor Debug: ")
print("starting program please wait: ")


#image position
image_x, image_y = 0, 0


# List of labels
Sim_Position = ["Simulator Motion is: Off", "Simulator Motion is: ON"]
ramp_Position = ["Ramp State is: Down", "Ramp State is: up"]
sim_status = ["Connection Secured", "Data Not Recieved yet"]
print("Labels loaded Ln20")


#----------------------------------------------
#This creates the Tkinter generation enviorment
root = tk.Tk()
#set title to program
root.title("Sim Monitor v1")
#Hide the screen
#root.withdraw()
# Create the main background for program
canvas = tk.Canvas(root, width = 1920, height = 1080, bg="green")
#here you can insert a custom image for the background, remove the next 3 "#" and set your files
#background_image = Image.open("background.png")  # Replace with your image file
#background_image = ImageTk.PhotoImage(background_image)
#canvas.create_image(0, 0, anchor="nw", image=background_image)
canvas.pack()
#-----------------------------------------------
#Automatic screen resoltion
print("started root program initiated image assignment ln 37")
screenx = root.winfo_screenwidth()
screeny = root.winfo_screenheight()

#here we create the ratio's for the blocks using the screen resol
pixelratiox = screenx / 6
pixelratioy = screeny / 2 


#This function converts the images to be used in the program

# List of image file paths
image_paths = ["simgif.gif", "simdown.jpg","fsilogo.png" ]

#assign the files here to a label
fsilogo = Image.open(image_paths[0])
simdown = Image.open(image_paths[0])
simup = Image.open(image_paths[0])
#remove after assigning the correct images
simup = simup.resize((240, 320)) 
simdwon = simdown.resize((240, 320)) 
# This converts the Python image code into tkinter code to be drawn on the GUI
simdown = ImageTk.PhotoImage(simdown) 
simup = ImageTk.PhotoImage(simup)
fsilogo = ImageTk.PhotoImage(fsilogo)
print("images have been loaded starting main program")

started = False

"""
#This function builds the title screen
def show_title_screen():
    menu_screen = tk.Toplevel(root)
    menu_screen.title("Title Screen")
    #Title screen size
    titlesizex = screenx * .8
    titlesizey = screeny * .8
    menu_screen.geometry("600x800") #adjust size

    # Create title screen content here
    title_label = tk.Label(menu_screen, text="Welcome to Sim Monitor!", font=("Helvetica", 24))
    title_label.pack(pady=20)
    
    start_button = tk.Button(menu_screen, text="Start", command=show_main_window)
    start_button.pack()
"""

#This reveals the program after user selection:
"""def show_main_window():
    root.deiconify() #show the main window
    menu_screen.destroy() # close the title screen window

      """

#This draws when the sim is up
def drawrampup(xcord, ycord): 
    #Draw image
    canvas.create_image(xcord + 40, ycord + 40, anchor="nw", image=simup)
    canvas.image = simup
#This draws when the sim is down with ramp values
def drawsimdown(xcord, ycord):
    #Draw image
    canvas.create_image(xcord + 40, ycord + 40, anchor="nw", image=simdown)
    canvas.image = simdown
def drawsimmotion(xcord, ycord):
    canvas.create_image(xcord + 40, ycord + 40, anchor="nw", image=simdown)
    canvas.image = simdown
#This draws the data and updates it
def drawsimdata(xcord, ycord, ramp, motion, status):
    # Create a label for displaying the text
    label_sim_position = canvas.create_text(xcord + 60 , ycord + 400, text = "Sim_Position[motion]", anchor="nw", font=("Helveticia", 12))
    label_ramp_position = canvas.create_text(xcord + 60 , ycord + 420, text = "ramp_Position[ramp]", anchor="nw", font=("Helveticia", 12))
    label_sim_connection = canvas.create_text(xcord + 60 , ycord + 440, text = "sim_status[status]", anchor="nw", font=("Helveticia", 12))
#Here are all the sims and their data to be drawn:
def sim350(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 0, pixelratioy * 0)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 0, pixelratioy * 0)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 0, pixelratioy * 0)
    else:
        drawsimmotion(pixelratiox * 0, pixelratioy * 0)
    drawsimdata(pixelratiox * 0 , pixelratioy * 0, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim407(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 1, pixelratioy * 0)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 1, pixelratioy * 0)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 1, pixelratioy * 0)
    else:
        drawsimmotion(pixelratiox * 1, pixelratioy * 0)
    drawsimdata(pixelratiox * 1 , pixelratioy * 0, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim130(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 2, pixelratioy * 0)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 2, pixelratioy * 0)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 2, pixelratioy * 0)
    else:
        drawsimmotion(pixelratiox * 2, pixelratioy * 0)
    drawsimdata(pixelratiox * 2 , pixelratioy * 0, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim135(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 3, pixelratioy * 0)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 3, pixelratioy * 0)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 3, pixelratioy * 0)
    else:
        drawsimmotion(pixelratiox * 3, pixelratioy * 0)
    drawsimdata(pixelratiox * 3 , pixelratioy * 0, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim24(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 4, pixelratioy * 0)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 4, pixelratioy * 0)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 4, pixelratioy * 0)
    else:
        drawsimmotion(pixelratiox * 4, pixelratioy * 0)
    drawsimdata(pixelratiox * 4 , pixelratioy * 0, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim12(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 5, pixelratioy * 0)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 5, pixelratioy * 0)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 5, pixelratioy * 0)
    else:
        drawsimmotion(pixelratiox * 5, pixelratioy * 0)
    drawsimdata(pixelratiox * 5 , pixelratioy * 0, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim700(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 0, pixelratioy * 1)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 0, pixelratioy * 1)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 0, pixelratioy * 1)
    else:
        drawsimmotion(pixelratiox * 0, pixelratioy * 1)
    drawsimdata(pixelratiox * 0 , pixelratioy * 1, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim200(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 1, pixelratioy * 1)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 1, pixelratioy * 1)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 1, pixelratioy * 1)
    else:
        drawsimmotion(pixelratiox * 1, pixelratioy * 1)
    drawsimdata(pixelratiox * 1 , pixelratioy * 1, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim19(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 2, pixelratioy * 1)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 2, pixelratioy * 1)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 2, pixelratioy * 1)
    else:
        drawsimmotion(pixelratiox * 2, pixelratioy * 1)
    drawsimdata(pixelratiox * 2 , pixelratioy * 1, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim16(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 3, pixelratioy * 1)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 3, pixelratioy * 1)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 3, pixelratioy * 1)
    else:
        drawsimmotion(pixelratiox * 3, pixelratioy * 1)
    drawsimdata(pixelratiox * 3 , pixelratioy * 1, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim32(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 4, pixelratioy * 1)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 4, pixelratioy * 1)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 4, pixelratioy * 1)
    else:
        drawsimmotion(pixelratiox * 4, pixelratioy * 1)
    drawsimdata(pixelratiox * 4 , pixelratioy * 1, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
def sim32(rampstate, motionstate, status):
    if (rampstate == "0"):  
        if (motionstate == "0"):
            drawsimdown(pixelratiox * 5, pixelratioy * 1)
    elif (rampstate == "1"): 
        if (motionstate == "0"):
            drawrampup(pixelratiox * 5, pixelratioy * 1)
    elif (rampstate == "1"):  
        if (motionstate == "1"):
            drawsimmotion(pixelratiox * 5, pixelratioy * 1)
    else:
        drawsimmotion(pixelratiox * 5, pixelratioy * 1)
    drawsimdata(pixelratiox * 5 , pixelratioy * 1, rampstate, motionstate, status)
    #This is a coded filler to be able to add and replace code later 
    #RCHFS
    




#initial drawing of sims
def Draw_all():
    drawsimdown(pixelratiox * 0, pixelratioy * 0)
    drawsimdown(pixelratiox * 1, pixelratioy * 0)
    drawsimdown(pixelratiox * 2, pixelratioy * 0)
    drawsimdown(pixelratiox * 3, pixelratioy * 0)
    drawsimdown(pixelratiox * 4, pixelratioy * 0)
    drawsimdown(pixelratiox * 5, pixelratioy * 0)
    drawsimdown(pixelratiox * 0, pixelratioy * 1)
    drawsimdown(pixelratiox * 1, pixelratioy * 1)
    drawsimdown(pixelratiox * 2, pixelratioy * 1)
    drawsimdown(pixelratiox * 3, pixelratioy * 1)
    drawsimdown(pixelratiox * 4, pixelratioy * 1)
    drawsimdown(pixelratiox * 5, pixelratioy * 1)

    drawsimdata(pixelratiox * 0 , pixelratioy * 0, 0, 0,0)
    drawsimdata(pixelratiox * 1 , pixelratioy * 0, 0, 0,0)
    drawsimdata(pixelratiox * 2 , pixelratioy * 0, 0, 0,0)
    drawsimdata(pixelratiox * 3 , pixelratioy * 0, 0, 0,0)
    drawsimdata(pixelratiox * 4 , pixelratioy * 0, 0, 0,0)
    drawsimdata(pixelratiox * 5 , pixelratioy * 0, 0, 0,0)
    drawsimdata(pixelratiox * 0 , pixelratioy * 1, 0, 0,0)
    drawsimdata(pixelratiox * 1 , pixelratioy * 1, 0, 0,0)
    drawsimdata(pixelratiox * 2 , pixelratioy * 1, 0, 0,0)
    drawsimdata(pixelratiox * 3 , pixelratioy * 1, 0, 0,0)
    drawsimdata(pixelratiox * 4 , pixelratioy * 1, 0, 0,0)
    drawsimdata(pixelratiox * 5 , pixelratioy * 1, 0, 0,0)


#This is what tells the program what to do when you press a key.
def key_pressed(event):
    key = event.keysym.lower()
    if key in ['escape']:
        root.attributes('-fullscreen', False)  
        root.destroy()   
    if key in ['f']:
        #making it fullscreen
        root.attributes('-fullscreen', True)

if (started ==False):
    Draw_all()
    started = True

#This section of code filters out the incoming data and sends to appropriate function
#here we read the serial monitor
"""ser = serial.Serial('COM1', 115200);
incomingData = ser.readline().decode().strip()
leng = sys.getsizeof(incomingData)
print(leng)
"""
#test data to be removed later
leng = 4
incomingData = ["3","2","1","1"]

if (leng == 4):
    print("reading data")
    #32 data read
    if (incomingData[0] == "3"):
        if (incomingData[1] == "2"):
            sim32(incomingData[2], incomingData[3], 1)




#Creating the title screen
#show_title_screen()
#setting up images


# Set up keystroke event to change the program
root.bind("<KeyPress>", key_pressed)

#loops program
root.mainloop()





