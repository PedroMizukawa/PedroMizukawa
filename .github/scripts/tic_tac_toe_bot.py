import json
import os
import re

import requests

TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
EVENT_NAME = os.environ["EVENT_NAME"]
EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]

API = f"https://api.github.com/repos/{REPO}"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

with open(EVENT_PATH) as f:
    EVENT = json.load(f)

ISSUE_NUMBER = EVENT["issue"]["number"]

CELL_EMOJI = {"X": "❌", "O": "⭕"}
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
STATE_RE = re.compile(r"<!-- ttt-state:([XO\-]{9}):(open|done) -->")


def render_board(board: str) -> str:
    rows = []
    for r in range(3):
        cells = []
        for c in range(3):
            i = r * 3 + c
            cells.append(CELL_EMOJI.get(board[i], f"`{i + 1}`"))
        rows.append(" ".join(cells))
    return "\n\n".join(rows)


def winner(board: str):
    for a, b, c in LINES:
        if board[a] != "-" and board[a] == board[b] == board[c]:
            return board[a]
    if "-" not in board:
        return "draw"
    return None


def minimax(board: str, player: str):
    w = winner(board)
    if w == "O":
        return 1, None
    if w == "X":
        return -1, None
    if w == "draw":
        return 0, None

    moves = [i for i, v in enumerate(board) if v == "-"]
    best_move = moves[0]

    if player == "O":
        best_score = -2
        for m in moves:
            score, _ = minimax(board[:m] + "O" + board[m + 1:], "X")
            if score > best_score:
                best_score, best_move = score, m
    else:
        best_score = 2
        for m in moves:
            score, _ = minimax(board[:m] + "X" + board[m + 1:], "O")
            if score < best_score:
                best_score, best_move = score, m

    return best_score, best_move


def post_comment(body: str):
    requests.post(f"{API}/issues/{ISSUE_NUMBER}/comments", headers=HEADERS, json={"body": body})


def close_issue():
    requests.patch(f"{API}/issues/{ISSUE_NUMBER}", headers=HEADERS, json={"state": "closed"})


def get_comments():
    r = requests.get(f"{API}/issues/{ISSUE_NUMBER}/comments", headers=HEADERS, params={"per_page": 100})
    r.raise_for_status()
    return r.json()


def state_marker(board: str, status: str) -> str:
    return f"<!-- ttt-state:{board}:{status} -->"


def get_state():
    for c in reversed(get_comments()):
        m = STATE_RE.search(c["body"])
        if m:
            return m.group(1), m.group(2)
    return "-" * 9, "open"


def main():
    if EVENT_NAME == "issues":
        board = "-" * 9
        post_comment(
            "🎮 **Vamos jogar da velha!**\n\n"
            "Você é ❌ e joga primeiro. Comente só o número da casa que quer jogar (1 a 9):\n\n"
            f"{render_board(board)}\n\n"
            f"{state_marker(board, 'open')}"
        )
        return

    comment_body = EVENT["comment"]["body"].strip()
    board, status = get_state()

    if status == "done":
        post_comment("O jogo já acabou por aqui! Abra uma nova issue com a label `tic-tac-toe` pra jogar de novo. 🔁")
        return

    if not re.fullmatch(r"[1-9]", comment_body):
        post_comment("Manda só um número de 1 a 9 correspondendo à casa que você quer jogar. 🙂")
        return

    pos = int(comment_body) - 1
    if board[pos] != "-":
        post_comment(f"Essa casa já está ocupada! Escolhe outra.\n\n{render_board(board)}")
        return

    board = board[:pos] + "X" + board[pos + 1:]
    w = winner(board)
    if w:
        result = "🎉 Você venceu! Parabéns, humano." if w == "X" else "🤝 Empate!"
        post_comment(f"{render_board(board)}\n\n{result}\n\n{state_marker(board, 'done')}")
        close_issue()
        return

    _, bot_move = minimax(board, "O")
    board = board[:bot_move] + "O" + board[bot_move + 1:]
    w = winner(board)
    if w:
        result = "🤖 Eu venci dessa vez! Bora outra?" if w == "O" else "🤝 Empate!"
        post_comment(f"{render_board(board)}\n\n{result}\n\n{state_marker(board, 'done')}")
        close_issue()
        return

    post_comment(f"Joguei na casa {bot_move + 1}. Sua vez!\n\n{render_board(board)}\n\n{state_marker(board, 'open')}")


if __name__ == "__main__":
    main()
