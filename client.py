import tkinter as tk
from tkinter import messagebox
import socket
import threading
import json


class SUquidClient:
    def __init__(self):
        self.sock = None
        self.listener_thread = None
        self.connected = False
        self.username = None
        self.awaiting_ack = False
        self.username = None
        self.result_received= 0

        self.root = tk.Tk()
        self.root.title("SUquid Client")
        self.root.geometry("1500x500")
        self.root.minsize(1000,500)

        self.create_frames()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)
        self.root.mainloop()

    # create all frames
    def create_frames(self):
        self.root.grid_columnconfigure(0, weight=0, minsize=220)# conn. frame
        self.root.grid_columnconfigure(1, weight=3)# question frame
        self.root.grid_columnconfigure(2, weight=2, minsize=500)# log frame
        self.root.grid_columnconfigure(3, weight=1, minsize=180)# scoreboard frame
        self.root.grid_rowconfigure(0, weight=1)

        self.create_connection_frame()
        self.create_question_frame()
        self.create_status_frame()
        self.create_scoreboard_frame()

    # connection control frame
    def create_connection_frame(self):
        self.conn_frame = tk.Frame(self.root, bd=2, relief="groove", padx=8, pady=8)
        self.conn_frame.grid(row=0, column=0, sticky="nsew")

        tk.Label(self.conn_frame, text="Connection").pack(anchor="w", pady=(0, 8))

        tk.Label(self.conn_frame, text="IP").pack(anchor="w")
        self.ip_entry = tk.Entry(self.conn_frame, width=18)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack()

        tk.Label(self.conn_frame, text="Port").pack(anchor="w", pady=(6, 0))
        self.port_entry = tk.Entry(self.conn_frame, width=18)
        self.port_entry.insert(0, "5050")
        self.port_entry.pack()

        tk.Label(self.conn_frame, text="Username").pack(anchor="w", pady=(6, 0))
        self.username_entry = tk.Entry(self.conn_frame, width=18)
        self.username_entry.pack()

        self.connect_btn = tk.Button(
            self.conn_frame, text="Connect", command=self.connect
        )
        self.connect_btn.pack(pady=(10, 4), fill="x")

        self.disconnect_btn = tk.Button(
            self.conn_frame, text="Disconnect",
            command=self.disconnect,
            state=tk.DISABLED
        )
        self.disconnect_btn.pack(fill="x")

    # question and answer frame
    def create_question_frame(self):
        self.question_frame = tk.Frame(self.root, bd=2, relief="groove", padx=10, pady=10)
        self.question_frame.grid(row=0, column=1, sticky="nsew")

        tk.Label(self.question_frame, text="Question").pack(anchor="w")

        self.question_box = tk.Text(
            self.question_frame, height=6, wrap="word", state=tk.DISABLED
        )
        self.question_box.pack(fill="x", pady=6)

        self.answer_var = tk.StringVar()
        self.option_boxes = {}

        for opt in ("A", "B", "C"):
            row = tk.Frame(self.question_frame)
            row.pack(fill="x", pady=4)

            tk.Radiobutton(
                row, text=opt, variable=self.answer_var, value=opt
            ).pack(side="left")

            txt = tk.Text(row, height=2, width=45, wrap="word", state=tk.DISABLED)
            txt.pack(side="left", padx=6)

            self.option_boxes[opt] = txt

        self.send_btn = tk.Button(
            self.question_frame, text="Send Answer",
            command=self.send_answer, state=tk.DISABLED # init answer button as disabled
        )
        self.send_btn.pack(pady=10)


    # log frame
    def create_status_frame(self):
        self.status_frame = tk.Frame(self.root, bd=2, relief="groove", padx=10, pady=10)
        self.status_frame.grid(row=0, column=2, sticky="nsew")

        self.status_label = tk.Label(
            self.status_frame, text="Not connected", fg="blue"
        )
        self.status_label.pack(anchor="w", pady=(0, 8))

        self.log_box = tk.Text(self.status_frame, state=tk.DISABLED)
        self.log_box.pack(fill="both", expand=True)

    # scoreboard frame
    def create_scoreboard_frame(self):
        self.scoreboard_frame = tk.Frame(
            self.root, bd=2, relief="groove", padx=10, pady=10
        )
        self.scoreboard_frame.grid(row=0, column=3, sticky="nsew")

        tk.Label(self.scoreboard_frame, text="Scoreboard").pack(anchor="w")

        self.scoreboard_box = tk.Text(self.scoreboard_frame,state=tk.DISABLED,width=22)
        self.scoreboard_box.pack(fill="both", expand=True)

        # text tags for differentiating player and other users
        self.scoreboard_box.tag_configure("me", foreground="blue", font=("TkDefaultFont", 10, "bold"))
        self.scoreboard_box.tag_configure("other", foreground="black")

    # connect handler
    def connect(self):
        if self.connected or self.awaiting_ack:
            return

        ip = self.ip_entry.get().strip()
        port = int(self.port_entry.get().strip())
        username = self.username_entry.get().strip()

        if not username:
            messagebox.showerror("Error", "Username required")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((ip, port))
            self.send_json({"command": "JOIN", "username": username})
        except Exception as e:
            # connection failed popup
            messagebox.showerror("Connection Failed", str(e))
            return

        # wait for ack
        self.awaiting_ack = True
        self.username = username
        self.set_status("Connecting...")
        self.log("Waiting for server approval...")

        # start thread
        self.listener_thread = threading.Thread(target=self.listen, daemon=True)
        self.listener_thread.start()

        # clear log and question frame
        # q frame
        self.question_box.config(state=tk.NORMAL)
        self.question_box.delete("1.0", tk.END)
        self.question_box.config(state=tk.DISABLED)

        # answers
        for opt in self.option_boxes.values():
            opt.config(state=tk.NORMAL)
            opt.delete("1.0", tk.END)
            opt.config(state=tk.DISABLED)

        # clear answer selector
        self.answer_var.set("")

        # clear log
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete("1.0", tk.END)
        self.log_box.config(state=tk.DISABLED)

    # disconnect handler
    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

        self.connected = False
        self.set_status("Disconnected")
        self.log("Disconnected")

        self.connect_btn.config(state=tk.NORMAL)
        self.ip_entry.config(state=tk.NORMAL)
        self.port_entry.config(state=tk.NORMAL)
        self.username_entry.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)


    # listen thread function
    def listen(self):
        buffer = ""
        while self.sock:
            try:
                data = self.sock.recv(1024).decode()

                # Server closed connection
                if not data:
                    break

                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    msg = json.loads(line)
                    self.dispatch_message(msg)

            except:
                break

        # connection closed
        if self.root.winfo_exists():
            # If game ended normally, don't show server disconnected popup
            if not self.result_received and self.connected:
                self.handle_server_disconnect()
            else:
                self.set_status("Game finished. Disconnected from server.")

    # send json helper function
    def send_json(self, data):
        try:
            self.sock.sendall((json.dumps(data) + "\n").encode())
        except:
            pass

    # incoming message handler
    # calls correct funciton depending on the command
    def dispatch_message(self, msg):

        cmd = msg.get("command")

        if cmd == "QUESTION":
            self.show_question(msg)

        elif cmd == "RESULT":
            self.show_result(msg)

        elif cmd == "SCOREBOARD":
            self.update_scoreboard(msg["scoreboard"])

        elif cmd == "INFO":
            self.handle_info(msg)

        elif cmd == "ERROR":
            self.handle_error(msg)

        elif cmd == "ACK":
            self.handle_ack(msg)

        elif cmd == "FINAL_RESULT":
            self.show_final_result(msg)

        elif cmd == "END":
            self.handle_end()

    # show question helper
    def show_question(self, msg):
        self.set_status("Answering")
        self.answer_var.set("")

        self.log(f"Question Received: {msg["question"]}")

        

        self.question_box.config(state=tk.NORMAL)
        self.question_box.delete("1.0", tk.END)
        self.question_box.insert(tk.END, msg["question"])
        self.question_box.config(state=tk.DISABLED)

        options = msg["text"].split(";")

        for opt, text in zip(("A", "B", "C"), options):
            box = self.option_boxes[opt]
            box.config(state=tk.NORMAL)
            box.delete("1.0", tk.END)
            box.insert(tk.END, text)
            box.config(state=tk.DISABLED)

        self.send_btn.config(state=tk.NORMAL)
    

    # show result helper
    def show_result(self, msg):
        self.set_status("Answered")
        self.log(
            f"Your: {msg['your_answer']} | "
            f"Correct: {msg['correct']} | "
            f"Gained: {msg['gained_score']} | "
            f"Total: {msg['total_score']} | "
            f"Rank: {msg['rank']}"
        )
        self.send_btn.config(state=tk.NORMAL)

    # answer sender
    def send_answer(self):
        ans = self.answer_var.get()
        
        if ans and self.connected:
            self.send_json({"command": "ANSWER", "answer": ans})
            self.set_status("Answered")
            self.send_btn.config(state=tk.DISABLED)

    # scoreboard updater
    def update_scoreboard(self, scoreboard):

        self.scoreboard_box.config(state=tk.NORMAL)
        self.scoreboard_box.delete("1.0", tk.END)

        local_scoreboard = [] 

        for i in range(len(scoreboard)):
            entry = scoreboard[i]

            try:
                name, score, status = entry.split(":", 2)
                local_scoreboard.append((name.strip(), int(score.strip()), status))
            except ValueError:
                continue

        rank = 1 # rank is the global rank
        prev_score = None # to identify players with the same points, (if p.score = prev_score)
        shown_rank = 0 # shown rank is the rank that displayed to scoreboard 
                       # it is used to assign same rank to equal point players
        
        for name, score, status in local_scoreboard:
                if score != prev_score:
                    shown_rank = rank
                    prev_score = score

                line = f"{shown_rank}. {name}: {score} {status}\n"

                if name == self.username:
                    self.scoreboard_box.insert(tk.END, line, "me")
                else:
                    self.scoreboard_box.insert(tk.END, line, "other")
                
                rank += 1

        self.scoreboard_box.config(state=tk.DISABLED)

    # error handler
    def handle_error(self, msg):
        error_text = msg.get("message")

        messagebox.showerror("Server Error", error_text)
        self.log(f"ERROR: {error_text}")

        # Reset connection state
        self.awaiting_ack = False
        self.connected = False

        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

        self.set_status("Not connected")

        # Re-enable inputs
        for w in (self.ip_entry, self.port_entry, self.username_entry):
            w.config(state=tk.NORMAL)

        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)

    # ack handler
    # ack send if username is available
    def handle_ack(self, msg):
        self.awaiting_ack = False
        self.connected = True

        self.set_status("Connected")
        self.log("Connected successfully")

        # Change input fields and buttons status
        self.ip_entry.config(state=tk.DISABLED)
        self.port_entry.config(state=tk.DISABLED)
        self.username_entry.config(state=tk.DISABLED)
        self.connect_btn.config(state=tk.DISABLED)
        self.disconnect_btn.config(state=tk.NORMAL)
        self.send_btn.config(state=tk.DISABLED)

    # logger
    def log(self, text):
        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, str(text) + "\n")
        self.log_box.config(state=tk.DISABLED)
        self.log_box.yview(tk.END)

    # status helper
    def set_status(self, text):
        self.status_label.config(text=text)

    # final result pop-up
    def show_final_result(self, msg):

        # parse winners
        winners_text = "Winner(s):\n" + "\n".join(msg.get('winners'))

        # Build text object
        text = (
            f"GAME OVER\n\n"
            f"Rank: {msg.get('rank')}\n"
            f"Total Score: {msg.get('total_score')}\n\n"
            f"Correct Answers: {msg.get('correct')}\n"
            f"Incorrect Answers: {msg.get('incorrect')}\n"
            f"Total Questions: {msg.get('total_questions')}\n"
            f"{winners_text}"
        )

        # Show info window
        messagebox.showinfo("Final Result", text)

        # Log it
        self.log(text)

        # Update status
        self.set_status("Game finished")
        self.result_received = 1

    # if server disconnects before game ends
    def handle_server_disconnect(self):
        self.awaiting_ack = False

        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

        if not self.root.winfo_exists():
            return

        self.set_status("Disconnected")
        self.log("Connection lost. Server is not accessible.")

        messagebox.showerror("Connection Lost", "Server is not accessible or has been closed.")

        # Enable inputs
        self.connect_btn.config(state=tk.NORMAL)
        self.ip_entry.config(state=tk.NORMAL)
        self.port_entry.config(state=tk.NORMAL)
        self.username_entry.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)

        # set connection flag to false
        self.connected = False

    # info message handler
    # "info" command only used when a user disconnects
    def handle_info(self, msg):
        self.log(f"[INFO] {msg['message']}")

    def handle_end(self):
        self.set_status("Game finished")
        self.connected = False

        self.connect_btn.config(state=tk.NORMAL)
        self.ip_entry.config(state=tk.NORMAL)
        self.port_entry.config(state=tk.NORMAL)
        self.username_entry.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)

    def on_close_window(self):
        try:
            self.disconnect()   # use disconnect function to properly close the connection
        except:
            pass
        try:
            self.root.destroy() # close the window
        except:
            pass

if __name__ == "__main__":
    SUquidClient()
