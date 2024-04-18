import threading
from socket import *
import time
import copy

port = 13570

#creates socket
listener = socket(AF_INET, SOCK_STREAM)
listener.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
listener.bind(('', port))
listener.listen(32)

offlineLock = threading.Lock() #mutex for offline dict
currUsers = {} #all users dictionary
savedMessages = {} #offline message dict
warned = {} #users that have be warned from password
bannedFor = {} #Ip time dict
messageCount = {} #Spam detection dict
spamCooldown = {} #Spam detection dict
activeUsers = [] #active users list
banList = []
admin = ""
motd = "Message of the Day\n"

with open("users.txt", "w+") as f: #reads all user from the users file
    data = f.read()
    if data != "":
        currUsers = eval(data)

def getLine(conn): #gets line until newline is found
    msg = b''
    while True:
        ch = conn.recv(1)
        msg += ch
        if ch == b'\n' or len(ch) == 0:
            break
    return msg.decode()

def spamDealer(user):
    currTime = time.time()

    # Check and see if ip is already in message count
    # If so add time to list
    if user in messageCount:

        messageTimes = messageCount[user]

        # Loop through and check and remove expired times
        for timeSub in copy.copy(messageTimes):

            timeDiff = currTime - timeSub

            if timeDiff > 5:
                messageTimes.remove(timeSub)

        # Add new time, then check len of list to see if greater than three
        messageTimes.append(currTime)

        if len(messageTimes) >= 5:
            spamCooldown[user] = currTime

        messageCount[user] = messageTimes

    # Else not in warned, then add to warned with new times list
    else:
        messageCount[user] = [currTime]

def failedPassword(ip):
    currTime = time.time()

    # Check and see if ip is already warrned
    # If so add time to list
    if ip in warned:

        clientTimes = warned[ip]

        # Loop through and check and remove expired times
        for timeSub in copy.copy(clientTimes):

            timeDiff = currTime - timeSub

            if timeDiff > 30:
                clientTimes.remove(timeSub)

        # Add new time, then check len of list to see if greater than three
        clientTimes.append(currTime)

        if len(clientTimes) >= 3:
            bannedFor[ip] = currTime

        warned[ip] = clientTimes

    # Else not in warned, then add to warned with new times list
    else:
        warned[ip] = [currTime]

# Check if ip is banned
def banCheck(ip):

    currTime = time.time()
    
    #check if in banned list and check if its on cooldown
    if ip in bannedFor:
        timeBanned = bannedFor[ip]

        if (currTime - timeBanned) >= 120:
            del bannedFor[ip]
            return False
        else:
            return True

    else:
        return False

# Check if user is banned
def spamCheck(user):

    currTime = time.time()

    #check if in banned list and check if its on cooldown
    if user in spamCooldown:
        timeCooled = spamCooldown[user]

        if (currTime - timeCooled) >= 20:
            del spamCooldown[user]
            return False
        else:
            return True

    else:
        return False

# Listens for commands and sends messages to users based off of command
def listen(conn, user):
    global savedMessages, admin
    # Tell everyone that the user has logged in and send the user the motd
    activeUsers.append(user)
    conn.send(("loggedIn\n").encode()) 
    for n in activeUsers:
        otherConn = currUsers[n]["conn"]
        otherConn.send((f'Server: {user} has logged in.\n').encode())
    conn.send((f"Server: MOTD: {motd}").encode())
    offlineLock.acquire() #lock offline messages variables
    if user in savedMessages: #check if user has any offline messages and send them to user
        for i in savedMessages[user]:
            conn.send(i.encode())
    offlineLock.release() #unlock variables
    if len(activeUsers) == 1: #if user is only user in server they are admin
        admin = user
        for n in activeUsers: #tell everyone they are admin
            otherConn = currUsers[n]["conn"]
            otherConn.send((f'Server: {admin} is now the admin.\n').encode())

    # Listening loop
    exited = False
    while not exited:
        msg = getLine(conn)
        if spamCheck(user): #checks if someone was spamming
            conn.send(("Server: Due to message spam, you have been blocked for up to twenty seconds.\n").encode())
            continue
        spamDealer(user) #logs when message was sent
        if msg.startswith("/"): #if the msg is a command
            msgList = msg.split(" ")
            cmd = msgList[0] 
            
            if cmd[len(cmd) - 1] == "\n": #take newline off cmd
                cmd = cmd[:-1]

            if cmd == "/who":
                conn.send(("Server: Active users are: \n").encode())
                for n in activeUsers: #send all users in active list
                    conn.send((f'{n}\n').encode())

            elif cmd == "/motd": #sends motd
                conn.send((f"Server: MOTD: {motd}").encode())

            elif cmd == "/exit": #closes all connections and updates the admin if necessary
                conn.close()
                activeUsers.remove(user)
                if user == admin:
                    try:
                        admin = activeUsers[0]
                        for n in activeUsers:
                            otherConn = currUsers[n]["conn"]
                            otherConn.send((f'Server: {admin} is now the admin.\n').encode())
                    except:
                        pass
                for n in activeUsers: #tells all users that someone has left
                    otherConn = currUsers[n]["conn"]
                    otherConn.send((f'Server: {user} has logged out.\n').encode())
                exited = True #end listen loop for that user

            elif cmd == "/me": #sends emote style message
                try:
                    message = msg.split(" ", 1)[1]
                    emote = f'*{user} {message}\n' #styles message
                    for n in activeUsers: #sends to everyone
                        otherConn = currUsers[n]["conn"]
                        otherConn.send(emote.encode())
                except:
                    conn.send(("Server: Invalid use of /me command.\n").encode())

            elif cmd == "/tell":# send message to specific user
                try:
                    message = msg.split(" ", 1)[1]
                    otherUser, message = message.split(" ", 1)
                    if otherUser in currUsers:
                        if otherUser in activeUsers:
                            otherConn = currUsers[otherUser]["conn"] #get specific user connection
                            otherConn.send((f'{user}: {message}\n').encode())
                        else:
                            offlineLock.acquire() #add to offline messages if other user if offline
                            if otherUser not in savedMessages:
                                tmp = []
                                tmp.append(f'{user}: {message}\n')
                                savedMessages[otherUser] = tmp
                            else:
                                savedMessages[otherUser].append(f'Server: {user}: {message}\n')
                            offlineLock.release()

                    else:
                        conn.send((f"Server: {otherUser} does not exist.\n").encode())
                except:
                    conn.send(("Server: Invalid use of /tell command.\n").encode())

            elif cmd == "/ban": #/bans specifies user. Only able to be used by admin
                if user == admin:
                    otherUser = msg.split(" ", 1)[1]
                    otherUser = otherUser[:-1]
                    if otherUser not in banList: #if the user exists and is not already banned
                        if otherUser in currUsers:
                            banList.append(otherUser)
                            if otherUser in activeUsers: #if they are online send them a ban code to tell the client to logout
                                otherConn = currUsers[otherUser]["conn"]
                                otherConn.send(("banCode\n").encode())
                            for n in activeUsers: # tell everyone that the user has been banned
                                otherConn = currUsers[n]["conn"]
                                otherConn.send((f"Server: {otherUser} has been banned.\n").encode())
                        else:
                            conn.send((f"Server: {otherUser} does not exist.\n").encode())
                    else:
                        conn.send((f"Server: {otherUser} already banned.\n").encode())
                else:
                    conn.send(("Server: You are not the admin.\n").encode())

            elif cmd == "/unban": #unbans already banned users. Admin privelage only
                if user == admin:
                    otherUser = msg.split(" ", 1)[1]
                    otherUser = otherUser[:-1]
                    if otherUser in banList:
                        banList.remove(otherUser)
                    else:
                        conn.send((f"Server: {otherUser} already unbanned.\n").encode())

            elif cmd == "/kick": #kicks someone from server. Exactly the same as ban but does not add to ban list
                if user == admin:
                    otherUser = msg.split(" ", 1)[1]
                    otherUser = otherUser[:-1]
                    if otherUser in currUsers:
                        otherConn = currUsers[otherUser]["conn"]
                        otherConn.send(("kickCode\n").encode()) #send kick code instead of ban
                        for n in activeUsers:
                            otherConn = currUsers[n]["conn"]
                            conn.send((f"Server: {otherUser} has been kicked.\n").encode())
                    else:
                        conn.send((f"Server: {otherUser} does not exist.\n").encode())
                else:
                    conn.send(("Server: You are not the admin.\n").encode())

            else:
                conn.send(("Server: Invalid Command\n").encode())
        else:
            for n in activeUsers: #send message to all users
                otherConn = currUsers[n]["conn"]
                otherConn.send((f'{user}: {msg}\n').encode())

def firstConn(connInfo): #user connection function
    timeout = {}
    conn, ip = connInfo
    username = getLine(conn) #gets usernamae and password from client
    password = getLine(conn)
    username = username[:-1] #takes off newlines
    password = password[:-1]

    if banCheck(ip[0]): #check if they are ip banned
        conn.send(("Server: Banned for 2 minutes.\n").encode())

    elif username in currUsers: #if the username is taken
        if password == currUsers[username]["pass"]: #if password matches
            if username not in activeUsers: #if not logged in
                if username not in banList:
                    currUsers[username]["conn"] = conn #update connection
                    listen(conn, username) #start listening for commands
                else:
                    conn.send(("Server: Banned from server.\n").encode())
            
            else: #send to client they are already logged in
                conn.send(("alreadyIn\n").encode())

        else: #send to client they had an incorrect password
            conn.send(("badCredentials\n").encode())
            failedPassword(ip[0])

    else: #if user does not exist
        currUsers[username] = {}
        currUsers[username]["pass"] = password #add password dictionary
        with open("users.txt", "w+") as f: #write updated dict to file
            f.write(str(currUsers))
        currUsers[username]["conn"] = conn #add connection to dict
        listen(conn, username) #start listening for commands

running = True
while running:
    try: #make a thread for each client connected
        threading.Thread(target = firstConn, args = (listener.accept(),), daemon = True).start()
        
    except KeyboardInterrupt: #shut down server if ctrl-C
        print("\n[Shutting Down]")
        running = False


