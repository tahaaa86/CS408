import time
import tkinter as tk
from tkinter import messagebox
import socket
import threading
import json

# player class to hold each player
class Player:
    def __init__(self, sock, name):

        self.sock = sock
        self.name = name
        self.alive = True

        self.score = 0
        self.last_gained = 0
        self.answer = None

        # when the question is answered, -1 is invalid and it is a placeholder
        # it is float as time() returns float (it was showing error idk)
        self.answer_time = -1.0

        # statics for result info
        self.correct_count = 0
        self.answered_count = 0
        self.final_rank = None

    # send helper function
    # sends the data (commands + data)
    def send(self, data):
        try:
            self.sock.sendall((json.dumps(data) + "\n").encode())
        except:
            pass

    def disconnect(self):
      if not self.alive:
          return
      self.alive=False
      try:
        # stop sending but allow client to read remaining data
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
      except:
          pass
     

class QuizServer:
    
    # constructor
    def __init__(self, master):
        self.master = master
        master.title("SUquid Server")
        master.geometry("800x500")
        master.minsize(800,500)

        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1, minsize=180)
        master.grid_columnconfigure(1, weight=3, minsize=180)
        master.grid_columnconfigure(2, weight=1, minsize=350)

        self.server_socket = None
        self.is_listening = False

        # all players includes players that disconnected while the game is running
        self.allPlayers = []
        # alive players only contains players that are connected to the server
        self.alivePlayers = []

        # global scoreboard object
        self.scoreboard = []

        self.questions = []
        self.current_q = 0

        # gameStatus represents the current stage of the game
        # 0 => not started 
        # 1 => game running 
        # 2 => game finished
        self.gameStatus = 0

        self.asked_count = 0 # asked question count for report calc


        self.rankList = [] # array of players sorted by their points
                    # format: {"player":"Ali","rank":int_rank, "score": int_score}

        self.rankMap = {} # mapped version of rankList, used to access a specific player easier

        # thread array to store threads and control the order of some executions
        self.clientThreads= []

        # threading lock for scoreboard, to prevent duplicate entries as client handling 
        # threads run almost at the same time
        self.scoreboard_lock = threading.Lock()
        self.remove_lock = threading.Lock()

        self.create_frames()
        self.create_server_info()
        self.create_game_control()
        self.create_scoreboard()
        self.create_log()

    # create all frames used in UI
    def create_frames(self):
        # Left column (top/bottom)
        self.left_top = tk.Frame(self.master, bd=2, relief="groove")
        self.left_bottom = tk.Frame(self.master, bd=2, relief="groove")

        self.left_top.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.left_bottom.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Right columns
        self.scoreboard_frame = tk.Frame(self.master, bd=2, relief="groove")
        self.log_frame = tk.Frame(self.master, bd=2, relief="groove")

        self.scoreboard_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=5, pady=5)
        self.log_frame.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=5, pady=5)

        # Configure row weights
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_rowconfigure(1, weight=1)


    # server info section
    def create_server_info(self):
        tk.Label(self.left_top, text="Server Settings").pack(pady=5)

        tk.Label(self.left_top, text="IP:").pack(anchor="w", padx=5)
        self.ip_entry = tk.Entry(self.left_top)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack(fill="x", padx=5)

        tk.Label(self.left_top, text="Port:").pack(anchor="w", padx=5, pady=(5,0))
        self.port_entry = tk.Entry(self.left_top)
        self.port_entry.insert(0,"5050")
        self.port_entry.pack(fill="x", padx=5)

        tk.Label(self.left_top, text="Question File:").pack(anchor="w", padx=5, pady=(10,0))
        self.file_entry = tk.Entry(self.left_top)
        self.file_entry.insert(0, "quiz_qa.txt")
        self.file_entry.pack(fill="x", padx=5)

        self.start_server_btn = tk.Button(self.left_top, text="Start Server", command=self.toggle_server)
        self.start_server_btn.pack(pady=10)

    # game control section
    def create_game_control(self):
        tk.Label(self.left_bottom, text="Game Control").pack(pady=5)

        tk.Label(self.left_bottom, text="Question Count:").pack(anchor="w", padx=5)
        self.qcount_entry = tk.Entry(self.left_bottom)
        self.qcount_entry.insert(0,"20")
        self.qcount_entry.pack(fill="x", padx=5)

        self.start_game_btn = tk.Button(self.left_bottom, text="Start Game", state=tk.DISABLED, command=self.toggle_game)
        self.start_game_btn.pack(pady=10)

        self.status_box = tk.Label(self.left_bottom, text="Not enough players")
        self.status_box.pack(pady=10)

    # scoreboard section
    def create_scoreboard(self):
        tk.Label(self.scoreboard_frame, text="Scoreboard").pack(anchor="w", padx=5, pady=5)
        self.scoreboardBox = tk.Text(self.scoreboard_frame, state=tk.DISABLED)
        self.scoreboardBox.pack(fill="both", expand=True, padx=5, pady=5)

    # log box section
    def create_log(self):
        tk.Label(self.log_frame, text="Server Log").pack(anchor="w", padx=5, pady=5)
        self.log = tk.Text(self.log_frame, state=tk.DISABLED)
        self.log.tag_config("separator", foreground="blue")
        self.log.tag_config("qSep", foreground="cyan")
        self.log.pack(fill="both", expand=True, padx=5, pady=5)

    # toggle server function for button
    def toggle_server(self):
      if not self.is_listening:
        self.start_server()
      else:
        self.stop_server()

    # start server function
    def start_server(self):

        # clean up the arrays
        self.alivePlayers = []
        self.allPlayers = []
      
        ip = str(self.ip_entry.get())
        port = int(self.port_entry.get())
        
        if not ip:
            messagebox.showerror("Error", "Please enter a ip address.")
            return
        
        if not port:
            messagebox.showerror("Error", "Please enter a port number.")
            return
        

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((ip, port))
        self.server_socket.listen()
        self.is_listening = True

        self.ip_entry.config(state=tk.DISABLED)
        self.port_entry.config(state=tk.DISABLED)

        self.start_server_btn.config(text="Stop Server")

        self.log_msg(f"Server started on {ip}:{port}")
        threading.Thread(target=self.accept_clients, daemon=True).start()

    # stop server function
    def stop_server(self):
        self.is_listening = False
        
        # send server closing info to each client
        self.broadcast_info("Server stopped. All players will be disconnected.")

        # send END command, so clients can handle end game case
        #for p in self.alivePlayers:
            #p.send({"command": "END"})

        time.sleep(0.3) # wait a bit, give clients some time

        # Disconnect players
        for p in self.alivePlayers:
            p.disconnect()

        try:
            self.server_socket.close()
        except:
            pass

        self.ip_entry.config(state=tk.NORMAL)
        self.port_entry.config(state=tk.NORMAL)
        self.start_server_btn.config(text="Start Server")

        self.start_game_btn.config(state=tk.DISABLED)

        self.log_msg("Server stopped")
        

        # activate question entry
        self.qcount_entry.config(state=tk.NORMAL)

    # accept clients function.
    # only works when server is listening (server online, game not started)
    def accept_clients(self):
        while self.is_listening:
            try:
                client_sock, client_address = self.server_socket.accept()
            except OSError:
                # As .accept() is blocking, when server stopped, it is not able to detect closure , and its produces error
                # consume that error
                break

            # append thread to the list
            t = threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True)
            t.start()
            self.clientThreads.append(t)


    # handle client function
    # handles client joins
    def handle_client(self, sock):
        # if a game is running, do not accept any client
        if self.gameStatus == 1:
            sock.sendall(json.dumps({
                "command": "ERROR",
                "message": "Game already running"
            }).encode() + b"\n")

            # log it
            self.log_msg("A player rejected as a game is running")

            # send an END command, so client knows server disconnected expectedly
            sock.sendall((json.dumps({"command": "END"}) + "\n").encode())
            time.sleep(0.3) # wait a bit, give clients some time

            sock.close()
            return

        # if game is not running, receive data
        try:
            data = sock.recv(1024).decode()
            msg = json.loads(data)
        except:
            sock.close()
            return
        
        # if not join message, close connection
        # Just a protection, as cilent is written by me, the first message should always be join
        if msg.get("command") != "JOIN":
            sock.close()
            return

        # get username and append to the player list
        name = msg.get("username")

        # check for duplicate usernames
        for p in self.alivePlayers:
            if p.name == name:
                try:
                    sock.sendall(json.dumps({
                        "command": "ERROR",
                        "message": "Username already taken"
                    }).encode() + b"\n")
                except:
                    pass

                # send an END command, so client knows server disconnected expectedly
                sock.sendall((json.dumps({"command": "END"}) + "\n").encode())
                time.sleep(0.3) # wait a bit, give clients some time

                sock.close()
                self.log_msg(f"Duplicate username \"{name}\" rejected")
                return
            
        player = Player(sock, name)
        self.allPlayers.append(player)
        self.alivePlayers.append(player)

        # send ack to player (means connection successful)
        player.send({
            "command": "ACK",
            "message": "Username accepted"
        })

        self.log_msg(f"Player joined: {name}")

        # send scoreboard to connected and existing users
        self.update_scoreboard()
        
        for p in self.alivePlayers:
            p.send({
                "command": "SCOREBOARD",
                "scoreboard": self.scoreboard
            })
        

        # check player count for each new player
        if len(self.alivePlayers) >= 2:
            self.start_game_btn.config(state=tk.NORMAL)
            self.status_box.config(text="Ready!")

        # listen for answers, while player is connected
        while player.alive:
            try:
                data = sock.recv(1024).decode()
                if not data:
                    break

                msg = json.loads(data)
                if msg.get("command") == "ANSWER":
                    player.answer = msg.get("answer")
                    player.answer_time = time.time()
                    # log player's answer
                    self.log_msg(f"{player.name} answered: {player.answer}")         
            except:
                break

        # end of loop, disconnect player
        self.log_msg(f"{player.name} disconnected")

        player.disconnect()

        # If player disconnected before game started
        self.broadcast_info(f"{player.name} left the lobby.")
        self.remove_player(player)

        # update start button
        if len(self.alivePlayers) < 2:
            self.start_game_btn.config(state=tk.DISABLED)
            self.status_box.config(text="Not enough players")

    # toggle game for button
    def toggle_game(self):
      if self.gameStatus != 1:
          self.start_game()
      else:
          self.end_game()

    # starts the game
    def start_game(self):
        count = self.qcount_entry.get()
        filename = self.file_entry.get()

        # empty name check
        if not filename:
            messagebox.showerror("Invalid Entry", "Question file name cannot be empty")
            return

        try:
            with open(filename, "r", encoding="utf-8"):
                pass  # file opens successfully
        except FileNotFoundError:
            messagebox.showerror(
                "Invalid File",
                f"File {filename} not found!"
            )
            return
        except Exception as e:
            messagebox.showerror(
                "Invalid File",
                f"Cannot open file:\n{e}"
            )
            return
        
        # q count check
        if not count or not count.isdigit():
            messagebox.showerror("Invalid Entry", "Invalid question count entry")
            return

        self.gameStatus = 1
        self.start_game_btn.config(text="End Game")
        self.qcount_entry.config(state=tk.DISABLED)
        self.file_entry.config(state=tk.DISABLED)

        self.log_msg("Game started")
        self.status_box.config(text="Game is running!")
        threading.Thread(target=self.run_game, daemon=True).start() # start threading

    # ends the game
    def end_game(self):
        self.gameStatus = 2

        self.start_game_btn.config(text="Start Game")
        self.qcount_entry.config(state=tk.NORMAL)
        self.file_entry.config(state=tk.NORMAL)

        # send game end info
        self.broadcast_info("Game has ended. Connection will be closed.")

        # send final result to every player
        self.send_final_results()

        # send END command, so clients can handle end game case
        for p in self.alivePlayers:
            p.send({"command": "END"})

        time.sleep(0.5) # wait a bit, give clients some time

        # Reset players
        for p in self.alivePlayers:
            p.disconnect()

        time.sleep(1)

        self.log_msg("Game ended")
        self.log_msg("--------------------------","separator")


        # clean up the arrays
        self.alivePlayers = []
        self.allPlayers = []
        # clean up asked q count
        self.asked_count = 0

    def run_game(self):

        # load questions
        self.load_questions()

        # for each question in the list
        for q_text, options, correct in self.questions:
           
            # send q to all players
            # also reset their answers and times
            for p in self.alivePlayers:
                p.answer = None
                p.answer_time = -1.0
                p.send({"command": "QUESTION", "question": q_text, "text": options})
            
            # log questions to logbox
            self.log_msg(f"---------------------------", tag="qSep")
            self.log_msg(f"QUESTION: {q_text}")
            self.log_msg(f"CHOICES: {options}")
            self.log_msg(f"CORRECT: {correct}")
            self.log_msg(f"---------------------------",tag="qSep")

            # wait until all connected players answered
            while True:
                
                # if game stopped, return
                if self.gameStatus != 1:
                    return

                # set all_answered to true, and loop through players
                # if a player is not answered, then change flag to false
                all_answered = True
                for p in self.alivePlayers:
                    if p.answer is None:
                        all_answered = False
                        break
                
                # if everybody is answered, break the loop and continue with score calculation
                if all_answered:
                    break

                # small sleep to avoid wasting resource
                threading.Event().wait(0.1)


            # update asked question count right after the answer wait loop
            # so, if for any reason game ends before, asked_count is up to date
            self.asked_count += 1

            if not self.alivePlayers:
                self.log_msg("No players left. Ending the loop")
                break

            # correct players
            # "p.answer_time is not -1.0" is extra security
            correct_players = [ p for p in self.alivePlayers if p.answer == correct and p.answer_time != -1.0]

            # find first correct answer (bonus winner)
            # if there are at least one correct answered player
            bonus_winner = None
            if correct_players:
                # get player with min answer_time
                bonus_winner = min(correct_players, key=lambda p: p.answer_time)

            # bonus points = connected players - 1
            # if there are less than two player remanied, bonus will be zero instead negative
            # then the game will end after evaluated question as there should be more than 2 players
            bonus_points = max(len(self.alivePlayers) - 1, 0)

            # calculate scores
            for p in self.alivePlayers:
                gained = 0
                if p.answer == correct:
                    gained = 1
                    p.correct_count += 1
                else:
                    if p.answer is not None:
                        p.answered_count += 1

                if p == bonus_winner:
                    gained += bonus_points

                p.score += gained
                # separate gained for reporting gained points   
                p.last_gained = gained

            # sort players according to their points
            self.sortRank()

            # send per-player result
            for p in self.alivePlayers:
                p.send({
                    "command": "RESULT",
                    "correct": correct,
                    "your_answer": p.answer,
                    "total_score": p.score,
                    "gained_score": p.last_gained,
                    "rank": self.rank_map[p] # this is mapped list
                })

            self.update_scoreboard()

            for p in self.alivePlayers:
                p.send({
                    "command": "SCOREBOARD",
                    "scoreboard": self.scoreboard
                })


            # if not enough player, end the game (at the end of the loop to ensure last question is asked)
            if len(self.alivePlayers) < 2:
                self.log_msg("Not enough players. Ending game.")
                break
                
        # wait a bit for clients to process
        time.sleep(0.3)

        for p in self.alivePlayers:
            p.send({"command": "SCOREBOARD","scoreboard": self.scoreboard})

        # wait a bit for clients to process
        time.sleep(0.3)

        # end game
        # END command sent in this function
        # player disconnection handled in this function
        self.end_game()

    # logger helper function
    # tag is used for formatting the message
    def log_msg(self, msg, tag=None):
        self.log.config(state=tk.NORMAL)
        
        # format output if tag is specified
        if tag:
            self.log.insert(tk.END, msg + "\n", tag)
        else:
            self.log.insert(tk.END, msg + "\n")

        self.log.config(state=tk.DISABLED)
        self.log.yview(tk.END)

    # question load helper
    def load_questions(self):

        # filename is fixed?
        filename = self.file_entry.get().strip()

        # for safety
        if not filename:
            self.log_msg("Question file name is empty!")
            messagebox.showerror("Question file name is empty!")
            return
        
        # clear old questions
        self.questions = []

        try:
            with open(filename, "r", encoding="utf-8") as f:
                # open file and get questions
                # ensuring extra empty lines are skipped
                lines = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.log_msg(f"Error, {filename} is not found!")
            messagebox.showerror( "ERROR",
                f"Error, {filename} is not found!"
            )
            return

        # total number of questions in file
        # assuming questions are in correct format (5 lines per q)
        total_questions = len(lines) // 5

        try:
            # get question count from the entry
            count = int(self.qcount_entry.get())
        except ValueError:
            # in an error case, assign total q in the file to count
            count = total_questions

        for i in range(count):

            # base is start index of a question
            base = (i % total_questions) * 5

            # get questions based on "base" index
            question = lines[base] 
            a = lines[base + 1].split("-", 1)[1].strip()
            b = lines[base + 2].split("-", 1)[1].strip()
            c = lines[base + 3].split("-", 1)[1].strip()
            correct = lines[base + 4].split(":")[1].strip()

            self.questions.append(
                (question, f"{a};{b};{c}", correct)
            )

        self.log_msg(f"Loaded {len(self.questions)} questions")

        # randomize questions, commented as it is not explained,
        # but i want to keep the line
        # random.shuffle(self.questions)

    # update scoreboard box, and scoreboard itself
    def update_scoreboard(self):
        with self.scoreboard_lock:
            self.scoreboardBox.config(state=tk.NORMAL)
            self.scoreboardBox.delete("1.0", tk.END)

            # define a local array, and sort according to their points
            local_ranked = sorted(self.allPlayers, key=lambda p: p.score, reverse=True)

            rank = 1 # rank is the global rank
            prev_score = None # to identify players with the same points, (if p.score = prev_score)
            shown_rank = 0 # shown rank is the rank that displayed to scoreboard 
                        # it is used to assign same rank to equal point players

            # make ranked and scoreboard arrays empty empty, so new data can be written instead of updating
            self.ranked = []
            self.scoreboard =[]


            for p in local_ranked:
                if p.score != prev_score:
                    shown_rank = rank
                    prev_score = p.score

                status = " (DISCONNECTED)" if not p.alive else ""
                self.scoreboardBox.insert(
                    tk.END,
                    f"{shown_rank}. {p.name}: {p.score}{status}\n"
                )

                # ranked list with tied ranks
                self.ranked.append({
                    "player": p,
                    "rank": shown_rank,
                    "score": p.score
                })

                # update the global scoreboard
                self.scoreboard.append(
                    f"{p.name}:{p.score}{':(DISCONNECTED)' if not p.alive else ':'}"
                )

                rank += 1

            self.scoreboardBox.config(state=tk.DISABLED)


    # remove disconnected player
    def remove_player(self, player):
        with self.remove_lock:

            # remove form alive list
            if player in self.alivePlayers:
                self.alivePlayers.remove(player)

            # if the game is not running running (i.e. not started), also keeps if the game is finished
            if player in self.allPlayers and self.gameStatus != 1:
                self.allPlayers.remove(player)

            self.log_msg(f"{player.name} removed from player list")

            # update scoreboard
            self.update_scoreboard()

            # send updated scoreboard to remaining players
            for p in self.alivePlayers:
                p.send({
                    "command": "SCOREBOARD",
                    "scoreboard": self.scoreboard
                })

    # send final result to everyone
    def send_final_results(self):

        # choose winners
        winners = [player.name for player, rank in self.rankList if rank == 1]

        for p, listRank in self.rankList:
            # compute incorrectly answered question count
            incorrect = self.asked_count - p.correct_count

            p.send({
                "command": "FINAL_RESULT",
                "total_score": p.score,
                "rank":listRank,
                "correct": p.correct_count,
                "incorrect": incorrect,
                "total_questions": self.asked_count,
                "winners":winners})

    # broadcast helper
    # sends given info to everyone
    def broadcast_info(self, message):
        self.log_msg(f"[INFO BROADCAST] {message}")

        # only send to alive players
        for p in self.alivePlayers:
            p.send({"command": "INFO","message": message})

    def sortRank(self):

        # local ranked list for calculation, so we can empty class lists
        ranked = sorted( [p for p in self.allPlayers], key=lambda p: p.score, reverse=True)

        # empty the list
        self.rankList = []
        self.rank_map = {} # map is used for faster access to player-rank tuples

        rank = 1 # rank is the global rank
        prev_score = None # to identify players with the same points, (if p.score = prev_score)
        shown_rank = 1 # shown rank is the rank that displayed to scoreboard 
                       # it is used to assign same rank to equal point players

        # loop to sort players
        for p in ranked:

            # if player point differ with prev player point
            if p.score != prev_score:
                shown_rank = rank
                prev_score = p.score

            # update global lists
            self.rankList.append((p, shown_rank))
            self.rank_map[p] = shown_rank

            # increase rank
            rank += 1

# main
if __name__ == "__main__":
    root = tk.Tk()
    QuizServer(root)
    root.mainloop()
