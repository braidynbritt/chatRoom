import os
import threading
import time
import curses
import atexit
from sys import argv
from socket import *

#makes sure args are correct
if len(argv) < 3:
    print("Usage: python3 bvChat-client.py [IPADDR] [PORT]")
    exit()

#initial vars
port = int(argv[2])
ip = argv[1]
response = ""
blockedList = []
helpInfo = """ \
            /who - Displays list of all users currently connected to the server

            /exit - Disconnects from servers and quits client application
            
            /tell [username] [message] - sends message to specified user

            /motd - display current message of the day

            /block [username] - Blocks specified user's messages

            /unblock [username] - Unblocks specified user's messages

            /me [message] - Displays emote message

            /help - displays list of commands

            -------------------ADMIN PRIVELAGES----------------------
            /kick [username] - Kicks a specified user off the server.

            /ban [username] - Bans a specified user from server. Makes them unable to log back in

            /unban [username] - Unbans a previously banned user.
            """

#gets username and password then adds a new line for sending
while True:
    username = input("Username: ")
    if " " in username:
        print("Spaces are not allowed in username. Try again.")
    else:
        break

password = input("Password: ")
username = username + "\n"
password = password + "\n"

#everything below is ncurses boilerplate
stdscr = curses.initscr()
curses.cbreak()
size = stdscr.getmaxyx()
row = size[0]
col = size[1]
chatLog = curses.newwin(row-2, col, 0, 0)
chatBox = curses.newwin(1, col, row-1, 0)
stdscr.scrollok(True)
chatLog.scrollok(True)
chatBox.scrollok(True)

def getLine(conn): #recvs message until newlien
    msg = b''
    while True:
        ch = conn.recv(1)
        msg += ch
        if ch == b'\n' or len(ch) == 0:
            break
    return msg.decode()

def serverConnect(): #makes a server connection
    try:
        serverSocket = socket(AF_INET, SOCK_STREAM)
        serverSocket.connect((ip, port))
        return serverSocket
    except:
        print("Connection failed.")
        exit()

def listen(conn): #listening for incoming messages
    global response

    while True:
        msg = getLine(conn)
        if len(msg) > 0:
            #if msg is a server code then update response for login
            if msg == "alreadyIn\n" or msg == "badCredentials\n" or msg == "banCode\n" or msg == "kickCode\n":
                response = msg
                break
            elif msg == "loggedIn\n":
                response = msg
            else:
                if ": " in msg: #prints message from a user
                    name = msg.split(": ", 1)[0]
                    if name not in blockedList:
                        chatLog.addstr("\n")
                        chatLog.addstr(msg[:-1])
                else: #prints everything else
                    chatLog.addstr("\n")
                    chatLog.addstr(msg[:-1])
                chatLog.refresh()


#gets user input to send to server
def userInput(conn):
    global blockedList 
    global response
    while True:
        chatBox.addstr(0,0, f'{username[:-1]}: ')
        userIn = chatBox.getstr(0, len(username) + 1).decode() #Ncurses line. Gets user input
        #userIn = input(f'{username[:-1]}: ') Orginal Line
        if response != "banCode\n" and response != "kickCode\n":
            msgList = userIn.split(" ")
            cmd = msgList[0]
            if cmd == "/help": #if its help print the help message
                #print(helpInfo)
                chatLog.addstr("\n")
                chatLog.addstr(helpInfo)
                chatLog.refresh()

            elif cmd == "/exit":
                conn.send((userIn + "\n").encode())
                chatLog.addstr("\n")
                chatLog.addstr("Logging Out.")
                chatLog.refresh()

                #print("Logging Out")
                break

            elif cmd == "/block": #blocks a specified user or prints if they are already blocked
                blocked = userIn.split(" ")[1]
                if blocked not in blockedList:
                    blockedList.append(userIn.split(" ")[1])
                else:
                    chatLog.addstr("\n")
                    chatLog.addstr(f"{blocked} is already blocked.")
                    chatLog.refresh()

                    #print(f'{blocked} is already blocked.')

            elif cmd == "/unblock": #unblocks a specified user or prints if they are not blocked
                blocked = userIn.split(" ")[1]
                if blocked in blockedList:
                    blockedList.remove(userIn.split(" ")[1])
                else:
                    chatLog.addstr("\n")
                    chatLog.addstr(f"{blocked} is already not blocked.")
                    chatLog.refresh()

                    #print(f'{blocked} is already not blocked')
            else:
                conn.send((userIn + "\n").encode()) #send input to server
        else:
            conn.send(("/exit\n").encode())
            if response == "banCode\n":
                chatLog.addstr("\n")
                chatLog.addstr(f"Banned.")
                chatLog.refresh()

                #print("Banned.")
            else:
                chatLog.addstr("\n")
                chatLog.addstr(f"Kicked.")
                chatLog.refresh()

                #print("Kicked.")
            return

# Connect user to server and try to login
def login(conn):
    global response
    loggedIn = False

    try:
        conn.send(username.encode()) #send username and password
        conn.send(password.encode())
        time.sleep(.5) #wait for response
        if response == "loggedIn\n": #if succes then get input
            loggedIn = True
            userInput(conn)

        if response == "badCredentials\n": #if bad password
            #print("Incorrect Password")
            chatLog.addstr("\n")
            chatLog.addstr(f"Incorrect Password.")
            chatLog.refresh()

            conn.close()
            exit()

        if response == "alreadyIn\n": #if already logged in
            #print("Already Logged in.")
            chatLog.addstr("\n")
            chatLog.addstr(f"Already Logged in.")
            chatLog.refresh()
            conn.close()
            exit()

    except Exception as e: #if an error happens
        print(e)
    
@atexit.register #on exit, makes sure ncurses closes correctly
def exitCurses():
    curses.nocbreak()
    curses.endwin()

serverSocket = serverConnect() #make a server connection
threading.Thread(target = listen, args = (serverSocket,), daemon = True).start() #thread for recv messages

try:
    login(serverSocket) #main thread runs login and input
except KeyboardInterrupt:
    print("\nLogging out")
    serverSocket.send(("/exit\n").encode())
    serverSocket.close()

